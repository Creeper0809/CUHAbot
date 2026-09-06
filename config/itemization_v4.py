"""Farming and buildcraft V4 itemization constants.

The definitions in this module are the authored source of truth.  Database
rows mirror them so auctions can filter affixes without interpreting JSON.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


FEATURE_FLAGS = {
    "itemization_v4": False,
    "farming_focus": False,
    "crafting_v4": False,
    "build_presets_v4": False,
    "set_effects_v4": False,
}

EQUIPMENT_STORAGE_BASE = 300
EQUIPMENT_STORAGE_MAX = 600
EQUIPMENT_STORAGE_STEP = 50
BUILD_PRESET_LIMIT = 10

AFFIX_COUNT_BY_GRADE = {1: 0, 2: 0, 3: 0, 4: 1, 5: 2, 6: 2, 7: 3, 8: 3}
AFFIX_TIERS_BY_GRADE = {
    4: (5, 4), 5: (4, 3), 6: (3, 2), 7: (2, 1), 8: (2, 1),
}
MYTHIC_T1_WEIGHT = 3.0
SALVAGE_ESSENCE = {1: 1, 2: 2, 3: 4, 4: 8, 5: 16, 6: 40, 7: 100, 8: 250}
REFORGE_ESSENCE = {4: 4, 5: 8, 6: 16, 7: 32, 8: 64}
PRESERVED_AFFIX_MULTIPLIER = {0: 1, 1: 3, 2: 9}
SOURCE_PROGRESS_THRESHOLDS = {"normal": 8, "elite": 10, "raid": 12}
TARGET_CRAFT_ESSENCE = 40
TARGET_CRAFT_GRADE = 4


@dataclass(frozen=True)
class AffixDefinition:
    id: str
    name: str
    family: str
    effect_group: str
    allowed_slots: tuple[str, ...]
    setup_tags: tuple[str, ...]
    payoff_tags: tuple[str, ...]
    runtime_key: str
    tier_values: dict[int, tuple[float, float]]
    weight: float = 1.0

    def runtime_config(self, value: float) -> dict[str, Any]:
        return {"components": [{"tag": "passive_buff", self.runtime_key: value}]}


OFFENSE = ("weapon", "sub_weapon", "gloves", "necklace", "ring1", "ring2")
DEFENSE = ("helmet", "armor", "gloves", "boots", "necklace", "ring1", "ring2", "sub_weapon")
ACCESSORY = ("boots", "necklace", "ring1", "ring2")
ALL_SLOTS = ("weapon", "sub_weapon", "helmet", "armor", "gloves", "boots", "necklace", "ring1", "ring2")


def _tiers(t5: float, t1: float) -> dict[int, tuple[float, float]]:
    step = (t1 - t5) / 5
    return {
        tier: (round(t5 + step * (5 - tier), 2), round(t5 + step * (6 - tier), 2))
        for tier in range(5, 0, -1)
    }


AFFIX_DEFINITIONS: tuple[AffixDefinition, ...] = (
    AffixDefinition("might", "완력", "offense", "attack", OFFENSE, (), ("physical",), "attack", _tiers(3, 18)),
    AffixDefinition("sorcery", "주술", "offense", "ap_attack", OFFENSE, (), ("magical",), "ap_attack", _tiers(3, 18)),
    AffixDefinition("precision", "정밀", "offense", "critical_rate", OFFENSE, (), ("critical",), "crit_rate", _tiers(1.5, 9)),
    AffixDefinition("brutality", "잔혹", "offense", "critical_damage", OFFENSE, (), ("critical",), "crit_damage", _tiers(5, 28)),
    AffixDefinition("sunder", "파쇄", "offense", "armor_penetration", OFFENSE, (), ("physical",), "armor_pen", _tiers(1.5, 10)),
    AffixDefinition("dispel", "해체", "offense", "magic_penetration", OFFENSE, (), ("magical",), "magic_pen", _tiers(1.5, 10)),
    AffixDefinition("vitality", "생명", "defense", "hp", DEFENSE, (), ("survival",), "hp_pct", _tiers(2, 12)),
    AffixDefinition("bulwark", "철벽", "defense", "ad_defense", DEFENSE, (), ("survival",), "ad_defense", _tiers(3, 20)),
    AffixDefinition("warding", "결계", "defense", "ap_defense", DEFENSE, (), ("survival",), "ap_defense", _tiers(3, 20)),
    AffixDefinition("restoration", "회복", "defense", "healing", DEFENSE, (), ("healing",), "healing_pct", _tiers(2, 12)),
    AffixDefinition("regeneration", "재생", "defense", "regeneration", DEFENSE, (), ("healing",), "regeneration_pct", _tiers(0.5, 3)),
    AffixDefinition("leech", "흡혈", "defense", "lifesteal", OFFENSE, (), ("sustain",), "lifesteal", _tiers(1, 6)),
    AffixDefinition("haste", "가속", "tempo", "speed", ACCESSORY, (), ("tempo",), "speed_pct", _tiers(1.5, 8)),
    AffixDefinition("first_move", "선제", "tempo", "first_strike", ACCESSORY, (), ("tempo",), "first_strike", _tiers(2, 12)),
    AffixDefinition("fortune", "행운", "exploration", "drop_rate", ACCESSORY, (), ("farming",), "drop_rate", _tiers(1, 8)),
    AffixDefinition("flame", "불씨", "element", "fire_damage", OFFENSE, ("ember", "burn"), ("burn",), "fire_damage_pct", _tiers(2, 12)),
    AffixDefinition("frost", "서리", "element", "ice_damage", OFFENSE, ("frost", "slow"), ("freeze", "shatter"), "ice_damage_pct", _tiers(2, 12)),
    AffixDefinition("storm", "전하", "element", "lightning_damage", OFFENSE, ("charge", "shock"), ("overload",), "lightning_damage_pct", _tiers(2, 12)),
    AffixDefinition("tide", "조류", "element", "water_damage", OFFENSE, ("tide", "wet"), ("flood", "erosion"), "water_damage_pct", _tiers(2, 12)),
    AffixDefinition("faith", "신념", "element", "holy_damage", OFFENSE, ("faith", "blessing"), ("judgment",), "holy_damage_pct", _tiers(2, 12)),
    AffixDefinition("soul", "영혼", "element", "dark_damage", OFFENSE, ("soul", "curse"), ("sacrifice",), "dark_damage_pct", _tiers(2, 12)),
    AffixDefinition("kindling", "발화", "setup", "burn_chance", OFFENSE, ("burn",), (), "burn_chance", _tiers(1, 7)),
    AffixDefinition("chill", "한기", "setup", "slow_chance", OFFENSE, ("slow",), (), "slow_chance", _tiers(1, 7)),
    AffixDefinition("static", "정전기", "setup", "shock_chance", OFFENSE, ("shock",), (), "shock_chance", _tiers(1, 7)),
)

AFFIX_BY_ID = {affix.id: affix for affix in AFFIX_DEFINITIONS}


def affix_count(grade: int) -> int:
    return AFFIX_COUNT_BY_GRADE.get(int(grade), 0)


def tier_range(grade: int) -> tuple[int, int] | None:
    return AFFIX_TIERS_BY_GRADE.get(int(grade))
