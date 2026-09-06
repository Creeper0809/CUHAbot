"""Canonical CUHABot Balance V2 profile.

Runtime combat, data generation, documentation, and simulations must consume
this module instead of copying numeric constants into their own modules.
Percent values in this profile use ratios (``0.25`` means 25%) unless a helper
explicitly returns percentage points for a legacy model field.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import floor, sqrt
from typing import Mapping


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def round10(value: float) -> int:
    return int(round(value / 10.0) * 10)


@dataclass(frozen=True)
class BaseStats:
    hp: int
    attack: int
    ap_attack: int
    ad_defense: int
    ap_defense: int
    speed: int = 100
    accuracy: int = 95
    evasion: int = 5
    critical_rate: int = 5
    critical_damage: int = 150

    def as_dict(self) -> dict[str, int]:
        return {
            "hp": self.hp,
            "attack": self.attack,
            "ap_attack": self.ap_attack,
            "ad_defense": self.ad_defense,
            "ap_defense": self.ap_defense,
            "speed": self.speed,
            "accuracy": self.accuracy,
            "evasion": self.evasion,
            "critical_rate": self.critical_rate,
            "critical_damage": self.critical_damage,
        }


@dataclass(frozen=True)
class BalanceProfile:
    version: str = "V2"
    max_level: int = 100
    stat_points_per_level: int = 3

    grade_multipliers: Mapping[str, float] = None  # type: ignore[assignment]
    slot_budget_weights: Mapping[str, float] = None  # type: ignore[assignment]
    action_values: Mapping[str, float] = None  # type: ignore[assignment]
    healing_max_hp: Mapping[str, float] = None  # type: ignore[assignment]
    effect_budget_caps: Mapping[str, float] = None  # type: ignore[assignment]
    drop_weights: Mapping[str, tuple[float, ...]] = None  # type: ignore[assignment]

    defense_constant: float = 100.0
    max_defense_reduction: float = 0.70
    max_penetration: float = 0.50
    damage_variance: float = 0.08
    minimum_raw_damage_ratio: float = 0.05
    min_hit_rate: float = 0.75
    max_hit_rate: float = 0.98
    max_critical_rate: float = 0.70
    max_critical_damage: float = 2.50
    max_drop_bonus: float = 1.00
    max_attribute_resistance: float = 0.60

    monster_action_targets: Mapping[str, float] = None  # type: ignore[assignment]
    monster_incoming_fractions: Mapping[str, float] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        object.__setattr__(self, "grade_multipliers", {
            "D": 1.00, "C": 1.08, "B": 1.18, "A": 1.32,
            "S": 1.50, "SS": 1.72, "SSS": 1.98, "MYTHIC": 2.30,
        })
        object.__setattr__(self, "slot_budget_weights", {
            "weapon": 0.24, "sub_weapon": 0.12, "armor": 0.16,
            "helmet": 0.10, "gloves": 0.10, "boots": 0.10,
            "necklace": 0.08, "ring1": 0.05, "ring2": 0.05,
        })
        object.__setattr__(self, "action_values", {
            "D": 1.00, "C": 1.10, "B": 1.25, "A": 1.45,
            "S": 1.70, "SS": 2.00, "SSS": 2.35, "MYTHIC": 2.75,
        })
        object.__setattr__(self, "healing_max_hp", {
            "D": 0.12, "C": 0.15, "B": 0.18, "A": 0.22,
            "S": 0.27, "SS": 0.32, "SSS": 0.38, "MYTHIC": 0.45,
        })
        object.__setattr__(self, "effect_budget_caps", {
            "D": 0.00, "C": 0.00, "B": 0.00, "A": 0.03,
            "S": 0.06, "SS": 0.10, "SSS": 0.14, "MYTHIC": 0.18,
        })
        object.__setattr__(self, "drop_weights", {
            "normal": (45, 28, 16, 8, 2.5, 0.4, 0.09, 0.01),
            "elite": (20, 28, 24, 17, 8, 2.3, 0.6, 0.1),
            "boss": (5, 12, 22, 27, 20, 10, 3.5, 0.5),
        })
        object.__setattr__(self, "monster_action_targets", {
            "CommonMob": 2.5, "EliteMob": 5.0, "BossMob": 10.0,
        })
        object.__setattr__(self, "monster_incoming_fractions", {
            "CommonMob": 0.065, "EliteMob": 0.09, "BossMob": 0.15,
        })

    def base_stats(self, level: int) -> BaseStats:
        level = int(clamp(level, 1, self.max_level))
        over = max(0, level - 50)
        return BaseStats(
            hp=300 + 18 * (level - 1) + floor(0.20 * over ** 2),
            attack=15 + 2 * (level - 1) + floor(0.02 * over ** 2),
            ap_attack=15 + 2 * (level - 1) + floor(0.02 * over ** 2),
            ad_defense=8 + floor(1.05 * (level - 1)) + floor(0.012 * over ** 2),
            ap_defense=8 + floor(1.05 * (level - 1)) + floor(0.012 * over ** 2),
        )

    def equipment_budget(self, level: int) -> float:
        level = clamp(level, 1, self.max_level)
        return 80.0 + 4.2 * level + 0.02 * level ** 2

    def slot_budget(self, level: int, slot: str, grade: str = "D") -> float:
        return (
            self.equipment_budget(level)
            * self.slot_budget_weights[slot]
            * self.grade_multipliers[grade.upper()]
        )

    def action_rate(self, speed: float) -> float:
        return clamp(1.0 + (speed - 100.0) / 200.0, 0.75, 1.50)

    def hit_rate(self, accuracy: float, evasion: float) -> float:
        return clamp((accuracy - evasion) / 100.0, self.min_hit_rate, self.max_hit_rate)

    def defense_reduction(self, defense: float, penetration: float = 0.0) -> float:
        effective = max(0.0, defense) * (1.0 - clamp(penetration, 0.0, self.max_penetration))
        return min(self.max_defense_reduction, effective / (effective + self.defense_constant))

    def exp_to_next(self, level: int) -> int:
        return round10(100.0 * max(1, level) ** 1.4)

    def cumulative_exp(self, level: int) -> int:
        return sum(self.exp_to_next(current) for current in range(1, max(1, level)))

    def target_clears_per_level(self, level: int) -> float:
        if level <= 10:
            return 1.0
        if level <= 30:
            return 1.5
        if level <= 50:
            return 2.0
        if level <= 70:
            return 2.5
        if level <= 90:
            return 3.0
        return 4.0

    def dungeon_exp(self, level: int) -> int:
        return round10(self.exp_to_next(level) / self.target_clears_per_level(level))

    def dungeon_gold(self, level: int) -> int:
        return round10(80 + 8 * level + 0.5 * level ** 2)

    def equipment_purchase_price(self, level: int, slot: str) -> int:
        return round10(
            self.dungeon_gold(level) * 12 * self.slot_budget_weights[slot]
        )

    @staticmethod
    def shop_grade_floor(level: int) -> int:
        """Guaranteed grade for a level-appropriate equipment commission.

        The shop is the deterministic bad-luck backstop. SSS and Mythic stay
        drop-only; the floor advances one progression tier at a time.
        """
        if level >= 85:
            return 6  # SS
        if level >= 65:
            return 5  # S
        if level >= 45:
            return 4  # A
        if level >= 25:
            return 3  # B
        return 2  # C

    @staticmethod
    def skill_shop_price(grade_id: int) -> int:
        return {
            1: 100, 2: 300, 3: 800, 4: 2_000,
            5: 5_000, 6: 12_000, 7: 30_000, 8: 80_000,
        }[int(clamp(grade_id, 1, 8))]

    def party_hp_scale(self, members: int) -> float:
        return 1.0 + 0.75 * max(0, members - 1)

    def party_attack_scale(self, members: int) -> float:
        return 1.0 + 0.12 * max(0, members - 1)

    def party_reward_scale(self, members: int) -> float:
        return 1.0 + 0.65 * max(0, members - 1)

    def monster_incoming_fraction(self, kind: str, level: int) -> float:
        """Damage pressure scaled to the healing tier available at a level.

        Every result stays inside the approved common 6–9%, elite 9–13%,
        boss 12–16% windows. Higher tiers need the upper end because their
        support actions restore a much larger percentage of maximum HP.
        """
        band = (
            "C" if level <= 20 else "B" if level <= 40 else
            "A" if level <= 60 else "S" if level <= 80 else
            "SS" if level < 95 else "END"
        )
        by_kind = {
            "CommonMob": {"C": .060, "B": .086, "A": .063, "S": .070, "SS": .075, "END": .090},
            "EliteMob": {"C": .080, "B": .095, "A": .085, "S": .100, "SS": .105, "END": .130},
            "BossMob": {"C": .120, "B": .156, "A": .125, "S": .140, "SS": .145, "END": .160},
        }
        return by_kind.get(kind, {band: self.monster_incoming_fractions.get(kind, .065)})[band]

    def enhancement_stat_multiplier(self, enhancement_level: int) -> float:
        return 1.0 + 0.02 * int(clamp(enhancement_level, 0, 15))

    def enhancement_cost(self, item_level: int, grade: str, target_level: int) -> int:
        if target_level <= 3:
            coefficient = 0.08
        elif target_level <= 6:
            coefficient = 0.15
        elif target_level <= 9:
            coefficient = 0.30
        elif target_level <= 12:
            coefficient = 0.65
        else:
            coefficient = 1.40
        raw = self.dungeon_gold(item_level) * sqrt(self.grade_multipliers[grade.upper()]) * coefficient
        return max(10, round10(raw))

    @staticmethod
    def passive_stack_efficiency(index: int) -> float:
        if index <= 1:
            return 1.0
        if index == 2:
            return 0.75
        if index == 3:
            return 0.50
        return 0.25

    @staticmethod
    def set_budget_cap(piece_count: int) -> float:
        if piece_count >= 6:
            return 0.18
        if piece_count == 5:
            return 0.14
        if piece_count >= 3:
            return 0.10
        if piece_count == 2:
            return 0.06
        return 0.0


BALANCE_V2 = BalanceProfile()
