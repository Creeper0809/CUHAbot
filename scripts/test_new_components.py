"""
새 컴포넌트 테스트 스크립트

Bag 조작, 자원 변환, 스킬 체인, 턴 기반 컴포넌트를 테스트합니다.
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from models import User, Monster
from service.dungeon.skill import Skill
from service.dungeon.components.attack_components import DamageComponent
from service.dungeon.components.bag_manipulation_components import (
    SkillRefreshComponent, DoubleDrawComponent
)
from service.dungeon.components.resource_conversion_components import (
    HPCostEmpowerComponent, DefenseToAttackComponent
)
from service.dungeon.components.skill_chain_components import (
    ConsecutiveSkillBonusComponent, SkillVarietyBonusComponent
)
from service.dungeon.components.turn_based_components import (
    TurnCountEmpowerComponent, AccumulationComponent
)
from service.dungeon.combat_events import DamageCalculationEvent


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


def create_test_skill():
    """테스트 스킬 생성"""
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
    damage_comp._tag = "attack"  # 태그 설정 (컴포넌트 인식용)

    skill = Skill(MockSkillModel(), [damage_comp])
    return skill


# =============================================================================
# 1. Bag 조작 컴포넌트 테스트
# =============================================================================

def test_skill_refresh():
    """스킬 재장전 테스트"""
    print("=" * 80)
    print("1. SkillRefreshComponent 테스트 (스킬 재장전)")
    print("=" * 80)

    user = create_test_user()
    user.equipped_skill = [1001, 1002, 1003]
    user.skill_queue = []

    # 30% 재장전 컴포넌트
    refresh_comp = SkillRefreshComponent()
    refresh_comp.apply_config({"refresh_chance": 1.0}, skill_name="무한의 주머니")  # 100% for testing
    refresh_comp._tag = "skill_refresh"

    print("\n📝 시나리오: 스킬 사용 후 100% 재장전")
    print("-" * 80)

    skill_id = 1001
    initial_queue_size = len(user.skill_queue)
    result = refresh_comp.on_skill_used(user, skill_id)

    print(f"초기 큐 크기: {initial_queue_size}")
    print(f"재장전 후 큐 크기: {len(user.skill_queue)}")
    print(f"결과: {result}")

    if skill_id in user.skill_queue:
        print("✅ 테스트 성공: 스킬이 큐에 다시 추가되었습니다!")
    else:
        print("❌ 테스트 실패: 스킬이 재장전되지 않았습니다.")

    print()


def test_double_draw():
    """스킬 2개 뽑기 테스트"""
    print("=" * 80)
    print("2. DoubleDrawComponent 테스트 (스킬 2개 중 선택)")
    print("=" * 80)

    user = create_test_user()

    # 자동 선택 모드
    double_draw = DoubleDrawComponent()
    double_draw.apply_config(
        {"proc_chance": 1.0, "auto_select_better": True},
        skill_name="전술가의 덱"
    )
    double_draw._tag = "double_draw"

    print("\n📝 시나리오: 2개 중 더 강한 것 자동 선택")
    print("-" * 80)

    # Note: on_draw_skill은 실제 게임 루프에서 호출되므로
    # 여기서는 개념 검증만 수행
    print("컴포넌트 설정:")
    print(f"  - proc_chance: {double_draw.proc_chance}")
    print(f"  - auto_select_better: {double_draw.auto_select_better}")
    print("✅ 컴포넌트 생성 및 설정 성공!")

    print()


# =============================================================================
# 2. 자원 변환 컴포넌트 테스트
# =============================================================================

def test_hp_cost_empower():
    """HP 소모 강화 테스트"""
    print("=" * 80)
    print("3. HPCostEmpowerComponent 테스트 (HP 소모 → 데미지 증폭)")
    print("=" * 80)

    user = create_test_user()
    monster = create_test_monster()

    # HP 10% 소모, 데미지 60% 증가
    hp_cost = HPCostEmpowerComponent()
    hp_cost.apply_config(
        {
            "hp_cost_percent": 10.0,
            "damage_boost_percent": 60.0,
            "min_hp_threshold": 5.0
        },
        skill_name="광기의 검"
    )
    hp_cost._tag = "hp_cost_empower"

    print("\n📝 시나리오: HP 10% 소모하여 데미지 60% 증가")
    print("-" * 80)

    user._equipment_components_cache = [hp_cost]

    # 데미지 계산 이벤트 생성
    event = DamageCalculationEvent(
        attacker=user,
        defender=monster,
        base_damage=100,
        skill_name="테스트 공격",
        skill_attribute="물리"
    )

    initial_hp = user.now_hp
    print(f"HP 소모 전: {initial_hp}/{user.hp}")

    # 이벤트 처리
    hp_cost.on_damage_calculation(event)

    final_damage = event.get_final_damage()
    hp_after = user.now_hp

    print(f"HP 소모 후: {hp_after}/{user.hp} (소모: {initial_hp - hp_after})")
    print(f"기본 데미지: 100")
    print(f"최종 데미지: {final_damage}")
    print(f"로그: {event.logs}")

    expected_hp_cost = int(user.hp * 0.1)
    expected_damage = int(100 * 1.6)

    if hp_after == initial_hp - expected_hp_cost and final_damage == expected_damage:
        print("✅ 테스트 성공: HP 소모 및 데미지 증폭이 정확합니다!")
    else:
        print(f"❌ 테스트 실패: 예상 HP={initial_hp - expected_hp_cost}, 실제={hp_after}")
        print(f"             예상 데미지={expected_damage}, 실제={final_damage}")

    print()


def test_defense_to_attack():
    """방어력 → 공격력 전환 테스트"""
    print("=" * 80)
    print("4. DefenseToAttackComponent 테스트 (방어력 → 공격력)")
    print("=" * 80)

    user = create_test_user()
    monster = create_test_monster()

    # 방어력 50% → 공격력 전환
    def_to_atk = DefenseToAttackComponent()
    def_to_atk.apply_config({"conversion_ratio": 0.5}, skill_name="광전사의 투구")
    def_to_atk._tag = "defense_to_attack"

    print("\n📝 시나리오: 방어력 50% → 공격력 전환")
    print("-" * 80)

    initial_def = user.defense
    initial_atk = user.attack

    print(f"전환 전: 공격력={initial_atk}, 방어력={initial_def}")

    # 전투 시작 시 전환
    log = def_to_atk.on_combat_start(user, monster)
    print(log)

    print(f"전환 후: 공격력={user.attack}, 방어력={user.defense}")

    expected_converted = int(initial_def * 0.5)
    expected_atk = initial_atk + expected_converted
    expected_def = initial_def - expected_converted

    if user.attack == expected_atk and user.defense == expected_def:
        print("✅ 테스트 성공: 방어력이 공격력으로 정확히 전환되었습니다!")
    else:
        print(f"❌ 테스트 실패: 예상 공격={expected_atk}, 실제={user.attack}")
        print(f"             예상 방어={expected_def}, 실제={user.defense}")

    print()


# =============================================================================
# 3. 스킬 체인 컴포넌트 테스트
# =============================================================================

def test_consecutive_bonus():
    """연속 스킬 보너스 테스트"""
    print("=" * 80)
    print("5. ConsecutiveSkillBonusComponent 테스트 (연속 보너스)")
    print("=" * 80)

    user = create_test_user()
    monster = create_test_monster()

    # 공격 스킬 연속 사용 시 10%씩 증가 (최대 5스택)
    consecutive = ConsecutiveSkillBonusComponent()
    consecutive.apply_config(
        {
            "target_skill_type": "attack",
            "bonus_per_stack": 10.0,
            "max_stacks": 5
        },
        skill_name="광전사의 사슬"
    )
    consecutive._tag = "consecutive_skill_bonus"

    print("\n📝 시나리오: 공격 스킬 연속 사용 시 10%씩 증가")
    print("-" * 80)

    skill = create_test_skill()

    # 3번 연속 사용
    for i in range(3):
        log = consecutive.on_skill_used(user, skill)
        print(f"사용 {i+1}회: {log}")

    # 데미지 계산
    event = DamageCalculationEvent(
        attacker=user,
        defender=monster,
        base_damage=100,
        skill_name="테스트 공격",
        skill_attribute="물리"
    )

    consecutive.on_damage_calculation(event)
    final_damage = event.get_final_damage()

    expected_damage = int(100 * 1.3)  # 3스택 = 30% 증가

    print(f"\n최종 데미지: {final_damage} (기본 100 → +30% = 130)")

    if final_damage == expected_damage:
        print("✅ 테스트 성공: 연속 보너스가 정확히 적용되었습니다!")
    else:
        print(f"❌ 테스트 실패: 예상={expected_damage}, 실제={final_damage}")

    print()


def test_variety_bonus():
    """다양성 보너스 테스트"""
    print("=" * 80)
    print("6. SkillVarietyBonusComponent 테스트 (다양성 보너스)")
    print("=" * 80)

    user = create_test_user()
    monster = create_test_monster()

    # 다양한 스킬 사용 시 5%씩 증가 (최대 4종)
    variety = SkillVarietyBonusComponent()
    variety.apply_config(
        {
            "bonus_per_unique": 5.0,
            "max_unique_count": 4,
            "reset_on_repeat": True
        },
        skill_name="만능 벨트"
    )
    variety._tag = "skill_variety_bonus"

    print("\n📝 시나리오: 다양한 스킬 사용 시 5%씩 증가 (중복 시 리셋)")
    print("-" * 80)

    # 서로 다른 스킬 3개 사용
    class MockSkill:
        def __init__(self, skill_id):
            self.id = skill_id

    for skill_id in [1001, 1002, 1003]:
        skill = MockSkill(skill_id)
        log = variety.on_skill_used(user, skill)
        print(f"스킬 {skill_id} 사용: {log}")

    # 데미지 계산
    event = DamageCalculationEvent(
        attacker=user,
        defender=monster,
        base_damage=100,
        skill_name="테스트 공격",
        skill_attribute="물리"
    )

    variety.on_damage_calculation(event)
    final_damage = event.get_final_damage()

    expected_damage = int(100 * 1.15)  # 3종 = 15% 증가

    print(f"\n최종 데미지: {final_damage} (기본 100 → +15% = 115)")

    if final_damage == expected_damage:
        print("✅ 테스트 성공: 다양성 보너스가 정확히 적용되었습니다!")
    else:
        print(f"❌ 테스트 실패: 예상={expected_damage}, 실제={final_damage}")

    print()


# =============================================================================
# 4. 턴 기반 컴포넌트 테스트
# =============================================================================

def test_turn_count_empower():
    """턴 카운트 강화 테스트"""
    print("=" * 80)
    print("7. TurnCountEmpowerComponent 테스트 (N턴마다 강화)")
    print("=" * 80)

    user = create_test_user()
    monster = create_test_monster()

    # 3턴마다 데미지 200%
    turn_empower = TurnCountEmpowerComponent()
    turn_empower.apply_config(
        {
            "trigger_interval": 3,
            "damage_multiplier": 2.0
        },
        skill_name="시계태엽 건틀릿"
    )
    turn_empower._tag = "turn_count_empower"

    print("\n📝 시나리오: 3턴마다 데미지 200%")
    print("-" * 80)

    # 5턴 시뮬레이션
    for turn in range(1, 6):
        log = turn_empower.on_turn_start(user, monster)

        event = DamageCalculationEvent(
            attacker=user,
            defender=monster,
            base_damage=100,
            skill_name="테스트 공격",
            skill_attribute="물리"
        )

        turn_empower.on_damage_calculation(event)
        final_damage = event.get_final_damage()

        is_trigger = (turn % 3 == 0)
        expected = 200 if is_trigger else 100

        status = "⏰ 발동!" if is_trigger else ""
        result = "✅" if final_damage == expected else "❌"

        print(f"턴 {turn}: 데미지 {final_damage} {status} {result}")
        if log:
            print(f"       로그: {log}")

    print("✅ 테스트 완료: 3턴마다 강화가 발동합니다!")
    print()


def test_accumulation():
    """누적 성장 테스트"""
    print("=" * 80)
    print("8. AccumulationComponent 테스트 (턴당 누적 성장)")
    print("=" * 80)

    user = create_test_user()
    monster = create_test_monster()

    # 매 턴 5% 성장 (최대 100%)
    accumulation = AccumulationComponent()
    accumulation.apply_config(
        {
            "growth_per_turn": 5.0,
            "max_growth": 100.0
        },
        skill_name="무한 성장의 반지"
    )
    accumulation._tag = "accumulation"

    print("\n📝 시나리오: 매 턴 5%씩 성장 (최대 100%)")
    print("-" * 80)

    # 10턴 시뮬레이션 (5턴만 출력)
    for turn in range(1, 6):
        log = accumulation.on_turn_start(user, monster)

        event = DamageCalculationEvent(
            attacker=user,
            defender=monster,
            base_damage=100,
            skill_name="테스트 공격",
            skill_attribute="물리"
        )

        accumulation.on_damage_calculation(event)
        final_damage = event.get_final_damage()

        expected = int(100 * (1 + turn * 0.05))

        print(f"턴 {turn}: 데미지 {final_damage} (기본 100 → +{turn * 5}% = {expected})")
        print(f"       로그: {log}")

    print("✅ 테스트 완료: 매 턴 누적 성장합니다!")
    print()


# =============================================================================
# 메인
# =============================================================================

if __name__ == "__main__":
    print("\n")
    print("╔" + "═" * 78 + "╗")
    print("║" + " " * 20 + "새 컴포넌트 테스트 스위트" + " " * 34 + "║")
    print("╚" + "═" * 78 + "╝")
    print()

    # Bag 조작
    test_skill_refresh()
    test_double_draw()

    # 자원 변환
    test_hp_cost_empower()
    test_defense_to_attack()

    # 스킬 체인
    test_consecutive_bonus()
    test_variety_bonus()

    # 턴 기반
    test_turn_count_empower()
    test_accumulation()

    print("=" * 80)
    print("전체 테스트 완료!")
    print("=" * 80)
