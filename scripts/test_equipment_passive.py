"""
장비 효과 PassiveBuffComponent 시스템 테스트

PassiveBuffComponent를 사용한 장비 효과 시스템을 검증합니다.
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def test_create_component():
    """컴포넌트 로딩 테스트"""
    from service.item.equipment_component_loader import load_equipment_components

    config = {
        "components": [
            {
                "tag": "passive_buff",
                "crit_rate": 5,
                "lifesteal": 3,
                "attack": 10,
            }
        ]
    }

    components = load_equipment_components(config)

    print("✅ 컴포넌트 로딩")
    print(f"   입력: {config}")
    print(f"   컴포넌트 수: {len(components)}")

    assert len(components) == 1
    component = components[0]
    assert component.crit_rate == 5
    assert component.lifesteal == 3

    print("   ✓ 컴포넌트가 정상적으로 로드됨\n")


def test_get_stat_bonuses():
    """스탯 보너스 추출 테스트"""
    from service.item.equipment_component_loader import (
        load_equipment_components,
        get_equipment_passive_stats
    )

    config = {
        "components": [
            {
                "tag": "passive_buff",
                "crit_rate": 10,
                "crit_damage": 20,
                "attack": 50,
                "fire_resist": 15,
            }
        ]
    }

    components = load_equipment_components(config)
    bonuses = get_equipment_passive_stats(components)

    print("✅ 스탯 보너스 추출")
    print(f"   설정: {config}")
    print(f"   보너스: {bonuses}")

    assert bonuses["crit_rate"] == 10
    assert bonuses["crit_damage"] == 20
    assert bonuses["attack"] == 50
    assert bonuses["fire_resist"] == 15

    print("   ✓ 모든 스탯이 정확히 추출됨\n")


def test_aggregate_effects():
    """다중 컴포넌트 집계 테스트"""
    from service.item.equipment_component_loader import (
        load_equipment_components,
        get_equipment_passive_stats
    )

    # 두 개의 컴포넌트를 가진 설정
    config = {
        "components": [
            {
                "tag": "passive_buff",
                "crit_rate": 5,
                "attack": 10,
            },
            {
                "tag": "passive_buff",
                "crit_rate": 3,
                "attack": 15,
            }
        ]
    }

    components = load_equipment_components(config)
    bonuses = get_equipment_passive_stats(components)

    print("✅ 다중 컴포넌트 집계")
    print(f"   설정: {config}")
    print(f"   보너스: {bonuses}")

    assert bonuses["crit_rate"] == 8  # 5 + 3
    assert bonuses["attack"] == 25     # 10 + 15

    print("   ✓ 다중 컴포넌트가 정확히 합산됨\n")


def test_percent_effects():
    """퍼센트 효과 테스트"""
    from service.item.equipment_component_loader import (
        load_equipment_components,
        get_equipment_passive_stats
    )
    from service.item.equipment_service import _apply_percent_bonuses

    config = {
        "components": [
            {
                "tag": "passive_buff",
                "bonus_hp_pct": 10,
                "bonus_speed_pct": 5,
                "crit_rate": 15,
            }
        ]
    }

    base_stats = {
        "hp": 1000,
        "attack": 100,
        "ap_attack": 50,
        "ad_defense": 30,
        "ap_defense": 20,
        "speed": 100,
    }

    print("✅ 퍼센트 효과 적용")
    print(f"   베이스 HP: {base_stats['hp']}")
    print(f"   베이스 속도: {base_stats['speed']}")
    print(f"   설정: {config}")

    components = load_equipment_components(config)
    passive_stats = get_equipment_passive_stats(components)
    result = _apply_percent_bonuses(passive_stats, base_stats)

    print(f"   결과: {result}")

    assert result.get("hp", 0) == 100  # 1000 * 0.1
    assert result.get("speed", 0) == 5  # 100 * 0.05
    assert result.get("crit_rate", 0) == 15

    print("   ✓ 퍼센트 효과가 베이스 스탯에 올바르게 적용됨\n")


def test_all_stats_percent():
    """모든 스탯 퍼센트 보너스 테스트"""
    from service.item.equipment_component_loader import (
        load_equipment_components,
        get_equipment_passive_stats
    )
    from service.item.equipment_service import _apply_percent_bonuses

    config = {
        "components": [
            {
                "tag": "passive_buff",
                "bonus_all_stats_pct": 10,
            }
        ]
    }

    base_stats = {
        "hp": 1000,
        "attack": 100,
        "ap_attack": 50,
        "ad_defense": 30,
        "ap_defense": 20,
        "speed": 80,
    }

    print("✅ 모든 스탯 퍼센트 보너스")
    print(f"   베이스 스탯: {base_stats}")
    print(f"   효과: 모든 스탯 +10%")

    components = load_equipment_components(config)
    passive_stats = get_equipment_passive_stats(components)
    result = _apply_percent_bonuses(passive_stats, base_stats)

    print(f"   결과: {result}")

    assert result["hp"] == 100
    assert result["attack"] == 10
    assert result["ap_attack"] == 5
    assert result["ad_defense"] == 3
    assert result["ap_defense"] == 2
    assert result["speed"] == 8

    print("   ✓ 모든 스탯에 10% 보너스 적용됨\n")


def test_mixed_effects():
    """혼합 효과 테스트"""
    from service.item.equipment_component_loader import (
        load_equipment_components,
        get_equipment_passive_stats
    )
    from service.item.equipment_service import _apply_percent_bonuses

    config = {
        "components": [
            {
                "tag": "passive_buff",
                "attack": 50,
                "bonus_hp_pct": 20,
                "crit_rate": 10,
                "lifesteal": 5,
                "fire_resist": 30,
            }
        ]
    }

    base_stats = {
        "hp": 500,
        "attack": 0,
        "ap_attack": 0,
        "ad_defense": 0,
        "ap_defense": 0,
        "speed": 0,
    }

    print("✅ 혼합 효과 테스트")
    print(f"   설정: {config}")

    components = load_equipment_components(config)
    passive_stats = get_equipment_passive_stats(components)
    result = _apply_percent_bonuses(passive_stats, base_stats)

    print(f"   결과: {result}")

    assert result["attack"] == 50
    assert result["hp"] == 100  # 500 * 0.2
    assert result["crit_rate"] == 10
    assert result["lifesteal"] == 5
    assert result["fire_resist"] == 30

    print("   ✓ 고정값과 퍼센트가 올바르게 혼합 적용됨\n")


if __name__ == "__main__":
    print("=" * 60)
    print("장비 효과 PassiveBuffComponent 시스템 테스트")
    print("=" * 60 + "\n")

    try:
        test_create_component()
        test_get_stat_bonuses()
        test_aggregate_effects()
        test_percent_effects()
        test_all_stats_percent()
        test_mixed_effects()

        print("=" * 60)
        print("✅ 모든 테스트 통과!")
        print("=" * 60)
    except AssertionError as e:
        print(f"\n❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
