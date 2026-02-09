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
    SelfDamageComponent,
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
    DotComponent, ReviveComponent, SelfDestructComponent,
)
from service.dungeon.components.defensive_passive_components import (
    ElementImmunityComponent, ElementResistanceComponent,
    DamageReflectionComponent, StatusImmunityComponent,
)
from service.dungeon.components.aura_passive_components import (
    AuraBuffComponent, AuraDebuffComponent,
)
from service.dungeon.components.stat_behavior_components import (
    BonusStatComponent, CombatStatComponent,
    DefenseStatComponent, AccuracyStatComponent,
    ElementalDamageComponent,
)
from service.dungeon.components.modular_combat_components import (
    AttackComponent, CriticalComponent,
    PenetrationComponent, AccuracyBonusComponent,
)
from service.dungeon.components.equipment_passive_components import (
    OnAttackProcComponent, RaceBonusComponent, OnKillStackComponent,
)
from service.dungeon.components.skill_damage_components import (
    SkillDamageBoostComponent, SkillTypeDamageBoostComponent,
    AttributeDamageBoostComponent, ConditionalDamageBoostComponent,
)
from service.dungeon.components.cooldown_components import (
    CooldownReductionComponent, ManaCostReductionComponent,
    BuffDurationExtensionComponent, SkillUsageLimitComponent,
)
from service.dungeon.components.special_equipment_components import (
    RandomAttributeComponent, RandomDamageVarianceComponent,
    OnKillHealComponent, CombatStatGrowthComponent,
    ConditionalStatBonusComponent, SacrificeEffectComponent,
    FirstStrikeComponent, CounterAttackComponent,
    ExtraAttackComponent, RegenerationComponent,
    ReviveComponent as EquipmentReviveComponent,
    ThornsDamageComponent, ExplorationSpeedComponent,
    TrapDetectionComponent, EnhancementBonusComponent,
    DurabilityBonusComponent, SpecialDropBonusComponent,
    DungeonSpecificBuffComponent,
    HealBlockingComponent, ActionPredictionComponent,
    DamageDelayComponent, PeriodicInvincibilityComponent,
    AllyProtectionComponent,
)
from service.dungeon.components.bag_manipulation_components import (
    SkillRefreshComponent, SkillRerollComponent, DoubleDrawComponent,
)
from service.dungeon.components.resource_conversion_components import (
    HPCostEmpowerComponent, DefenseToAttackComponent,
)
from service.dungeon.components.skill_chain_components import (
    ConsecutiveSkillBonusComponent, SkillVarietyBonusComponent,
)
from service.dungeon.components.turn_based_components import (
    TurnCountEmpowerComponent, AccumulationComponent,
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
    "SelfDamageComponent",
    # 지원
    "HealComponent", "ShieldComponent", "CleanseComponent",
    # 스탯
    "BuffComponent", "DebuffComponent", "PassiveBuffComponent",
    "PassiveRegenComponent", "ConditionalPassiveComponent",
    "TurnScalingComponent", "DebuffReductionComponent",
    # 특수
    "StatusComponent", "ComboComponent", "SummonComponent",
    "OnDeathReviveComponent", "OnDeathSummonComponent",
    "DotComponent", "ReviveComponent", "SelfDestructComponent",
    # 방어 패시브
    "ElementImmunityComponent", "ElementResistanceComponent",
    "DamageReflectionComponent", "StatusImmunityComponent",
    # 오라 패시브
    "AuraBuffComponent", "AuraDebuffComponent",
    # 스탯 행동 (분리된 패시브)
    "BonusStatComponent", "CombatStatComponent",
    "DefenseStatComponent", "AccuracyStatComponent",
    "ElementalDamageComponent",
    # 모듈화된 전투 컴포넌트
    "AttackComponent", "CriticalComponent",
    "PenetrationComponent", "AccuracyBonusComponent",
    # 장비 전용 패시브
    "OnAttackProcComponent", "RaceBonusComponent", "OnKillStackComponent",
    # 스킬 데미지 강화 (장비)
    "SkillDamageBoostComponent", "SkillTypeDamageBoostComponent",
    "AttributeDamageBoostComponent", "ConditionalDamageBoostComponent",
    # 쿨다운 및 자원 관리 (장비)
    "CooldownReductionComponent", "ManaCostReductionComponent",
    "BuffDurationExtensionComponent", "SkillUsageLimitComponent",
    # 특수 장비 효과
    "RandomAttributeComponent", "RandomDamageVarianceComponent",
    "OnKillHealComponent", "CombatStatGrowthComponent",
    "ConditionalStatBonusComponent", "SacrificeEffectComponent",
    "FirstStrikeComponent", "CounterAttackComponent",
    "ExtraAttackComponent", "RegenerationComponent",
    "EquipmentReviveComponent",
    # 유틸리티 장비 효과
    "ThornsDamageComponent", "ExplorationSpeedComponent",
    "TrapDetectionComponent", "EnhancementBonusComponent",
    "DurabilityBonusComponent", "SpecialDropBonusComponent",
    "DungeonSpecificBuffComponent",
    # 고급 전투 효과
    "HealBlockingComponent", "ActionPredictionComponent",
    "DamageDelayComponent", "PeriodicInvincibilityComponent",
    "AllyProtectionComponent",
    # Bag 조작 (Bag 시스템 특화)
    "SkillRefreshComponent", "SkillRerollComponent", "DoubleDrawComponent",
    # 자원 변환 (HP/방어력 소모)
    "HPCostEmpowerComponent", "DefenseToAttackComponent",
    # 스킬 체인 & 콤보
    "ConsecutiveSkillBonusComponent", "SkillVarietyBonusComponent",
    # 턴 기반 효과
    "TurnCountEmpowerComponent", "AccumulationComponent",
]
