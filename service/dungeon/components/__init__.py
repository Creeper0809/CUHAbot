"""
스킬 컴포넌트 시스템

스킬의 다양한 효과를 컴포넌트 단위로 분리하여 조합합니다.
"""
# 레지스트리 및 기본 클래스
from service.dungeon.components.base import (
    skill_component_register,
    register_skill_with_tag,
    get_component_by_tag,
    SkillComponent,
)

# 컴포넌트 임포트 (데코레이터로 자동 등록)
from service.dungeon.components.attack_components import (
    DamageComponent, LifestealComponent, ConsumeComponent,
)
from service.dungeon.components.support_components import (
    HealComponent, ShieldComponent, CleanseComponent,
)
from service.dungeon.components.stat_components import (
    BuffComponent, DebuffComponent, PassiveBuffComponent,
    PassiveRegenComponent, ConditionalPassiveComponent,
    TurnScalingComponent, DebuffReductionComponent,
)
from service.dungeon.components.special_components import (
    StatusComponent, ComboComponent, SummonComponent,
    OnDeathReviveComponent, OnDeathSummonComponent,
)
from service.dungeon.components.defensive_passive_components import (
    ElementImmunityComponent, ElementResistanceComponent,
    DamageReflectionComponent, StatusImmunityComponent,
)
from service.dungeon.components.aura_passive_components import (
    AuraBuffComponent, AuraDebuffComponent,
)

__all__ = [
    # 레지스트리
    "skill_component_register",
    "register_skill_with_tag",
    "get_component_by_tag",
    # 기본 클래스
    "SkillComponent",
    # 공격
    "DamageComponent", "LifestealComponent", "ConsumeComponent",
    # 지원
    "HealComponent", "ShieldComponent", "CleanseComponent",
    # 스탯
    "BuffComponent", "DebuffComponent", "PassiveBuffComponent",
    "PassiveRegenComponent", "ConditionalPassiveComponent",
    "TurnScalingComponent", "DebuffReductionComponent",
    # 특수
    "StatusComponent", "ComboComponent", "SummonComponent",
    "OnDeathReviveComponent", "OnDeathSummonComponent",
    # 방어 패시브
    "ElementImmunityComponent", "ElementResistanceComponent",
    "DamageReflectionComponent", "StatusImmunityComponent",
    # 오라 패시브
    "AuraBuffComponent", "AuraDebuffComponent",
]
