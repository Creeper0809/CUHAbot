"""Typed combat-stat and modifier normalization for Balance V2."""
from __future__ import annotations

from dataclasses import dataclass, fields
from typing import ClassVar, Mapping

from config import BALANCE_V2


@dataclass
class CombatStats:
    hp: float = 0.0
    attack: float = 0.0
    ap_attack: float = 0.0
    ad_defense: float = 0.0
    ap_defense: float = 0.0
    speed: float = 100.0
    accuracy: float = 95.0
    evasion: float = 5.0
    critical_rate: float = 5.0
    critical_damage: float = 150.0
    drop_rate: float = 0.0

    def finalize(self) -> "CombatStats":
        self.hp = round(max(1.0, self.hp))
        self.attack = round(max(0.0, self.attack))
        self.ap_attack = round(max(0.0, self.ap_attack))
        self.ad_defense = round(max(0.0, self.ad_defense))
        self.ap_defense = round(max(0.0, self.ap_defense))
        self.speed = round(max(0.0, self.speed))
        self.accuracy = round(self.accuracy)
        self.evasion = round(max(0.0, self.evasion))
        self.critical_rate = round(min(100 * BALANCE_V2.max_critical_rate, max(0.0, self.critical_rate)))
        self.critical_damage = round(min(100 * BALANCE_V2.max_critical_damage, max(100.0, self.critical_damage)))
        self.drop_rate = min(100 * BALANCE_V2.max_drop_bonus, max(0.0, self.drop_rate))
        return self


@dataclass
class ModifierBundle:
    hp: float = 0.0
    attack: float = 0.0
    ap_attack: float = 0.0
    ad_defense: float = 0.0
    ap_defense: float = 0.0
    speed: float = 0.0
    accuracy: float = 0.0
    evasion: float = 0.0
    critical_rate: float = 0.0
    critical_damage: float = 0.0
    drop_rate: float = 0.0

    hp_pct: float = 0.0
    attack_pct: float = 0.0
    ap_attack_pct: float = 0.0
    ad_defense_pct: float = 0.0
    ap_defense_pct: float = 0.0
    speed_pct: float = 0.0
    physical_damage_pct: float = 0.0
    magical_damage_pct: float = 0.0
    damage_taken_pct: float = 0.0
    healing_pct: float = 0.0
    regeneration_pct: float = 0.0
    lifesteal: float = 0.0
    armor_penetration: float = 0.0
    magic_penetration: float = 0.0
    all_resistance: float = 0.0
    fire_damage_pct: float = 0.0
    ice_damage_pct: float = 0.0
    water_damage_pct: float = 0.0
    lightning_damage_pct: float = 0.0
    holy_damage_pct: float = 0.0
    dark_damage_pct: float = 0.0
    burn_chance: float = 0.0
    slow_chance: float = 0.0
    shock_chance: float = 0.0
    first_strike: float = 0.0
    extra_action: float = 0.0
    dragon_bonus: float = 0.0

    RUNTIME_CONSUMERS: ClassVar[dict[str, str]] = {
        "hp": "equipment_stats", "attack": "equipment_stats",
        "ap_attack": "equipment_stats", "ad_defense": "equipment_stats",
        "ap_defense": "equipment_stats", "speed": "equipment_stats",
        "accuracy": "equipment_stats", "evasion": "equipment_stats",
        "critical_rate": "equipment_stats", "critical_damage": "equipment_stats",
        "drop_rate": "drop_rate", "hp_pct": "user_stats",
        "attack_pct": "user_stats", "ap_attack_pct": "user_stats",
        "ad_defense_pct": "user_stats", "ap_defense_pct": "user_stats",
        "speed_pct": "user_stats", "physical_damage_pct": "damage_component",
        "magical_damage_pct": "damage_component", "damage_taken_pct": "damage_pipeline",
        "healing_pct": "heal_component", "regeneration_pct": "turn_regeneration",
        "lifesteal": "damage_component", "armor_penetration": "damage_component",
        "magic_penetration": "damage_component", "all_resistance": "damage_pipeline",
        "fire_damage_pct": "damage_component", "water_damage_pct": "damage_component",
        "ice_damage_pct": "damage_component",
        "lightning_damage_pct": "damage_component", "holy_damage_pct": "damage_component",
        "dark_damage_pct": "damage_component", "burn_chance": "damage_status_proc",
        "slow_chance": "damage_status_proc", "shock_chance": "damage_status_proc",
        "first_strike": "combat_start", "extra_action": "action_gauge",
        "dragon_bonus": "damage_component",
    }

    _ALIASES = {
        "crit_rate": "critical_rate", "crit_damage": "critical_damage",
        "phys_dmg_pct": "physical_damage_pct", "mag_dmg_pct": "magical_damage_pct",
        "dmg_taken_pct": "damage_taken_pct",
        "heal_pct": "healing_pct", "regen_pct": "regeneration_pct",
        "armor_pen": "armor_penetration", "magic_pen": "magic_penetration",
        "fire_dmg_pct": "fire_damage_pct", "ice_dmg_pct": "ice_damage_pct", "water_dmg_pct": "water_damage_pct",
        "lightning_dmg_pct": "lightning_damage_pct", "holy_dmg_pct": "holy_damage_pct",
        "dark_dmg_pct": "dark_damage_pct",
    }
    _RATIO_FIELDS = {
        "hp_pct", "attack_pct", "ap_attack_pct", "ad_defense_pct", "ap_defense_pct",
        "speed_pct", "physical_damage_pct", "magical_damage_pct", "damage_taken_pct",
        "healing_pct", "regeneration_pct", "lifesteal", "armor_penetration",
        "magic_penetration", "all_resistance", "fire_damage_pct", "water_damage_pct",
        "ice_damage_pct", "lightning_damage_pct", "holy_damage_pct", "dark_damage_pct", "burn_chance",
        "slow_chance", "shock_chance", "first_strike", "extra_action", "dragon_bonus",
    }

    @classmethod
    def from_mapping(
        cls,
        values: Mapping[str, float],
        *,
        strict: bool = True,
        percentage_points: bool | None = None,
    ) -> "ModifierBundle":
        bundle = cls()
        valid = {entry.name for entry in fields(cls) if not entry.name.startswith("_")}
        for raw_key, raw_value in values.items():
            key = cls._ALIASES.get(raw_key, raw_key)
            if key not in valid:
                if strict:
                    raise ValueError(f"Unknown Balance V2 modifier key: {raw_key}")
                continue
            value = float(raw_value)
            if key in cls._RATIO_FIELDS:
                if percentage_points is True:
                    value /= 100.0
                elif percentage_points is None and abs(value) > 1.0:
                    value /= 100.0
            setattr(bundle, key, getattr(bundle, key) + value)
        bundle.armor_penetration = min(BALANCE_V2.max_penetration, bundle.armor_penetration)
        bundle.magic_penetration = min(BALANCE_V2.max_penetration, bundle.magic_penetration)
        bundle.all_resistance = min(BALANCE_V2.max_attribute_resistance, bundle.all_resistance)
        return bundle

    @classmethod
    def assert_runtime_consumers(cls, keys: set[str]) -> None:
        normalized = {cls._ALIASES.get(key, key) for key in keys}
        missing = sorted(normalized - set(cls.RUNTIME_CONSUMERS))
        if missing:
            raise ValueError(f"Balance V2 modifiers have no runtime consumer: {missing}")

    def merge(self, other: "ModifierBundle") -> "ModifierBundle":
        for entry in fields(self):
            if not entry.name.startswith("_"):
                setattr(self, entry.name, getattr(self, entry.name) + getattr(other, entry.name))
        self.armor_penetration = min(BALANCE_V2.max_penetration, self.armor_penetration)
        self.magic_penetration = min(BALANCE_V2.max_penetration, self.magic_penetration)
        self.all_resistance = min(BALANCE_V2.max_attribute_resistance, self.all_resistance)
        return self

    def apply(self, stats: CombatStats) -> CombatStats:
        for key in ("hp", "attack", "ap_attack", "ad_defense", "ap_defense", "speed"):
            setattr(stats, key, (getattr(stats, key) + getattr(self, key)) * (1.0 + getattr(self, f"{key}_pct")))
        stats.accuracy += self.accuracy
        stats.evasion += self.evasion
        stats.critical_rate += self.critical_rate
        stats.critical_damage += self.critical_damage
        stats.drop_rate += self.drop_rate
        return stats

    def as_runtime_dict(self) -> dict[str, float]:
        return {entry.name: getattr(self, entry.name) for entry in fields(self) if not entry.name.startswith("_")}
