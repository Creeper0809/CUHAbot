"""
버프/디버프/상태이상 시스템

전투 중 엔티티에 적용되는 모든 효과를 관리합니다.
- Buff: 스탯 버프 (공격력, 방어력, 속도 등)
- StatusEffect: 상태이상 (화상, 독, 동결, 기절 등)

사용법:
    from service.dungeon.status import apply_status_effect, can_entity_act
"""
# 기본 클래스 + 등록 시스템
from service.dungeon.status.base import (
    Buff,
    StatusEffect,
    buff_register,
    status_effect_register,
    register_buff_with_tag,
    register_status_effect,
    get_buff_by_tag,
    get_status_effect_by_type,
)

# 스탯 버프 (임포트 시 자동 등록)
from service.dungeon.status.stat_buffs import (
    AttackBuff,
    DefenseBuff,
    SpeedBuff,
    ApAttackBuff,
    ApDefenseBuff,
    ShieldBuff,
)

# DOT 효과 (임포트 시 자동 등록)
from service.dungeon.status.dot_effects import (
    BurnEffect,
    PoisonEffect,
    BleedEffect,
    ErodeEffect,
)

# CC 효과 (임포트 시 자동 등록)
from service.dungeon.status.cc_effects import (
    SlowEffect,
    FreezeEffect,
    StunEffect,
    ParalyzeEffect,
)

# 디버프 효과 (임포트 시 자동 등록)
from service.dungeon.status.debuff_effects import (
    CurseEffect,
    MarkEffect,
    SubmergeEffect,
    ShockEffect,
    InfectionEffect,
    ComboEffect,
)

# 헬퍼 함수
from service.dungeon.status.helpers import (
    apply_status_effect,
    remove_status_effects,
    process_status_ticks,
    has_status_effect,
    get_status_stacks,
    can_entity_act,
    get_cc_effect_name,
    decay_all_durations,
    get_damage_taken_multiplier,
    has_curse_effect,
    get_status_icons,
)
