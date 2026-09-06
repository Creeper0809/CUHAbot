#!/usr/bin/env python3
"""Deterministic abstract Monte Carlo calibration for roguelike targets.

This harness is intentionally independent from Discord and the database. It
models normalized recommended-level combat attrition using the production
route weights, hidden hazard outcomes, room scaling, rests, NPC healing, and
boss attrition. Run live telemetry remains the final balancing authority.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import random
import statistics
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config import ROGUELIKE, RouteKind
from service.dungeon.roguelike_routes import generate_route_offers, room_stat_scale


@dataclass(frozen=True)
class TestCharacter:
    name: str
    normalized_toughness: float


CHARACTERS = (
    TestCharacter("beginner", 0.95),
    TestCharacter("intermediate", 1.00),
    TestCharacter("advanced", 1.05),
)

GRADE_VALUE = {"D": 0, "C": 1, "B": 2, "A": 3, "S": 4}
# Conditional, utility, and HP-cost effects use encounter-averaged power rather
# than their tooltip's peak multiplier.
AUGMENT_EFFECTIVE_POWER = (
    0.21, 0.17, 0.15, 0.13, 0.14, 0.17, 0.25,
    0.15, 0.14, 0.13, 0.12, 0.14, 0.21, 0.17,
)


def _choose(offers, rng: random.Random, strategy: str):
    if strategy == "elite":
        return max(offers, key=lambda item: (item.kind == RouteKind.ELITE, item.risk))
    return max(
        offers,
        key=lambda item: GRADE_VALUE[item.reward_grade] * 1.4 - item.risk + rng.random(),
    )


def simulate_run(seed: int, toughness: float, strategy: str = "balanced") -> bool:
    rng = random.Random(seed)
    hp = 1.0
    for room in range(1, ROGUELIKE.ROUTE_ROOMS + 1):
        offer = _choose(generate_route_offers(room, rng), rng, strategy)
        scale = room_stat_scale(room)
        if offer.kind == RouteKind.COMBAT:
            hp -= rng.uniform(0.10, 0.17) * scale / toughness
        elif offer.kind == RouteKind.ELITE:
            hp -= rng.uniform(0.18, 0.32) * scale / toughness
        elif offer.kind == RouteKind.HAZARD and offer.payload["triggered"]:
            hp -= float(offer.payload["damage_rate"]) / toughness
        elif offer.kind == RouteKind.REST:
            hp = min(1.0, hp + ROGUELIKE.REST_HEAL_RATE)
        elif offer.kind == RouteKind.EVENT:
            hp += 0.10 if offer.payload["event_type"] == "heal" else (
                -0.05 if offer.payload["event_type"] == "damage" else 0.0
            )
        elif offer.kind == RouteKind.NPC and offer.payload["npc_type"] == "healer":
            hp = min(1.0, hp + 0.30)
        if hp <= 0:
            return False
    hp -= rng.uniform(0.30, 0.55) / toughness
    return hp > 0


def report(runs: int) -> dict:
    result = {"runs_per_character": runs, "characters": {}}
    for index, character in enumerate(CHARACTERS):
        balanced = sum(
            simulate_run(index * runs + seed, character.normalized_toughness)
            for seed in range(runs)
        ) / runs
        elite = sum(
            simulate_run(10_000_000 + index * runs + seed, character.normalized_toughness, "elite")
            for seed in range(runs)
        ) / runs
        result["characters"][character.name] = {
            "recommended_clear_rate": balanced,
            "elite_priority_clear_rate": elite,
        }

    rng = random.Random(20260813)
    single = [rng.choice(AUGMENT_EFFECTIVE_POWER) for _ in range(runs)]
    triple = []
    for _ in range(runs):
        modifiers = rng.sample(AUGMENT_EFFECTIVE_POWER, 3)
        triple.append((1 + modifiers[0]) * (1 + modifiers[1]) * (1 + modifiers[2]) - 1)
    result["augments"] = {
        "mean_single_power_gain": statistics.mean(single),
        "median_three_power_gain": statistics.median(triple),
    }
    return result


def validate(result: dict) -> list[str]:
    errors = []
    for name, values in result["characters"].items():
        if not 0.60 <= values["recommended_clear_rate"] <= 0.75:
            errors.append(f"{name}: recommended clear rate outside 60-75%")
        if values["elite_priority_clear_rate"] > 0.45:
            errors.append(f"{name}: elite-priority clear rate exceeds 45%")
    augments = result["augments"]
    if not 0.15 <= augments["mean_single_power_gain"] <= 0.25:
        errors.append("mean single augment outside 15-25%")
    if not 0.45 <= augments["median_three_power_gain"] <= 0.65:
        errors.append("median three augments outside 45-65%")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=20_000)
    args = parser.parse_args()
    result = report(max(100, args.runs))
    for name, values in result["characters"].items():
        print(
            f"{name}: recommended={values['recommended_clear_rate']:.2%}, "
            f"elite={values['elite_priority_clear_rate']:.2%}"
        )
    print(
        f"augments: single_mean={result['augments']['mean_single_power_gain']:.2%}, "
        f"triple_median={result['augments']['median_three_power_gain']:.2%}"
    )
    errors = validate(result)
    for error in errors:
        print(f"FAIL: {error}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
