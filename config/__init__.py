"""
CUHABot 게임 설정 상수

모든 매직 넘버와 게임 밸런스 관련 상수를 여기서 관리합니다.
각 도메인별 설정은 config/ 하위 모듈에 정의되어 있습니다.
"""
from config.combat import CombatConfig, COMBAT
from config.damage import DamageConfig, DAMAGE
from config.attributes import (
    AttributeType, AttributeConfig, ATTRIBUTE,
    ATTRIBUTE_ADVANTAGE, ATTRIBUTE_DISADVANTAGE,
    get_attribute_multiplier,
)
from config.status_effects import StatusEffectConfig, STATUS_EFFECT
from config.user_stats import UserStatsConfig, USER_STATS, StatConversionConfig, STAT_CONVERSION
from config.dungeon import DungeonConfig, DUNGEON
from config.drops import (
    DropConfig, DROP,
    BoxRewardType, BoxRewardConfig, BoxConfig, BOX_CONFIGS,
)
from config.ui import EmbedColor, UIConfig, UI
from config.encounter import EncounterConfig, ENCOUNTER
from config.enhancement import EnhancementConfig, ENHANCEMENT
from config.skills import SKILL_DECK_SIZE, DEFAULT_SKILL_SLOT, SkillIdConfig, SKILL_ID
from config.shop import ShopConfig, SHOP, InventoryConfig, INVENTORY
from config.leveling import LEVELING_EXP_TABLE, LEVELING_EXP_DEFAULT
from config.synergies import SynergyTier, ATTRIBUTE_SYNERGIES, ComboSynergy, COMBO_SYNERGIES
from config.grade import (
    InstanceGrade, GradeInfo, GRADE_TABLE,
    GRADE_DROP_WEIGHTS, SpecialEffectDef, SPECIAL_EFFECT_POOL,
    get_grade_info, get_grade_name_map,
)
from config.multiplayer import (
    PartyConfig, PARTY,
    WeeklyTowerConfig, WEEKLY_TOWER,
    AuctionConfig, AUCTION,
)

__all__ = [
    # combat
    "CombatConfig", "COMBAT",
    # damage
    "DamageConfig", "DAMAGE",
    # attributes
    "AttributeType", "AttributeConfig", "ATTRIBUTE",
    "ATTRIBUTE_ADVANTAGE", "ATTRIBUTE_DISADVANTAGE",
    "get_attribute_multiplier",
    # status effects
    "StatusEffectConfig", "STATUS_EFFECT",
    # user stats
    "UserStatsConfig", "USER_STATS",
    "StatConversionConfig", "STAT_CONVERSION",
    # dungeon
    "DungeonConfig", "DUNGEON",
    # drops & boxes
    "DropConfig", "DROP",
    "BoxRewardType", "BoxRewardConfig", "BoxConfig", "BOX_CONFIGS",
    # ui
    "EmbedColor", "UIConfig", "UI",
    # encounter
    "EncounterConfig", "ENCOUNTER",
    # enhancement
    "EnhancementConfig", "ENHANCEMENT",
    # skills
    "SKILL_DECK_SIZE", "DEFAULT_SKILL_SLOT", "SkillIdConfig", "SKILL_ID",
    # shop & inventory
    "ShopConfig", "SHOP", "InventoryConfig", "INVENTORY",
    # leveling
    "LEVELING_EXP_TABLE", "LEVELING_EXP_DEFAULT",
    # synergies
    "SynergyTier", "ATTRIBUTE_SYNERGIES", "ComboSynergy", "COMBO_SYNERGIES",
    # multiplayer
    "PartyConfig", "PARTY",
    "WeeklyTowerConfig", "WEEKLY_TOWER",
    "AuctionConfig", "AUCTION",
    # grade
    "InstanceGrade", "GradeInfo", "GRADE_TABLE",
    "GRADE_DROP_WEIGHTS", "SpecialEffectDef", "SPECIAL_EFFECT_POOL",
    "get_grade_info", "get_grade_name_map",
]
