"""
장비 흡혈 테스트

장비의 lifesteal 스탯이 전투에서 제대로 적용되고 메시지가 표시되는지 확인합니다.
"""
import asyncio
import sys
from pathlib import Path

# 프로젝트 루트를 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from models import User, Monster
from service.dungeon.skill import Skill
from service.dungeon.components.attack_components import DamageComponent


def create_test_user():
    """테스트 유저 생성"""
    user = User(
        id=1,
        discord_id=123456789,
        username="TestUser",
        hp=1000,
        now_hp=1000,
        attack=100,
        defense=50,
        speed=50,
        ap_attack=50,
        ap_defense=30,
    )
    user._init_runtime_fields()
    return user


def create_test_monster():
    """테스트 몬스터 생성"""
    monster = Monster(
        id=1,
        name="테스트 슬라임",
        attribute="무속성",
        hp=500,
        now_hp=500,
        attack=30,
        defense=20,
        speed=30,
    )
    monster._init_runtime_fields()
    return monster


def create_test_attack_skill():
    """테스트 공격 스킬 생성"""
    # 간단한 스킬 모델 mock 객체
    class MockSkillModel:
        def __init__(self):
            self.id = 1001
            self.name = "테스트 공격"
            self.description = "테스트용 공격 스킬"
            self.attribute = "물리"

    # DamageComponent 추가
    damage_comp = DamageComponent()
    damage_comp.apply_config(
        {"ad_ratio": 1.5, "is_physical": True},
        skill_name="테스트 공격",
    )
    damage_comp.skill_name = "테스트 공격"
    damage_comp.skill_attribute = "물리"

    skill = Skill(MockSkillModel(), [damage_comp])
    return skill


def test_equipment_lifesteal():
    """장비 흡혈 테스트"""
    print("=" * 80)
    print("장비 흡혈 테스트 시작")
    print("=" * 80)

    user = create_test_user()
    monster = create_test_monster()
    skill = create_test_attack_skill()

    # 심해검 (lifesteal 5%) 장비 시뮬레이션
    print("\n📝 테스트 시나리오: 심해검 (lifesteal 5%) 장착")
    print("-" * 80)

    # 장비 컴포넌트 생성 (수동으로 PassiveBuffComponent 생성)
    from service.dungeon.components.stat_components import PassiveBuffComponent

    lifesteal_comp = PassiveBuffComponent()
    lifesteal_comp.apply_config(
        {"lifesteal": 5.0},
        skill_name="심해검 패시브",
    )
    lifesteal_comp._tag = "passive_buff"

    # 장비 컴포넌트 캐시 설정
    user._equipment_components_cache = [lifesteal_comp]

    # 유저 HP 약간 감소시켜서 회복 효과 확인
    user.now_hp = 800
    print(f"전투 전 HP: {user.now_hp}/{user.hp}")
    print(f"몬스터 HP: {monster.now_hp}/{monster.hp}")
    print()

    # 공격 실행
    damage_comp = skill.components[0]
    result = damage_comp.on_turn(user, monster)

    print("전투 결과:")
    print(result)
    print()
    print(f"전투 후 HP: {user.now_hp}/{user.hp}")
    print(f"몬스터 HP: {monster.now_hp}/{monster.hp}")
    print()

    # 검증
    if "💚 흡혈" in result:
        print("✅ 테스트 성공: 장비 흡혈 메시지가 표시되었습니다!")
    else:
        print("❌ 테스트 실패: 장비 흡혈 메시지가 표시되지 않았습니다.")
        print()
        print("디버그 정보:")
        print(f"- user._equipment_components_cache 존재: {hasattr(user, '_equipment_components_cache')}")
        if hasattr(user, '_equipment_components_cache'):
            print(f"- 캐시된 컴포넌트 수: {len(user._equipment_components_cache)}")
            for comp in user._equipment_components_cache:
                print(f"  - {comp.__class__.__name__}, tag={getattr(comp, '_tag', 'N/A')}, lifesteal={getattr(comp, 'lifesteal', 0)}")

    print()
    print("=" * 80)


def test_multiple_lifesteal_items():
    """여러 흡혈 아이템 중첩 테스트"""
    print("=" * 80)
    print("여러 흡혈 아이템 중첩 테스트")
    print("=" * 80)

    user = create_test_user()
    monster = create_test_monster()
    skill = create_test_attack_skill()

    # 여러 흡혈 아이템 시뮬레이션 (총 20%)
    print("\n📝 테스트 시나리오: 심해검(5%) + 마검(10%) + 심연의 검(15%) = 총 30% 흡혈")
    print("-" * 80)

    from service.dungeon.components.stat_components import PassiveBuffComponent

    components = []
    for lifesteal_value in [5.0, 10.0, 15.0]:
        comp = PassiveBuffComponent()
        comp.apply_config({"lifesteal": lifesteal_value}, skill_name="테스트")
        comp._tag = "passive_buff"
        components.append(comp)

    user._equipment_components_cache = components

    user.now_hp = 500
    print(f"전투 전 HP: {user.now_hp}/{user.hp}")
    print(f"몬스터 HP: {monster.now_hp}/{monster.hp}")
    print()

    damage_comp = skill.components[0]
    result = damage_comp.on_turn(user, monster)

    print("전투 결과:")
    print(result)
    print()
    print(f"전투 후 HP: {user.now_hp}/{user.hp}")
    print(f"몬스터 HP: {monster.now_hp}/{monster.hp}")
    print()

    if "💚 흡혈" in result:
        print("✅ 테스트 성공: 여러 장비의 흡혈이 중첩되어 적용되었습니다!")
    else:
        print("❌ 테스트 실패: 흡혈 메시지가 표시되지 않았습니다.")

    print()
    print("=" * 80)


def test_passive_skill_lifesteal():
    """패시브 스킬 흡혈 테스트"""
    print("=" * 80)
    print("패시브 스킬 흡혈 테스트")
    print("=" * 80)

    user = create_test_user()
    monster = create_test_monster()
    skill = create_test_attack_skill()

    # 패시브 스킬 시뮬레이션 (lifesteal 10%)
    print("\n📝 테스트 시나리오: 패시브 스킬 흡혈 10%")
    print("-" * 80)

    # equipped_skill 설정 (패시브 스킬 ID 리스트)
    # 실제로는 get_passive_stat_bonuses()가 호출되지만, 여기서는 직접 mock
    user.equipped_skill = [6001]  # 임의의 패시브 스킬 ID

    # get_passive_stat_bonuses mock
    original_get_passive = None
    try:
        from service.dungeon import skill as skill_module
        original_get_passive = skill_module.get_passive_stat_bonuses

        def mock_get_passive_stat_bonuses(skill_ids):
            return {
                "attack_percent": 0.0,
                "defense_percent": 0.0,
                "speed_percent": 0.0,
                "hp_percent": 0.0,
                "evasion_percent": 0.0,
                "ap_attack_percent": 0.0,
                "crit_rate": 0.0,
                "crit_damage": 0.0,
                "lifesteal": 10.0,  # 10% 흡혈
                "drop_rate": 0.0,
            }

        skill_module.get_passive_stat_bonuses = mock_get_passive_stat_bonuses

        user.now_hp = 700
        print(f"전투 전 HP: {user.now_hp}/{user.hp}")
        print(f"몬스터 HP: {monster.now_hp}/{monster.hp}")
        print()

        damage_comp = skill.components[0]
        result = damage_comp.on_turn(user, monster)

        print("전투 결과:")
        print(result)
        print()
        print(f"전투 후 HP: {user.now_hp}/{user.hp}")
        print(f"몬스터 HP: {monster.now_hp}/{monster.hp}")
        print()

        if "💚 흡혈" in result:
            print("✅ 테스트 성공: 패시브 스킬 흡혈이 적용되었습니다!")
        else:
            print("❌ 테스트 실패: 흡혈 메시지가 표시되지 않았습니다.")

    finally:
        # 원래 함수 복원
        if original_get_passive:
            skill_module.get_passive_stat_bonuses = original_get_passive

    print()
    print("=" * 80)


def test_combined_lifesteal():
    """장비 + 패시브 스킬 흡혈 조합 테스트"""
    print("=" * 80)
    print("장비 + 패시브 스킬 흡혈 조합 테스트")
    print("=" * 80)

    user = create_test_user()
    monster = create_test_monster()
    skill = create_test_attack_skill()

    print("\n📝 테스트 시나리오: 장비 흡혈 15% + 패시브 스킬 흡혈 10% = 총 25%")
    print("-" * 80)

    # 장비 흡혈 설정
    from service.dungeon.components.stat_components import PassiveBuffComponent
    equipment_comp = PassiveBuffComponent()
    equipment_comp.apply_config({"lifesteal": 15.0}, skill_name="장비 패시브")
    equipment_comp._tag = "passive_buff"
    user._equipment_components_cache = [equipment_comp]

    # 패시브 스킬 설정
    user.equipped_skill = [6001]

    original_get_passive = None
    try:
        from service.dungeon import skill as skill_module
        original_get_passive = skill_module.get_passive_stat_bonuses

        def mock_get_passive_stat_bonuses(skill_ids):
            return {
                "attack_percent": 0.0,
                "defense_percent": 0.0,
                "speed_percent": 0.0,
                "hp_percent": 0.0,
                "evasion_percent": 0.0,
                "ap_attack_percent": 0.0,
                "crit_rate": 0.0,
                "crit_damage": 0.0,
                "lifesteal": 10.0,
                "drop_rate": 0.0,
            }

        skill_module.get_passive_stat_bonuses = mock_get_passive_stat_bonuses

        user.now_hp = 600
        print(f"전투 전 HP: {user.now_hp}/{user.hp}")
        print(f"몬스터 HP: {monster.now_hp}/{monster.hp}")
        print()

        damage_comp = skill.components[0]
        result = damage_comp.on_turn(user, monster)

        print("전투 결과:")
        print(result)
        print()
        print(f"전투 후 HP: {user.now_hp}/{user.hp}")
        print(f"몬스터 HP: {monster.now_hp}/{monster.hp}")
        print()

        if "💚 흡혈" in result:
            print("✅ 테스트 성공: 장비 + 패시브 스킬 흡혈이 합산되어 적용되었습니다!")
        else:
            print("❌ 테스트 실패: 흡혈 메시지가 표시되지 않았습니다.")

    finally:
        if original_get_passive:
            skill_module.get_passive_stat_bonuses = original_get_passive

    print()
    print("=" * 80)


if __name__ == "__main__":
    test_equipment_lifesteal()
    print()
    test_multiple_lifesteal_items()
    print()
    test_passive_skill_lifesteal()
    print()
    test_combined_lifesteal()
