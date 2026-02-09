"""
이벤트 시스템 테스트

stat_behavior_components와 modular_combat_components가
이벤트를 통해 제대로 작동하는지 테스트합니다.
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from models import User, Monster
from service.dungeon.skill import Skill
from service.dungeon.components.attack_components import DamageComponent
from service.dungeon.components.stat_behavior_components import (
    CombatStatComponent, AccuracyStatComponent
)


def create_test_user():
    """테스트 유저 생성"""
    user = User(
        id=1,
        discord_id=123456789,
        username="TestUser",
        hp=1000,
        now_hp=800,
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
    class MockSkillModel:
        def __init__(self):
            self.id = 1001
            self.name = "테스트 공격"
            self.description = "테스트용 공격 스킬"
            self.attribute = "물리"

    damage_comp = DamageComponent()
    damage_comp.apply_config(
        {"ad_ratio": 1.5, "is_physical": True},
        skill_name="테스트 공격",
    )
    damage_comp.skill_name = "테스트 공격"
    damage_comp.skill_attribute = "물리"

    skill = Skill(MockSkillModel(), [damage_comp])
    return skill


def test_combat_stat_component():
    """CombatStatComponent 이벤트 테스트 (치명타, 흡혈)"""
    print("=" * 80)
    print("CombatStatComponent 이벤트 테스트")
    print("=" * 80)

    user = create_test_user()
    monster = create_test_monster()
    skill = create_test_attack_skill()

    # CombatStatComponent 설정 (치명타 50%, 흡혈 15%)
    print("\n📝 테스트 시나리오: 장비 CombatStatComponent (치명타 50%, 흡혈 15%)")
    print("-" * 80)

    combat_stat_comp = CombatStatComponent()
    combat_stat_comp.apply_config(
        {
            "crit_rate": 50.0,  # 50% 치명타
            "crit_damage": 50.0,  # 치명타 데미지 +50% (총 200%)
            "lifesteal": 15.0,  # 15% 흡혈
        },
        skill_name="전투 마스터리"
    )
    combat_stat_comp._tag = "stat_combat"

    user._equipment_components_cache = [combat_stat_comp]
    user.now_hp = 600  # HP 낮춤

    print(f"전투 전 HP: {user.now_hp}/{user.hp}")
    print(f"몬스터 HP: {monster.now_hp}/{monster.hp}")
    print()

    # 여러 번 공격해서 치명타가 발동하는지 확인
    total_crits = 0
    total_lifesteal = 0

    for i in range(10):
        old_hp = user.now_hp
        damage_comp = skill.components[0]
        result = damage_comp.on_turn(user, monster)

        # 치명타 확인
        if "💥" in result or "치명타" in result:
            total_crits += 1

        # 흡혈 확인
        hp_gained = user.now_hp - old_hp
        if hp_gained > 0:
            total_lifesteal += hp_gained

        if i == 0:  # 첫 번째 결과만 출력
            print(f"첫 번째 공격 결과:")
            print(result)
            print()

    print(f"10회 공격 후:")
    print(f"- 치명타 발동 횟수: {total_crits}/10 (예상: ~5회)")
    print(f"- 총 흡혈 회복량: {total_lifesteal} HP")
    print(f"- 최종 HP: {user.now_hp}/{user.hp}")
    print(f"- 몬스터 HP: {monster.now_hp}/{monster.hp}")
    print()

    if total_crits > 0:
        print("✅ 테스트 성공: 치명타가 발동했습니다!")
    else:
        print("⚠️ 치명타가 한 번도 안 나왔습니다 (확률적으로 가능)")

    if total_lifesteal > 0:
        print("✅ 테스트 성공: 흡혈이 작동했습니다!")
    else:
        print("❌ 테스트 실패: 흡혈이 작동하지 않았습니다.")

    print()
    print("=" * 80)


def test_accuracy_stat_component():
    """AccuracyStatComponent 이벤트 테스트 (명중률)"""
    print("=" * 80)
    print("AccuracyStatComponent 이벤트 테스트")
    print("=" * 80)

    user = create_test_user()
    monster = create_test_monster()
    skill = create_test_attack_skill()

    # AccuracyStatComponent 설정 (명중률 +20%)
    print("\n📝 테스트 시나리오: 장비 AccuracyStatComponent (명중률 +20%)")
    print("-" * 80)

    accuracy_comp = AccuracyStatComponent()
    accuracy_comp.apply_config(
        {"accuracy": 20.0},  # 명중률 +20%
        skill_name="정확도 향상"
    )
    accuracy_comp._tag = "stat_accuracy"

    user._equipment_components_cache = [accuracy_comp]

    print(f"전투 전 HP: {user.now_hp}/{user.hp}")
    print(f"몬스터 HP: {monster.now_hp}/{monster.hp}")
    print()

    # 여러 번 공격해서 명중률 확인
    hits = 0
    misses = 0

    for i in range(20):
        damage_comp = skill.components[0]
        result = damage_comp.on_turn(user, monster)

        if "MISS" in result:
            misses += 1
        else:
            hits += 1

    print(f"20회 공격 후:")
    print(f"- 명중: {hits}/20")
    print(f"- 회피: {misses}/20")
    print(f"- 명중률: {hits/20*100:.1f}%")
    print()

    if hits > 15:  # 명중률이 높아야 함
        print("✅ 테스트 성공: 명중률이 향상되었습니다!")
    else:
        print("⚠️ 명중률 향상 효과가 미미합니다 (확률적 변동 가능)")

    print()
    print("=" * 80)


if __name__ == "__main__":
    test_combat_stat_component()
    print()
    test_accuracy_stat_component()
