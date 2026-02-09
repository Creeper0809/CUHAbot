"""
스탯 행동 컴포넌트 테스트

새로 분리된 컴포넌트들이 제대로 로드되고 작동하는지 검증합니다.
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def test_component_registration():
    """컴포넌트가 skill_component_register에 등록되었는지 확인"""
    from service.dungeon.components.base import skill_component_register

    print("=" * 60)
    print("✅ 컴포넌트 등록 테스트")
    print("=" * 60)

    expected_tags = [
        "stat_bonus",
        "stat_combat",
        "stat_defense",
        "stat_accuracy",
        "stat_elemental_damage",
    ]

    for tag in expected_tags:
        if tag in skill_component_register:
            comp_class = skill_component_register[tag]
            print(f"   ✓ {tag:25s} → {comp_class.__name__}")
        else:
            print(f"   ✗ {tag:25s} → NOT FOUND")
            raise AssertionError(f"Tag '{tag}' not registered")

    print()


def test_bonus_stat_component():
    """BonusStatComponent 로딩 및 메타데이터 테스트"""
    from service.dungeon.components.base import skill_component_register

    print("=" * 60)
    print("✅ BonusStatComponent 테스트")
    print("=" * 60)

    comp_class = skill_component_register["stat_bonus"]
    comp = comp_class()

    config = {
        "drop_rate": 15.0,
        "exp_bonus": 10.0,
    }

    comp.apply_config(config, "테스트 스킬")

    # 메타데이터 확인
    assert "drop_rate" in comp.STAT_METADATA
    assert "exp_bonus" in comp.STAT_METADATA

    # 표시용 스탯 추출
    displayable = comp.get_displayable_stats()

    print(f"   설정: {config}")
    print(f"   표시용 스탯: {displayable}")

    assert "drop_rate" in displayable
    assert displayable["drop_rate"]["value"] == 15.0
    assert displayable["drop_rate"]["metadata"]["label"] == "드롭률"

    print("   ✓ BonusStatComponent 정상 작동\n")


def test_combat_stat_component():
    """CombatStatComponent 로딩 및 이벤트 훅 테스트"""
    from service.dungeon.components.base import skill_component_register
    from service.dungeon.combat_events import DamageCalculationEvent, DamageDealtEvent

    print("=" * 60)
    print("✅ CombatStatComponent 테스트")
    print("=" * 60)

    comp_class = skill_component_register["stat_combat"]
    comp = comp_class()

    config = {
        "crit_rate": 25.0,
        "crit_damage": 50.0,
        "lifesteal": 10.0,
        "armor_pen": 30.0,
    }

    comp.apply_config(config, "테스트 스킬")

    print(f"   설정: {config}")

    # 메타데이터 확인
    displayable = comp.get_displayable_stats()
    print(f"   표시용 스탯: {list(displayable.keys())}")

    # on_damage_calculation 메서드 존재 확인
    assert hasattr(comp, "on_damage_calculation")
    assert hasattr(comp, "on_deal_damage")

    # 더미 이벤트 생성 (실제 Entity 대신 Mock 객체)
    class MockEntity:
        def __init__(self):
            self.now_hp = 100
            self.max_hp = 100

        def heal(self, amount):
            self.now_hp = min(self.now_hp + amount, self.max_hp)

    attacker = MockEntity()
    defender = MockEntity()

    # 데미지 계산 이벤트
    calc_event = DamageCalculationEvent(
        attacker=attacker,
        defender=defender,
        base_damage=100,
        skill_name="테스트",
    )

    comp.on_damage_calculation(calc_event)

    # 방어구 관통 적용 확인
    assert calc_event.defense_ignore > 0
    print(f"   ✓ 방어구 관통 적용: {calc_event.defense_ignore * 100}%")

    # 치명타는 랜덤이므로 여러 번 시도
    crit_count = 0
    for _ in range(100):
        event = DamageCalculationEvent(
            attacker=attacker,
            defender=defender,
            base_damage=100,
        )
        comp.on_damage_calculation(event)
        if event.is_critical:
            crit_count += 1

    print(f"   ✓ 치명타 발생률: {crit_count}% (설정: 25%)")

    # 흡혈 테스트
    attacker.now_hp = 50  # HP 감소
    dealt_event = DamageDealtEvent(
        attacker=attacker,
        defender=defender,
        damage=100,
        damage_attribute="물리",
    )

    comp.on_deal_damage(dealt_event)

    assert attacker.now_hp > 50  # HP 회복됨
    print(f"   ✓ 흡혈 작동: 50 HP → {attacker.now_hp} HP")
    print(f"   ✓ 흡혈 로그: {dealt_event.logs}")

    print()


def test_defense_stat_component():
    """DefenseStatComponent 로딩 및 저항 테스트"""
    from service.dungeon.components.base import skill_component_register
    from service.dungeon.combat_events import TakeDamageEvent

    print("=" * 60)
    print("✅ DefenseStatComponent 테스트")
    print("=" * 60)

    comp_class = skill_component_register["stat_defense"]
    comp = comp_class()

    config = {
        "fire_resist": 30.0,
        "ice_resist": 20.0,
    }

    comp.apply_config(config, "테스트 스킬")

    print(f"   설정: {config}")

    # 메타데이터 확인
    displayable = comp.get_displayable_stats()
    print(f"   표시용 스탯: {list(displayable.keys())}")

    # on_take_damage 메서드 존재 확인
    assert hasattr(comp, "on_take_damage")

    # 더미 엔티티
    class MockEntity:
        def get_name(self):
            return "테스트"

    attacker = MockEntity()
    defender = MockEntity()

    # 화염 데미지 저항 테스트
    event = TakeDamageEvent(
        attacker=attacker,
        defender=defender,
        damage=100,
        damage_attribute="화염",
    )

    comp.on_take_damage(event)

    # 저항 적용 확인
    assert len(event.reductions) > 0
    final_damage = event.get_final_damage()
    print(f"   ✓ 화염 저항 적용: 100 → {final_damage} (30% 저항)")
    print(f"   ✓ 저항 로그: {event.logs}")

    # 냉기 데미지 저항 테스트
    event2 = TakeDamageEvent(
        attacker=attacker,
        defender=defender,
        damage=100,
        damage_attribute="냉기",
    )

    comp.on_take_damage(event2)
    final_damage2 = event2.get_final_damage()
    print(f"   ✓ 냉기 저항 적용: 100 → {final_damage2} (20% 저항)")

    print()


def test_elemental_damage_component():
    """ElementalDamageComponent 테스트"""
    from service.dungeon.components.base import skill_component_register
    from service.dungeon.combat_events import DamageCalculationEvent

    print("=" * 60)
    print("✅ ElementalDamageComponent 테스트")
    print("=" * 60)

    comp_class = skill_component_register["stat_elemental_damage"]
    comp = comp_class()

    config = {
        "fire_damage": 25.0,
        "ice_damage": 15.0,
    }

    comp.apply_config(config, "테스트 스킬")

    print(f"   설정: {config}")

    # 메타데이터 확인
    displayable = comp.get_displayable_stats()
    print(f"   표시용 스탯: {list(displayable.keys())}")

    # 더미 엔티티
    class MockEntity:
        pass

    attacker = MockEntity()
    defender = MockEntity()

    # 화염 스킬에 화염 데미지 증가 적용
    event = DamageCalculationEvent(
        attacker=attacker,
        defender=defender,
        base_damage=100,
        skill_attribute="화염",
    )

    comp.on_damage_calculation(event)

    # 배율 적용 확인
    assert len(event.multipliers) > 1  # 기본 1.0 + 추가 배율
    final_damage = event.get_final_damage()
    print(f"   ✓ 화염 스킬 데미지 증가: 100 → {final_damage} (+25%)")
    print(f"   ✓ 데미지 로그: {event.logs}")

    print()


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("스탯 행동 컴포넌트 시스템 테스트")
    print("=" * 60 + "\n")

    try:
        test_component_registration()
        test_bonus_stat_component()
        test_combat_stat_component()
        test_defense_stat_component()
        test_elemental_damage_component()

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
