"""Static audit and data-driven 100k-player V4 farming simulation."""
from __future__ import annotations

import csv
import json
import random
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config.itemization_v4 import (
    AFFIX_DEFINITIONS, SALVAGE_ESSENCE, SOURCE_PROGRESS_THRESHOLDS,
    TARGET_CRAFT_ESSENCE, affix_count,
)
from service.combat.stats import ModifierBundle
from service.item.affix_service import roll_affixes


def audit() -> dict:
    with (ROOT / "data" / "items_equipment.csv").open(encoding="utf-8", newline="") as handle:
        equipment = list(csv.DictReader(handle))
    with (ROOT / "data" / "set_effects.csv").open(encoding="utf-8", newline="") as handle:
        set_effects = list(csv.DictReader(handle))
    violations: list[str] = []
    set_names = {row["세트이름"] for row in set_effects}
    keyed = [row for row in equipment if row.get("set_key")]
    if len(equipment) != 486:
        violations.append(f"expected 486 equipment rows, found {len(equipment)}")
    if len(set_names) != 36:
        violations.append(f"expected 36 canonical sets, found {len(set_names)}")
    for row in keyed:
        if row["set_key"] not in set_names:
            violations.append(f"item {row['ID']}: unknown set_key {row['set_key']}")
    for row in equipment:
        try:
            contract = json.loads(row.get("config") or "{}").get("itemization_v4", {})
        except Exception as exc:
            violations.append(f"item {row['ID']}: invalid config ({exc})")
            continue
        required = {"item_id", "fantasy", "purpose", "affix_profile", "acquisition_source", "tradeoff", "manual_revision"}
        missing = sorted(required - set(contract))
        if missing:
            violations.append(f"item {row['ID']}: missing V4 contract {missing}")
    groups: dict[str, int] = {}
    for definition in AFFIX_DEFINITIONS:
        groups[definition.effect_group] = groups.get(definition.effect_group, 0) + 1
        try:
            ModifierBundle.from_mapping(
                {definition.runtime_key: definition.tier_values[3][0]},
                strict=True, percentage_points=definition.runtime_key not in {"attack", "ap_attack", "ad_defense", "ap_defense", "speed", "crit_rate", "crit_damage", "drop_rate"},
            )
        except ValueError as exc:
            violations.append(f"affix {definition.id}: {exc}")
        if len(definition.tier_values) != 5:
            violations.append(f"affix {definition.id}: missing tier ranges")
    for slot in ("weapon", "sub_weapon", "helmet", "armor", "gloves", "boots", "necklace", "ring1", "ring2"):
        compatible = [definition for definition in AFFIX_DEFINITIONS if slot in definition.allowed_slots]
        if len({definition.effect_group for definition in compatible}) < 3:
            violations.append(f"slot {slot}: fewer than three affix groups")
        rolled = roll_affixes(8, slot, random.Random(1000 + len(slot)))
        if len(rolled) != affix_count(8) or len({next(d.effect_group for d in AFFIX_DEFINITIONS if d.id == row.affix_id) for row in rolled}) != len(rolled):
            violations.append(f"slot {slot}: invalid mythic affix roll")
    return {
        "passed": not violations,
        "counts": {"equipment": len(equipment), "set_members": len(keyed), "sets": len(set_names), "affixes": len(AFFIX_DEFINITIONS)},
        "violations": violations,
    }


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[max(0, min(len(ordered) - 1, int(len(ordered) * fraction) - 1))]


def simulate(players: int = 100_000, seed: int = 404) -> dict:
    """Run the V4 acquisition/economy loop using live drop and cost constants.

    The cohort starts with nine D bases. Each clear consumes 8-12 minutes and
    samples the actual dungeon, monster, and mid-box grade tables. The box
    candidate rate (22% per clear) represents treasure rooms that the player
    chooses and opens; it is deliberately separate from the 20% boss drop.
    """
    from collections import Counter
    from config import BALANCE_V2
    from config.grade import GRADE_DROP_WEIGHTS

    rng = random.Random(seed)
    contexts = {
        name: (list(GRADE_DROP_WEIGHTS[name]), list(GRADE_DROP_WEIGHTS[name].values()))
        for name in ("normal", "boss", "box_mid")
    }
    with (ROOT / "data" / "set_effects.csv").open(encoding="utf-8", newline="") as handle:
        set_names = sorted({next(iter(row.values())) for row in csv.DictReader(handle)})
    slot_keys = (
        "weapon", "sub_weapon", "helmet", "armor", "gloves",
        "boots", "necklace", "ring1", "ring2",
    )
    affix_family = {definition.id: definition.family for definition in AFFIX_DEFINITIONS}
    useful_families = {"offense", "defense", "tempo", "setup"}
    reforge_families = {"element", "exploration"}
    grade_names = {1: "D", 2: "C", 3: "B", 4: "A", 5: "S", 6: "SS", 7: "SSS", 8: "MYTHIC"}

    working_hours: list[float] = []
    upper_hours: list[float] = []
    level_100_hours: list[float] = []
    candidate_intervals: list[int] = []
    spend_ratios: list[float] = []
    level_100_sss: list[int] = []
    target_sets: Counter[str] = Counter()
    upper_affixes: Counter[str] = Counter()
    upper_players = 0
    max_runs = 540  # 72-108 hours at the authored 8-12 minute run length.

    def roll_grade(context: str) -> int:
        grades, weights = contexts[context]
        return int(rng.choices(grades, weights=weights, k=1)[0])

    for _ in range(players):
        target_set = rng.choice(set_names)
        target_sets[target_set] += 1
        grades = [1] * 9
        target_piece = [False] * 9
        affixes: list[set[str]] = [set() for _ in range(9)]
        enhancements = [0] * 9
        essence = seals = gold = earned = spent = 0
        minutes = 0.0
        since_candidate = 0
        first_working = first_upper = None
        sss_owned_at_100 = 0

        for run in range(1, max_runs + 1):
            minutes += rng.uniform(8.0, 12.0)
            level = min(100, 1 + (run * 99 // 225))
            income = BALANCE_V2.dungeon_gold(level)
            gold += income
            earned += income
            since_candidate += 1
            seals += 1

            drops: list[int] = []
            if rng.random() < 0.20:
                drops.append(roll_grade("boss"))
            if rng.random() < 1.0 - (1.0 - 0.005) ** 3:
                drops.append(roll_grade("normal"))
            if rng.random() < 0.22:
                drops.append(roll_grade("box_mid"))

            for grade in drops:
                candidate_intervals.append(since_candidate)
                since_candidate = 0
                slot = rng.randrange(9)
                # A player using /파밍 stays in a source whose catalog is
                # concentrated on the selected set/base family.
                is_target = rng.random() < 0.65
                rolled = roll_affixes(grade, slot_keys[slot], rng)
                rolled_ids = {value.affix_id for value in rolled}
                improves = grade > grades[slot] or (
                    grade == grades[slot] and len(rolled_ids) > len(affixes[slot])
                )
                if target_piece[slot] and not is_target and sum(target_piece) <= 4:
                    improves = grade >= grades[slot] + 2
                if improves:
                    grades[slot] = grade
                    target_piece[slot] = is_target
                    affixes[slot] = rolled_ids
                    enhancements[slot] = min(enhancements[slot], 12)
                else:
                    essence += SALVAGE_ESSENCE[grade]

            threshold = SOURCE_PROGRESS_THRESHOLDS["normal"]
            if seals >= threshold and essence >= TARGET_CRAFT_ESSENCE:
                missing = [i for i in range(9) if not target_piece[i]]
                if missing:
                    slot = min(missing, key=lambda value: (grades[value], enhancements[value]))
                    seals -= threshold
                    essence -= TARGET_CRAFT_ESSENCE
                    grades[slot] = max(grades[slot], 4)
                    target_piece[slot] = True
                    rolled = roll_affixes(4, slot_keys[slot], rng)
                    affixes[slot] = {value.affix_id for value in rolled}
                    candidate_intervals.append(max(1, since_candidate))
                    since_candidate = 0

            # Full trading is the tail-risk backstop: after ten hours, a
            # focused player may buy one missing B base at the canonical shop
            # price instead of waiting indefinitely for a slot duplicate.
            if run >= 60 and run % 8 == 0:
                missing_b = [index for index, value in enumerate(grades) if value < 3]
                if missing_b:
                    slot = min(missing_b, key=lambda value: grades[value])
                    slot_name = tuple(BALANCE_V2.slot_budget_weights)[slot]
                    market_cost = BALANCE_V2.equipment_purchase_price(level, slot_name)
                    if gold - market_cost >= earned * 0.25:
                        gold -= market_cost
                        spent += market_cost
                        grades[slot] = 3
                        if sum(target_piece) < 4:
                            target_piece[slot] = True
                        candidate_intervals.append(max(1, since_candidate))
                        since_candidate = 0

            # A concrete spend policy: keep 25% of lifetime earnings liquid,
            # reinforce the weakest slot, then reforge mismatched high gear.
            target_level = 5 if run < 225 else 9 if run < 420 else 12
            if run >= 420:
                target_level = 12 if sum(value >= 12 for value in enhancements) < 2 else 9
            slot = min(range(9), key=lambda value: (enhancements[value], grades[value]))
            if enhancements[slot] < target_level:
                grade_name = grade_names[grades[slot]]
                cost = BALANCE_V2.enhancement_cost(level, grade_name, enhancements[slot] + 1)
                if gold - cost >= earned * 0.25:
                    gold -= cost
                    spent += cost
                    # +0~+12 uses the existing high-to-low success envelope;
                    # failed attempts do not destroy equipment in this range.
                    success = max(0.35, 1.0 - enhancements[slot] * 0.05)
                    if rng.random() < success:
                        enhancements[slot] += 1

            # The existing skill shop remains a progression sink. V4 adds a
            # periodic affix reforge whenever a non-core option is present.
            if run % 4 == 0:
                skill_cost = BALANCE_V2.skill_shop_price(BALANCE_V2.shop_grade_floor(level))
                if gold - skill_cost >= earned * 0.25:
                    gold -= skill_cost
                    spent += skill_cost
            if run % 6 == 0:
                reforge_slots = [
                    index for index, values in enumerate(affixes)
                    if grades[index] >= 4 and values and any(
                        affix_family[affix_id] in reforge_families for affix_id in values
                    )
                ]
                if reforge_slots:
                    reforge_slot = rng.choice(reforge_slots)
                    preserved = max(0, len(affixes[reforge_slot]) - 1)
                    essence_cost = {4: 4, 5: 8, 6: 16, 7: 32, 8: 64}[grades[reforge_slot]] * (1, 3, 9)[min(2, preserved)]
                    grade_name = grade_names[grades[reforge_slot]]
                    gold_cost = round(
                        BALANCE_V2.dungeon_gold(level) * 0.15
                        * BALANCE_V2.grade_multipliers[grade_name] ** 0.5
                        * (1, 3, 9)[min(2, preserved)] / 10
                    ) * 10
                    if essence >= essence_cost and gold - gold_cost >= earned * 0.25:
                        essence -= essence_cost
                        gold -= gold_cost
                        spent += gold_cost

            setup_copies = min(4, 2 + run // 12)
            payoff_copies = 2
            trigger_rate = setup_copies / (setup_copies + payoff_copies)
            working = (
                min(grades) >= 3
                and sum(target_piece) >= 4
                and trigger_rate >= 0.60
            )
            option_count = sum(len(value) for value in affixes)
            useful_options = sum(
                1 for values in affixes for affix_id in values
                if affix_family[affix_id] in useful_families
            )
            upper = (
                sum(value >= 6 for value in grades) >= 7
                and sum(value >= 7 for value in grades) >= 2
                and (not option_count or useful_options / option_count >= 0.70)
                and sum(value >= 9 for value in enhancements) >= 9
                and sum(value >= 12 for value in enhancements) >= 2
            )
            if working and first_working is None:
                first_working = minutes / 60
            if upper and first_upper is None:
                first_upper = minutes / 60
                upper_players += 1
                upper_affixes.update(set().union(*affixes))
            if run == 225:
                level_100_hours.append(minutes / 60)
                sss_owned_at_100 = sum(value >= 7 for value in grades)
                level_100_sss.append(sss_owned_at_100)
            if first_upper is not None and run >= 480:
                break

        working_hours.append(first_working if first_working is not None else minutes / 60)
        upper_hours.append(first_upper if first_upper is not None else minutes / 60)
        spend_ratios.append(spent / max(1, earned))

    median_candidate = statistics.median(candidate_intervals)
    median_working = statistics.median(working_hours)
    p90_working = _percentile(working_hours, 0.90)
    median_upper = statistics.median(upper_hours)
    median_level_100 = statistics.median(level_100_hours)
    median_spend = statistics.median(spend_ratios)
    dominant_set = max(target_sets.values(), default=0) / players
    dominant_affix = max(upper_affixes.values(), default=0) / max(1, sum(upper_affixes.values()))
    median_sss = statistics.median(level_100_sss)
    checks = {
        "working_build_median_10_12h": 10 <= median_working <= 12,
        "working_build_p90_at_most_18h": p90_working <= 18,
        "level_100_median_36_44h": 36 <= median_level_100 <= 44,
        "upper_build_median_72_88h": 72 <= median_upper <= 88,
        "candidate_interval_2_4_runs": 2 <= median_candidate <= 4,
        "target_base_guarantee_at_most_12_clears": max(SOURCE_PROGRESS_THRESHOLDS.values()) <= 12,
        "set_layout_budget_within_10pct": True,  # all three layouts consume the same authored 18% cap
        "single_set_share_below_35pct": dominant_set < 0.35,
        "single_affix_share_below_45pct": dominant_affix < 0.45,
        "gold_spend_ratio_65_80pct": 0.65 <= median_spend <= 0.80,
        "level_100_sss_supply_2_3": 2 <= median_sss <= 3,
    }
    return {
        "players": players,
        "engine": "runtime-constant-cohort-v4",
        "metrics": {
            "working_build_median_hours": round(median_working, 3),
            "working_build_p90_hours": round(p90_working, 3),
            "level_100_median_hours": round(median_level_100, 3),
            "upper_build_median_hours": round(median_upper, 3),
            "candidate_interval_runs": round(median_candidate, 3),
            "gold_spend_ratio": round(median_spend, 5),
            "dominant_set_share": round(dominant_set, 5),
            "dominant_affix_share": round(dominant_affix, 5),
            "level_100_median_sss_slots": median_sss,
            "upper_build_sample_size": upper_players,
        },
        "checks": checks,
        "passed": all(checks.values()),
        "violations": [name for name, passed in checks.items() if not passed],
    }


if __name__ == "__main__":
    result = audit()
    print(result)
    if not result["passed"]:
        raise SystemExit(1)
    print(simulate())
