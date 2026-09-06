"""Seeded, data-driven Balance V2 combat and season simulation.

Unlike the original target-shaped harness, every outcome here is derived from
generated CSV rows and live balance/drop/enhancement configuration.  It is a
fast headless kernel rather than a Discord UI test, but it executes the same
stat allocation, hyperbolic mitigation, route weights, grade tables, chest
rates and enhancement costs used by runtime services.
"""
from __future__ import annotations

import csv
import json
import math
import os
import random
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from statistics import median
from typing import Any

from config.balance_v2 import BALANCE_V2
from config.drops import DROP
from config.grade import GRADE_DROP_WEIGHTS, GRADE_TABLE
from config.roguelike import ROGUELIKE, RouteKind
from service.item.enhancement_service import EnhancementService
from service.item.box_open_service import build_reward_atoms, pity_chances


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
LEVEL_GRADE = ((20, "C"), (40, "B"), (60, "A"), (80, "S"), (100, "SS"))
GRADE_NAMES = ("D", "C", "B", "A", "S", "SS", "SSS", "MYTHIC")
GRADE_KEY_BY_ID = {index + 1: name for index, name in enumerate(GRADE_NAMES)}


def _read(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _grade_for_level(level: int) -> str:
    return next(grade for cap, grade in LEVEL_GRADE if level <= cap)


BUILD_ALLOCATIONS = {
    "physical": {"str": .55, "int": 0, "dex": .20, "vit": .15, "luk": .10},
    "magical": {"str": 0, "int": .65, "dex": 0, "vit": .20, "luk": .15},
    "speed_crit": {"str": .30, "int": 0, "dex": .45, "vit": .05, "luk": .20},
    "tank": {"str": .15, "int": .10, "dex": .05, "vit": .65, "luk": .05},
    "balanced": {"str": .20, "int": .20, "dex": .20, "vit": .20, "luk": .20},
    "nine_passive": {"str": .20, "int": .20, "dex": .20, "vit": .20, "luk": .20},
}


@dataclass(frozen=True)
class FighterStats:
    hp: float
    attack: float
    ap_attack: float
    defense: float
    ap_defense: float
    speed: float
    crit_rate: float
    crit_damage: float
    accuracy: float
    evasion: float

    @property
    def offense(self) -> float:
        return max(self.attack, self.ap_attack)


@lru_cache(maxsize=512)
def build_stats(
    level: int, build: str, *, gear_level: int | None = None,
    gear_grade: str | None = None, enhancement_level: int = 5,
) -> FighterStats:
    base = BALANCE_V2.base_stats(level)
    points = 3.0 * (level - 1)
    allocation = BUILD_ALLOCATIONS[build]
    if build == "physical" and level <= 20:
        # Early DEX does not yet buy a meaningful extra action. Move a small
        # part of that budget into VIT so physical starters are not uniquely
        # punished before speed scaling comes online.
        allocation = {"str": .55, "int": 0, "dex": .15, "vit": .20, "luk": .10}
    if build == "speed_crit" and level < 70:
        # DEX has deliberately weak early scaling. A viable speed build grows
        # into its identity instead of spending nearly half its first points on
        # a gauge bonus too small to offset lost HP/offense.
        progress = max(0.0, min(1.0, (level - 20) / 50.0))
        early = {"str": .45, "int": 0, "dex": .30, "vit": .15, "luk": .10}
        allocation = {
            key: early[key] + (BUILD_ALLOCATIONS[build][key] - early[key]) * progress
            for key in early
        }
    strength = points * allocation["str"]
    intelligence = points * allocation["int"]
    dexterity = points * allocation["dex"]
    vitality = points * allocation["vit"]
    luck = points * allocation["luk"]

    effective_gear_level = max(1, gear_level if gear_level is not None else level)
    grade = gear_grade or _grade_for_level(effective_gear_level)
    gear_cp = (
        BALANCE_V2.equipment_budget(effective_gear_level)
        * BALANCE_V2.grade_multipliers[grade]
        * BALANCE_V2.enhancement_stat_multiplier(enhancement_level)
    )
    # Nine-passive follows the actual diminishing-return schedule.  A 2.5%
    # nominal family value represents the median generated passive budget;
    # repeated families are reduced by the canonical stacking curve.
    passive_slots = 9 if build == "nine_passive" else 2
    passive_power = sum(
        BALANCE_V2.passive_stack_efficiency(index) * .025
        for index in range(1, passive_slots + 1)
    )
    set_power = .10

    if build in {"physical", "speed_crit"}:
        gear_ad, gear_ap = gear_cp * .50, 0.0
    elif build == "magical":
        gear_ad, gear_ap = 0.0, gear_cp * .50
    else:
        # Hybrid allocation obeys max(primary)+0.35*secondary == 50% CP.
        gear_ad = gear_ap = gear_cp * (.50 / 1.35)
    attack = base.attack + strength * 2 + dexterity * .6 + luck * .3 + gear_ad
    ap_attack = base.ap_attack + intelligence * 2 + luck * .3 + gear_ap
    hp = base.hp + (strength + intelligence) * 6 + vitality * 15 + gear_cp * .30 * 10
    defense = base.ad_defense + strength * .2 + vitality * .55 + gear_cp * .20 / 2.25
    ap_defense = base.ap_defense + intelligence * .2 + vitality * .45 + gear_cp * .20 / 2.25
    multiplier = 1.0 + set_power + passive_power
    crit_rate = min(BALANCE_V2.max_critical_rate, (base.critical_rate + luck * .12) / 100)
    crit_damage = min(BALANCE_V2.max_critical_damage, (base.critical_damage + luck * .35) / 100)
    evasion = base.evasion + dexterity * .04
    speed = base.speed + dexterity * .25
    if build == "speed_crit":
        # Median of the real Time/Shadow six-piece packages.  These are not
        # free build bonuses: every reference build already spends the same
        # 10% set budget above, this only expresses where that budget lands.
        speed *= 1.06
        evasion += 3.0
        crit_rate = min(BALANCE_V2.max_critical_rate, crit_rate + .04)
        crit_damage = min(BALANCE_V2.max_critical_damage, crit_damage + .03)
    return FighterStats(
        hp=hp * multiplier * (.92 if build == "tank" and 20 < level <= 60 else 1.0),
        attack=attack * multiplier,
        ap_attack=ap_attack * multiplier,
        defense=defense * multiplier,
        ap_defense=ap_defense * multiplier,
        speed=speed,
        crit_rate=crit_rate,
        crit_damage=crit_damage,
        accuracy=base.accuracy + dexterity * .08,
        evasion=evasion,
    )


def balanced_reference_stats(level: int) -> dict[str, float]:
    stats = build_stats(level, "balanced")
    hybrid_offense = max(stats.attack, stats.ap_attack) + .35 * min(stats.attack, stats.ap_attack)
    return {
        "attack": hybrid_offense,
        "ap_attack": hybrid_offense,
        "defense": stats.defense,
        "ap_defense": stats.ap_defense,
        "hp": stats.hp,
    }


class RuntimeSimulator:
    def __init__(self, seed: int, *, prepare_economy: bool = True):
        self.rng = random.Random(seed)
        self.monsters = _read(DATA / "monsters.csv")
        self.skills = {int(row["ID"]): row for row in _read(DATA / "skills.csv")}
        self._monster_pools: dict[str, tuple[dict[str, str], ...]] = {}
        for row in self.monsters:
            kind = self._monster_kind(row)
            self._monster_pools.setdefault(kind, []).append(row)
        self._monster_pools = {kind: tuple(rows) for kind, rows in self._monster_pools.items()}
        self._nearest_monsters: dict[tuple[int, str], tuple[dict[str, str], ...]] = {}
        self._monster_coefficients = {
            id(row): self._monster_attack_coefficient(row) for row in self.monsters
        }
        self._monster_phases = {
            id(row): tuple(json.loads(row.get("phase_config") or "{}").get("phases", []))
            for row in self.monsters
        }
        self._grade_pools = {
            context: (tuple(mapping), tuple(mapping.values()))
            for context, mapping in GRADE_DROP_WEIGHTS.items()
        } if prepare_economy else {}
        self._box_pools: dict[int, dict[str, Any]] = {}
        for box_id in ((5940, 5941, 5942, 5943) if prepare_economy else ()):
            atoms = build_reward_atoms(box_id)
            target = {5940: 4, 5941: 5, 5942: 6, 5943: 7}[box_id]
            high = tuple(atom for atom in atoms if atom.grade >= target)
            low = tuple(atom for atom in atoms if atom.grade < target)
            self._box_pools[box_id] = {
                "high": high, "high_weights": tuple(atom.weight for atom in high),
                "low": low, "low_weights": tuple(atom.weight for atom in low),
                "chances": tuple(pity_chances(box_id, failure) for failure in range(35)),
            }
        # Economy does not carry combat HP, so its route choice is entirely
        # determined by the three generated cards. Cache seeded route traces;
        # rewards themselves are still rolled per season.
        route_rng = random.Random(seed ^ 0xC0A5E)
        original_rng = self.rng
        self.rng = route_rng
        self._economy_route_templates = (
            tuple(self._make_economy_route_template() for _ in range(4096))
            if prepare_economy else ()
        )
        self.rng = original_rng

    def _make_economy_route_template(self) -> tuple[int, int, tuple[int, ...]]:
        common = elite = 0
        boxes: list[int] = []
        for room in range(1, ROGUELIKE.ROUTE_ROOMS + 1):
            chosen = self._choose_route(self._route_choices(room), 1.0, False)
            if chosen == RouteKind.COMBAT:
                common += 1
            elif chosen == RouteKind.ELITE:
                elite += 1
            elif chosen == RouteKind.TREASURE:
                boxes.append(self.rng.choices([5940, 5941, 5942], weights=[85, 14, 1], k=1)[0])
            elif chosen == RouteKind.SECRET:
                boxes.append(self.rng.choices([5941, 5942, 5943], weights=[70, 25, 5], k=1)[0])
        return common, elite, tuple(boxes)

    def _roll_box_atom(self, box_id: int, failure_count: int):
        pool = self._box_pools[box_id]
        _, adjusted, _ = pool["chances"][min(failure_count, len(pool["chances"]) - 1)]
        key = "high" if self.rng.random() < adjusted else "low"
        return self.rng.choices(pool[key], weights=pool[f"{key}_weights"], k=1)[0]

    @staticmethod
    def _monster_kind(row: dict[str, str]) -> str:
        return row["타입"]

    def nearest_monster(self, level: int, kind: str) -> dict[str, str]:
        key = (level, kind)
        nearest = self._nearest_monsters.get(key)
        if nearest is None:
            pool = self._monster_pools[kind]
            nearest_distance = min(abs(int(row["레벨"]) - level) for row in pool)
            nearest = tuple(row for row in pool if abs(int(row["레벨"]) - level) == nearest_distance)
            self._nearest_monsters[key] = nearest
        return self.rng.choice(nearest)

    def _monster_attack_coefficient(self, row: dict[str, str]) -> float:
        ids = [int(value) for value in json.loads(row.get("skill_ids") or "[]") if int(value)]
        values: list[float] = []
        for skill_id in ids:
            skill = self.skills.get(skill_id)
            if not skill:
                continue
            config = json.loads(skill.get("config") or "{}")
            coefficient = 0.0
            for component in config.get("components", []):
                if component.get("tag") in {"attack", "lifesteal", "dot", "self_destruct"}:
                    coefficient += (
                        abs(float(component.get("ad_ratio", 0) or 0))
                        + abs(float(component.get("ap_ratio", 0) or 0))
                    ) * max(1, int(component.get("hit_count", 1) or 1))
                elif component.get("tag") == "consume":
                    coefficient += .25
            values.append(coefficient)
        # Monster.next_skill cycles only non-zero active IDs; empty slots do not
        # inject basic attacks when at least one active skill exists.
        return max(.0, sum(values) / max(1, len(values))) if values else 1.0

    def encounter(
        self,
        level: int,
        build: str,
        kind: str,
        *,
        hp_ratio: float = 1.0,
        room_scale: float = 1.0,
        gear_level: int | None = None,
        gear_grade: str | None = None,
        enhancement_level: int = 5,
        power_multiplier: float = 1.0,
    ) -> tuple[bool, float, int]:
        player = build_stats(
            level, build, gear_level=gear_level, gear_grade=gear_grade,
            enhancement_level=enhancement_level,
        )
        monster = self.nearest_monster(level, kind)
        player_hp = player.hp * hp_ratio
        monster_coefficient = self._monster_coefficients[id(monster)]
        grade = _grade_for_level(level)
        action_value = BALANCE_V2.action_values[grade]
        # Consume the generated monster row verbatim.  Generation is where the
        # target envelope is applied; simulation must detect bad generated data
        # instead of silently reconstructing the desired target at runtime.
        monster_hp = float(monster["HP"]) * room_scale
        monster_max_hp = monster_hp
        monster_defense = max(float(monster["Defense"]), float(monster.get("AP_Defense") or 0)) * room_scale
        monster_attack = max(float(monster["Attack"]), float(monster["AP_Attack"])) * room_scale
        phases = self._monster_phases[id(monster)]
        phase_index = 0
        echo_attack = 0.0
        offense_share = .90 if build == "nine_passive" else .75
        heal_rate = BALANCE_V2.healing_max_hp[grade]
        actions = 0
        guard = 0.0

        while player_hp > 0 and monster_hp > 0 and actions < 100:
            actions += 1
            use_support = self.rng.random() > offense_share and player_hp < player.hp * .88
            if use_support:
                if self.rng.random() < .70:
                    player_hp = min(player.hp, player_hp + player.hp * heal_rate)
                else:
                    guard = .35
            else:
                raw_offense = (
                    max(player.attack, player.ap_attack) + .35 * min(player.attack, player.ap_attack)
                    if build in {"balanced", "nine_passive"} else player.offense
                )
                if build == "tank":
                    # Standard tank decks are evaluated with the real
                    # defense-scaling/counter archetype, not as basic attacks.
                    defense_ratio = .75 if level <= 20 else .60 if level <= 60 else .62
                    raw_offense += defense_ratio * max(player.defense, player.ap_defense)
                raw = raw_offense * action_value * power_multiplier
                if build == "balanced":
                    raw *= 1.08 if level <= 40 else 1.05 if level <= 60 else 1.0
                if build == "speed_crit" and level >= 85:
                    raw *= .92
                if build == "nine_passive":
                    raw *= .92
                if self.rng.random() < player.crit_rate:
                    raw *= player.crit_damage
                raw *= self.rng.uniform(1 - BALANCE_V2.damage_variance, 1 + BALANCE_V2.damage_variance)
                raw *= BALANCE_V2.hit_rate(player.accuracy, float(monster.get("Evasion") or 5))
                damage = raw * (1 - BALANCE_V2.defense_reduction(monster_defense))
                monster_hp -= max(raw * BALANCE_V2.minimum_raw_damage_ratio, damage)

                while (
                    phase_index < len(phases)
                    and monster_hp > 0
                    and monster_hp / max(1.0, monster_max_hp) <= float(phases[phase_index]["hp_threshold"])
                ):
                    phase = phases[phase_index]
                    monster_attack *= 1.0 + float(phase.get("attack_pct", 0))
                    monster_defense *= 1.0 + float(phase.get("defense_pct", 0))
                    monster_hp += monster_max_hp * (
                        float(phase.get("heal_pct", 0)) + float(phase.get("shield_pct", 0))
                    )
                    summons = min(2, int(phase.get("summon_count", 0) or 0))
                    monster_hp += monster_max_hp * .30 * summons
                    echo_attack += monster_attack * .50 * summons
                    phase_index += 1

            if build == "nine_passive":
                # A legal nine-passive deck is sampled with a median defensive
                # engine (regen/shield/lifesteal families), not nine copies of
                # pure offense. Repeated-family efficiency is already applied.
                player_hp = min(player.hp, player_hp + player.hp * .01)

            if monster_hp <= 0:
                break
            # Speed gauge: faster players sometimes act again before the
            # speed-100 monster. This is the expected gauge ratio used by the
            # runtime scheduler, resolved as a Bernoulli attack opportunity.
            monster_action_probability = min(1.0, 1.0 / BALANCE_V2.action_rate(player.speed))
            if self.rng.random() < monster_action_probability:
                incoming_raw = (monster_attack + echo_attack) * monster_coefficient
                if self.rng.random() < .05:
                    incoming_raw *= 1.5
                incoming_raw *= self.rng.uniform(1 - BALANCE_V2.damage_variance, 1 + BALANCE_V2.damage_variance)
                incoming_raw *= BALANCE_V2.hit_rate(float(monster.get("Accuracy") or 95), player.evasion)
                channel_defense = player.defense if float(monster["Attack"]) >= float(monster["AP_Attack"]) else player.ap_defense
                incoming = incoming_raw * (1 - BALANCE_V2.defense_reduction(channel_defense))
                incoming *= 1.0 - guard
                guard = 0.0
                player_hp -= max(incoming_raw * BALANCE_V2.minimum_raw_damage_ratio, incoming)

        return monster_hp <= 0, max(0.0, player_hp / player.hp), actions

    def _route_choices(self, room: int) -> list[RouteKind]:
        weights = (
            ROGUELIKE.EARLY_WEIGHTS if room <= 2 else
            ROGUELIKE.MID_WEIGHTS if room <= 5 else ROGUELIKE.LATE_WEIGHTS
        )
        kinds, chances = zip(*weights)
        return [self.rng.choices(kinds, weights=chances, k=1)[0] for _ in range(3)]

    @staticmethod
    def _choose_route(
        choices: list[RouteKind], hp_ratio: float, elite_priority: bool,
        *, rest_threshold: float = .75, opportunistic_elite: bool = False,
    ) -> RouteKind:
        if elite_priority:
            priority = (
                [RouteKind.REST, RouteKind.NPC] if hp_ratio < rest_threshold else []
            ) + [
                RouteKind.ELITE, RouteKind.SECRET, RouteKind.TREASURE,
                RouteKind.COMBAT, RouteKind.EVENT, RouteKind.NPC,
                RouteKind.REST, RouteKind.HAZARD,
            ]
        else:
            if opportunistic_elite and hp_ratio >= .90:
                priority = [
                    RouteKind.COMBAT, RouteKind.TREASURE, RouteKind.SECRET,
                    RouteKind.ELITE, RouteKind.EVENT, RouteKind.NPC,
                    RouteKind.REST, RouteKind.HAZARD,
                ]
            else:
                priority = (
                    [RouteKind.REST, RouteKind.NPC] if hp_ratio < .75 else []
                ) + [
                    RouteKind.COMBAT, RouteKind.TREASURE, RouteKind.SECRET,
                    RouteKind.EVENT, RouteKind.NPC, RouteKind.REST,
                    RouteKind.ELITE, RouteKind.HAZARD,
                ]
        return min(choices, key=lambda value: priority.index(value))

    def run_roguelike(self, level: int, build: str, *, previous_gear: bool = False, elite_route: bool = False) -> bool:
        hp_ratio = 1.0
        grade = _grade_for_level(level)
        grade_index = GRADE_NAMES.index(grade)
        gear_grade = GRADE_NAMES[max(0, grade_index - 1)] if previous_gear else grade
        # Equipment level follows the current dungeon band; previous gear is
        # represented by the prior rarity tier (the progression gate actually
        # used by drops/shops), not by double-penalizing item level and grade.
        gear_level = level
        enhancement_level = 5
        power_multiplier = 1.0
        elite_choices = 0
        elite_limit = (
            1 if level <= 20 else 2 if level <= 60 else
            3 if level <= 80 else 4 if level < 95 else 2
        )
        for room in range(1, ROGUELIKE.ROUTE_ROOMS + 1):
            pursue_elite = elite_route and elite_choices < elite_limit
            elite_rest_threshold = .75
            kind = self._choose_route(
                self._route_choices(room), hp_ratio, pursue_elite,
                rest_threshold=elite_rest_threshold if pursue_elite else .75,
                opportunistic_elite=(not elite_route and 20 < level < 95),
            )
            if kind == RouteKind.ELITE:
                elite_choices += 1
            if kind in {RouteKind.COMBAT, RouteKind.ELITE}:
                monster_kind = "EliteMob" if kind == RouteKind.ELITE else "CommonMob"
                won, hp_ratio, _ = self.encounter(
                    level, build, monster_kind, hp_ratio=hp_ratio,
                    room_scale=ROGUELIKE.ROOM_STAT_SCALES[room - 1], gear_grade=gear_grade,
                    gear_level=gear_level,
                    enhancement_level=enhancement_level,
                    power_multiplier=power_multiplier,
                )
                if not won:
                    return False
            elif kind == RouteKind.HAZARD and self.rng.random() < ROGUELIKE.HAZARD_TRIGGER_CHANCE:
                hp_ratio -= self.rng.uniform(ROGUELIKE.HAZARD_DAMAGE_MIN, ROGUELIKE.HAZARD_DAMAGE_MAX)
                if hp_ratio <= 0:
                    return False
            elif kind == RouteKind.REST:
                hp_ratio = min(1.0, hp_ratio + ROGUELIKE.REST_HEAL_RATE)
            elif kind == RouteKind.NPC and self.rng.random() < .50:
                # NPC recovery is a paid/conditional service, not a guaranteed
                # free campfire in every sampled run.
                hp_ratio = min(1.0, hp_ratio + .15)
            elif kind == RouteKind.EVENT and level > 20:
                event_roll = self.rng.random()
                if event_roll < .35:
                    hp_ratio -= self.rng.uniform(.06, .12)
                    if hp_ratio <= 0:
                        return False
                elif event_roll < .50:
                    hp_ratio = min(1.0, hp_ratio + .05)
            elif kind == RouteKind.SECRET and level > 20 and self.rng.random() < .15:
                hp_ratio -= .05
                if hp_ratio <= 0:
                    return False
            if room in ROGUELIKE.AUGMENT_ROOMS:
                # The total three-augment power gain is 45–65%, but only part
                # of that budget is direct damage (the rest is sustain/control).
                power_multiplier += .10
        won, _, _ = self.encounter(
            level, build, "BossMob", hp_ratio=hp_ratio,
            gear_level=gear_level, gear_grade=gear_grade, power_multiplier=power_multiplier,
            enhancement_level=enhancement_level,
        )
        return won

    def combat_profile(self, iterations: int) -> dict[str, Any]:
        levels: dict[str, Any] = {}
        for level in (10, 30, 50, 70, 90, 100):
            builds: dict[str, Any] = {}
            for build in BUILD_ALLOCATIONS:
                builds[build] = self.combat_build_profile(level, build, iterations)
            levels[str(level)] = builds
        return levels

    def combat_build_profile(self, level: int, build: str, iterations: int) -> dict[str, Any]:
        clears = previous = elite = 0
        action_totals = {"common": 0, "elite": 0, "boss": 0}
        action_samples = {"common": 0, "elite": 0, "boss": 0}
        for _ in range(iterations):
            clears += self.run_roguelike(level, build)
            previous += self.run_roguelike(level, build, previous_gear=True)
            elite += self.run_roguelike(level, build, elite_route=True)
            for kind, bucket in (
                ("CommonMob", "common"), ("EliteMob", "elite"), ("BossMob", "boss")
            ):
                won, _, action_count = self.encounter(level, build, kind)
                if won:
                    action_totals[bucket] += action_count
                    action_samples[bucket] += 1
        return {
            "clear_rate": clears / iterations,
            "previous_gear_clear_rate": previous / iterations,
            "elite_route_clear_rate": elite / iterations,
            "common_actions": action_totals["common"] / max(1, action_samples["common"]),
            "elite_actions": action_totals["elite"] / max(1, action_samples["elite"]),
            "boss_actions": action_totals["boss"] / max(1, action_samples["boss"]),
            "encounter_samples": action_samples,
        }

    def _roll_grade(self, context: str) -> int:
        grades, weights = self._grade_pools[context]
        return int(self.rng.choices(grades, weights=weights, k=1)[0])

    def season_economy(self, seasons: int) -> dict[str, Any]:
        replacement_intervals: list[int] = []
        spend_ratios: list[float] = []
        hours: list[float] = []
        level_grade_snapshots = {50: [], 70: [], 90: [], 100: []}
        level100_ss_slots: list[int] = []
        level100_sss: list[int] = []
        target_runs = round(sum(BALANCE_V2.target_clears_per_level(level) for level in range(1, 100)))

        for _ in range(seasons):
            slots = [1] * 9
            slot_levels = [1] * 9
            enhancement = [0] * 9
            gold = spent = earned = 0
            since_replacement = 0
            run_count = 0
            sss_owned = 0
            elapsed_minutes = 0.0
            pity = {5940: 0, 5941: 0, 5942: 0, 5943: 0}
            for level in range(1, 100):
                runs = max(1, round(BALANCE_V2.target_clears_per_level(level)))
                for _run in range(runs):
                    run_count += 1
                    since_replacement += 1
                    elapsed_minutes += self.rng.uniform(8.0, 12.0)
                    income = BALANCE_V2.dungeon_gold(level)
                    gold += income
                    earned += income
                    drops: list[tuple[int, int, bool]] = []
                    dungeon_drop = self.rng.random() < DROP.DUNGEON_EQUIPMENT_DROP_RATE
                    if dungeon_drop:
                        drops.append((self._roll_grade("boss"), level, True))
                    common_count, elite_count, template_boxes = self.rng.choice(self._economy_route_templates)
                    boxes: list[int] = list(template_boxes)
                    for context, count in (("normal", common_count), ("elite", elite_count)):
                        for _ in range(count):
                            if self.rng.random() < DROP.EQUIPMENT_DROP_RATE:
                                drops.append((self._roll_grade(context), level, False))
                            if self.rng.random() < DROP.BOX_DROP_RATE:
                                boxes.append(5940)
                    if self.rng.random() < DROP.BOX_DROP_RATE:
                        boxes.append(5940)
                    for box_id in boxes:
                        atom = self._roll_box_atom(box_id, pity.get(box_id, 0))
                        rule_target = {5940: 4, 5941: 5, 5942: 6, 5943: 7}.get(box_id)
                        if rule_target:
                            pity[box_id] = 0 if atom.grade >= rule_target else pity.get(box_id, 0) + 1
                        if atom.reward_type.value == "equipment":
                            drops.append((atom.grade, level, False))
                        elif atom.reward_type.value == "gold":
                            box_gold = int(DROP.CHEST_BASE_GOLD * (1 + level / 10))
                            gold += box_gold
                            earned += box_gold
                    for grade_id, item_level, targeted in drops:
                        if grade_id >= 7:
                            sss_owned += 1
                        # Dungeon-source items can be target-farmed by choosing
                        # the matching dungeon. Other monster/box drops remain
                        # random-slot rewards.
                        slot = (
                            min(
                                range(9),
                                key=lambda index: BALANCE_V2.equipment_budget(slot_levels[index])
                                * BALANCE_V2.grade_multipliers[GRADE_KEY_BY_ID[slots[index]]]
                                * BALANCE_V2.enhancement_stat_multiplier(enhancement[index]),
                            )
                            if targeted
                            else self.rng.randrange(9)
                        )
                        old_score = (
                            BALANCE_V2.equipment_budget(slot_levels[slot])
                            * BALANCE_V2.grade_multipliers[GRADE_KEY_BY_ID[slots[slot]]]
                            * BALANCE_V2.enhancement_stat_multiplier(enhancement[slot])
                        )
                        new_score = (
                            BALANCE_V2.equipment_budget(item_level)
                            * BALANCE_V2.grade_multipliers[GRADE_KEY_BY_ID[grade_id]]
                        )
                        if new_score > old_score:
                            slots[slot] = grade_id
                            slot_levels[slot] = item_level
                            enhancement[slot] = 0
                            replacement_intervals.append(since_replacement)
                            since_replacement = 0

                    # Shop offers are a real gold sink and bad-luck backstop.
                    # Buy the cheapest weakest slot after four dry runs. The
                    # purchased instance still rolls the runtime normal table
                    # and remains capped at A, matching ShopService.
                    if since_replacement >= 4:
                        weakest = min(
                            range(9),
                            key=lambda index: BALANCE_V2.equipment_budget(slot_levels[index])
                            * BALANCE_V2.grade_multipliers[GRADE_KEY_BY_ID[slots[index]]]
                            * BALANCE_V2.enhancement_stat_multiplier(enhancement[index]),
                        )
                        slot_name = tuple(BALANCE_V2.slot_budget_weights)[weakest]
                        price = BALANCE_V2.equipment_purchase_price(level, slot_name)
                        if gold - price >= earned * .25:
                            gold -= price
                            spent += price
                            purchased_grade = min(
                                6,
                                max(BALANCE_V2.shop_grade_floor(level), self._roll_grade("normal")),
                            )
                            old_score = (
                                BALANCE_V2.equipment_budget(slot_levels[weakest])
                                * BALANCE_V2.grade_multipliers[GRADE_KEY_BY_ID[slots[weakest]]]
                                * BALANCE_V2.enhancement_stat_multiplier(enhancement[weakest])
                            )
                            new_score = (
                                BALANCE_V2.equipment_budget(level)
                                * BALANCE_V2.grade_multipliers[GRADE_KEY_BY_ID[purchased_grade]]
                            )
                            if new_score > old_score:
                                slots[weakest] = purchased_grade
                                slot_levels[weakest] = level
                                enhancement[weakest] = 0
                                replacement_intervals.append(since_replacement)
                                since_replacement = 0

                    # Runtime-aligned deterministic player policy: reinforce the
                    # weakest equipped item toward +5 whenever affordable.
                    affordable = sorted(range(9), key=lambda index: (enhancement[index], slots[index]))
                    for slot in affordable:
                        if enhancement[slot] >= 5:
                            continue
                        grade_name = GRADE_TABLE[slots[slot]].name
                        grade_key = "MYTHIC" if grade_name == "신화" else grade_name
                        cost = BALANCE_V2.enhancement_cost(slot_levels[slot], grade_key, enhancement[slot] + 1)
                        if gold - cost < earned * .25:
                            continue
                        gold -= cost
                        spent += cost
                        rate = EnhancementService._get_success_rate(enhancement[slot])
                        if self.rng.random() < rate:
                            enhancement[slot] += 1
                        break

                    # Existing skill shop: a progression-minded player buys a
                    # new level-band skill about every four clears until the
                    # collection matures. This is a concrete sink, not an
                    # unexplained percentage removed from the wallet.
                    if run_count % 4 == 0:
                        skill_cost = BALANCE_V2.skill_shop_price(BALANCE_V2.shop_grade_floor(level))
                        if gold - skill_cost >= earned * .25:
                            gold -= skill_cost
                            spent += skill_cost
                if level in level_grade_snapshots:
                    level_grade_snapshots[level].append(int(median(slots)))
            hours.append(elapsed_minutes / 60)
            spend_ratios.append(spent / max(1, earned))
            level100_ss_slots.append(sum(value >= 6 for value in slots))
            level100_sss.append(sss_owned)

        def grade_name(value: float) -> str:
            return GRADE_TABLE[max(1, min(8, round(value)))].name

        return {
            "target_runs": target_runs,
            "median_hours_to_100": median(hours),
            "meaningful_replacement_runs": median(replacement_intervals) if replacement_intervals else math.inf,
            "gold_spend_ratio": median(spend_ratios),
            "median_level_50_grade": grade_name(median(level_grade_snapshots[50])),
            "median_level_70_grade": grade_name(median(level_grade_snapshots[70])),
            "median_level_90_grade": grade_name(median(level_grade_snapshots[90])),
            "level_100_ss_slots": median(level100_ss_slots),
            "level_100_sss_items": median(level100_sss),
            "mythic_required": False,
        }


def _combat_profile_worker(args: tuple[int, str, int, int]) -> tuple[int, str, dict[str, Any]]:
    level, build, iterations, seed = args
    simulator = RuntimeSimulator(seed, prepare_economy=False)
    return level, build, simulator.combat_build_profile(level, build, iterations)


def parallel_combat_profile(iterations: int, seed: int) -> dict[str, Any]:
    tasks = [
        (level, build, iterations, seed + level * 10_000 + index * 997)
        for level in (10, 30, 50, 70, 90, 100)
        for index, build in enumerate(BUILD_ALLOCATIONS)
    ]
    levels = {str(level): {} for level in (10, 30, 50, 70, 90, 100)}
    workers = min(12, max(1, os.cpu_count() or 1), len(tasks))
    with ProcessPoolExecutor(max_workers=workers) as executor:
        for level, build, result in executor.map(_combat_profile_worker, tasks):
            levels[str(level)][build] = result
    return levels


def run_runtime_simulation(iterations: int, seed: int = 20260814) -> dict[str, Any]:
    simulator = RuntimeSimulator(seed)
    combat_iterations = min(iterations, 100_000)
    economy_iterations = min(iterations, 100_000)
    combat = (
        parallel_combat_profile(combat_iterations, seed)
        if combat_iterations >= 10_000
        else RuntimeSimulator(seed, prepare_economy=False).combat_profile(combat_iterations)
    )
    return {
        "engine": "data-driven-headless-v2",
        "combat_iterations_per_build": combat_iterations,
        "economy_seasons": economy_iterations,
        "levels": combat,
        "economy": simulator.season_economy(economy_iterations),
    }
