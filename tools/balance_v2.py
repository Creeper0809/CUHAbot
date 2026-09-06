"""Balance V2 data generator, auditor, simulator, and report writer.

Usage::

    python tools/balance_v2.py audit
    python tools/balance_v2.py generate --write
    python tools/balance_v2.py simulate --iterations 100000
    python tools/balance_v2.py report --output reports/balance_v2
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import random
import re
import sys
from collections import Counter, defaultdict
from copy import deepcopy
from pathlib import Path
from statistics import median
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.balance_v2 import BALANCE_V2

DATA = ROOT / "data"
GRADE_ORDER = ("D", "C", "B", "A", "S", "SS", "SSS", "MYTHIC")
# Reference progression bands used by both generated monsters and the runtime
# harness: C at the first checkpoint, then one tier every twenty levels.
GRADE_BY_LEVEL = ((20, "C"), (40, "B"), (60, "A"), (80, "S"), (100, "SS"))

SLOT_CANONICAL = {
    "검": "weapon", "무기": "weapon", "지팡이": "weapon", "활": "weapon", "도끼": "weapon",
    "방패": "sub_weapon", "오브": "sub_weapon",
    "갑옷": "armor", "방어구": "armor", "망토": "armor",
    "투구": "helmet", "장갑": "gloves", "신발": "boots",
    "목걸이": "necklace", "장신구": "necklace", "반지": "ring1",
}
CANONICAL_TO_CSV = {
    "weapon": "무기", "sub_weapon": "방패", "armor": "갑옷", "helmet": "투구",
    "gloves": "장갑", "boots": "신발", "necklace": "목걸이", "ring1": "반지",
}
NAME_CLASSIFIERS = (
    ("장갑", "gloves"), ("투구", "helmet"), ("갑옷", "armor"), ("로브", "armor"),
    ("반지", "ring1"), ("목걸이", "necklace"), ("귀걸이", "necklace"),
    ("십자가", "necklace"), ("심장", "necklace"), ("모래시계", "necklace"),
    ("검", "weapon"), ("낫", "weapon"),
)


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def write_text_lf(path: Path, content: str) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(content)


def write_csv(path: Path, fieldnames: list[str], rows: Iterable[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value) if str(value).strip() else default
    except (TypeError, ValueError):
        return default


def classify_slot(row: dict[str, str]) -> str:
    raw = row.get("슬롯", "").strip()
    if raw:
        if raw not in SLOT_CANONICAL:
            raise ValueError(f"Unclassified equipment slot {raw!r}: {row.get('ID')} {row.get('이름')}")
        return SLOT_CANONICAL[raw]
    name = row.get("이름", "")
    for token, slot in NAME_CLASSIFIERS:
        if token in name:
            return slot
    raise ValueError(f"Unclassified blank-slot equipment: {row.get('ID')} {name}")


def equipment_cp(row: dict[str, Any]) -> float:
    ad, ap = number(row.get("Attack")), number(row.get("AP_Attack"))
    pdef, mdef = number(row.get("AD_Def")), number(row.get("AP_Def"))
    offense = max(ad, ap) + 0.35 * min(ad, ap)
    defense = 1.5 * (max(pdef, mdef) + 0.5 * min(pdef, mdef))
    return offense + number(row.get("HP")) / 10.0 + defense + number(row.get("Speed")) * 2.0


def equipment_final_cp(
    row: dict[str, Any], grade: str, enhancement_level: int = 0,
    special_effects: list[dict[str, Any]] | None = None,
) -> float:
    """Final instance CP using the same grade/enhancement/effect budgets as runtime."""
    from service.item.grade_service import GradeService

    grade_key = _grade_key(grade)
    effect_ratio = GradeService.special_effect_budget_ratio(special_effects)
    return (
        equipment_cp(row)
        * BALANCE_V2.grade_multipliers[grade_key]
        * BALANCE_V2.enhancement_stat_multiplier(enhancement_level)
        * (1.0 + effect_ratio)
    )


def _seed_equipment_vector(slot: str, target: float) -> dict[str, float]:
    result = {key: 0.0 for key in ("Attack", "AP_Attack", "HP", "AD_Def", "AP_Def", "Speed")}
    if slot == "weapon":
        result["Attack"] = target
    elif slot == "sub_weapon":
        result["Attack"] = target * 0.35
        result["AD_Def"] = target * 0.65 / 1.5
    elif slot in {"armor", "helmet"}:
        result["HP"] = target * 4.0
        result["AD_Def"] = target * 0.6 / 1.5
    elif slot in {"gloves", "boots"}:
        result["Attack"] = target * 0.45
        result["Speed"] = target * 0.55 / 2.0
    elif slot == "necklace":
        result["AP_Attack"] = target * 0.55
        result["HP"] = target * 4.5
    else:
        result["Attack"] = target * 0.55
        result["AP_Attack"] = target * 0.45
    return result


def generate_equipment(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    generated: list[dict[str, str]] = []
    stat_keys = ("Attack", "AP_Attack", "HP", "AD_Def", "AP_Def", "Speed")
    for source in rows:
        row = dict(source)
        slot = classify_slot(row)
        if not row.get("슬롯", "").strip():
            row["슬롯"] = CANONICAL_TO_CSV[slot]
        level = max(1, min(100, int(number(row.get("Lv"), 1))))
        target = BALANCE_V2.slot_budget(level, slot)
        current = equipment_cp(row)
        values = (
            {key: number(row.get(key)) * target / current for key in stat_keys}
            if current > 0 else _seed_equipment_vector(slot, target)
        )
        for key, value in values.items():
            rounded = max(0, int(round(value)))
            row[key] = str(rounded) if rounded else ""
        # Correct integer rounding drift. Coarse primary stats are stepped
        # down only when they overshoot; HP then fills with 0.1 CP granularity.
        row["HP"] = ""
        while equipment_cp(row) > target + 0.05:
            candidates = [key for key in ("Attack", "AP_Attack", "Speed", "AD_Def", "AP_Def") if number(row.get(key)) > 0]
            if not candidates:
                break
            key = max(candidates, key=lambda candidate: number(row.get(candidate)))
            value = max(0, int(number(row.get(key))) - 1)
            row[key] = str(value) if value else ""
        hp = max(0, int(round((target - equipment_cp(row)) * 10)))
        row["HP"] = str(hp) if hp else ""
        generated.append(row)
    return generated


def _grade_key(raw: str) -> str:
    return "MYTHIC" if raw == "신화" else raw if raw in GRADE_ORDER else "D"


def _attack_components(config: dict[str, Any]) -> list[dict[str, Any]]:
    return [component for component in config.get("components", []) if component.get("tag") in {"attack", "lifesteal"}]


def _component_attack_value(component: dict[str, Any]) -> float:
    hits = max(1, int(component.get("hit_count", 1)))
    coefficient = abs(number(component.get("ad_ratio"))) + abs(number(component.get("ap_ratio")))
    if coefficient == 0:
        coefficient = abs(number(component.get("damage"), 1.0))
    target = str(component.get("target", "single")).lower()
    aoe = component.get("aoe", False) or target in {"all", "all_enemies", "all_enemy", "enemies"}
    return coefficient * hits * (2.2 if aoe else 1.0)


def skill_action_value(row: dict[str, str], config: dict[str, Any]) -> float:
    grade = _grade_key(row.get("등급", "D"))
    center = 3.75 if row.get("카테고리") == "ultimate" else BALANCE_V2.action_values[grade]
    healing_reference = BALANCE_V2.healing_max_hp[grade]
    value = 0.0
    recognized = False
    components = config.get("components", [])
    for component in components:
        tag = component.get("tag")
        if tag in {"attack", "lifesteal"}:
            value += _component_attack_value(component)
            recognized = True
        elif tag == "heal":
            heal_ratio = number(component.get("percent", component.get("heal_percent")))
            if heal_ratio:
                value += heal_ratio / max(0.01, healing_reference) * center
                recognized = True
            elif component.get("heal_type") == "hp_restore_snapshot":
                # Snapshot restoration has no scalar in the legacy data.  It is a
                # full action utility effect, so keep an explicit tunable scale
                # instead of silently accepting it at the grade target.
                value += center * number(component.get("power_scale"), 1.0)
                recognized = True
        elif tag == "shield":
            value += number(component.get("percent")) / max(0.01, healing_reference) * center * 0.8
            recognized = True
        elif tag in {"buff", "debuff"}:
            magnitude = sum(
                abs(number(raw))
                for key, raw in component.items()
                if key not in {"tag", "duration", "target", "power_scale"}
            )
            if magnitude:
                value += (
                    magnitude
                    * min(5, max(1, int(number(component.get("duration"), 1))))
                    / 3.0
                    * 1.5
                    * number(component.get("power_scale"), 1.0)
                )
                recognized = True
            else:
                duration = min(5, max(1, int(number(component.get("duration"), 1))))
                target_multiplier = 2.2 if str(component.get("target", "single")).lower() in {
                    "all", "all_ally", "all_allies", "all_enemy", "all_enemies"
                } else 1.0
                utility_per_turn = {
                    "invincible": 0.80,
                    "heal_block": 0.25,
                    "death_mark": 0.25,
                    "random_redistribute": 0.45,
                }.get(str(component.get("stat", "")), 0.20)
                value += (
                    utility_per_turn
                    * duration
                    * target_multiplier
                    * number(component.get("power_scale"), 1.0)
                )
                recognized = True
        elif tag == "status":
            value += (
                min(1.0, number(component.get("chance"), 1.0))
                * max(1, int(number(component.get("duration"), 1)))
                * max(1, int(number(component.get("stacks"), 1)))
                * 0.20
            )
            recognized = True
        elif tag == "cleanse":
            value += center if len(components) == 1 else 0.15
            recognized = True
        elif tag == "combo":
            coefficient = abs(number(component.get("ad_ratio"))) + abs(number(component.get("ap_ratio")))
            multiplier = max(0.0, number(component.get("damage_multiplier"), 1.0))
            status_value = 0.35 if component.get("apply_status") else 0.0
            value += (
                (coefficient * multiplier + status_value)
                * 0.55
                * number(component.get("power_scale"), 1.0)
            )
            recognized = True
        elif tag == "consume":
            coefficient = (
                abs(number(component.get("ad_ratio")))
                + abs(number(component.get("ap_ratio")))
                + abs(number(component.get("per_stack_ratio")))
            )
            value += max(0.25, coefficient * 2.0) * 0.55
            recognized = True
        elif tag == "summon":
            count = max(1, int(number(component.get("count"), 1)))
            value += 0.75 * count * number(component.get("power_scale"), 1.0)
            recognized = True
        elif tag == "dot":
            coefficient = abs(number(component.get("ad_ratio"))) + abs(number(component.get("ap_ratio")))
            duration = max(1, int(number(component.get("duration"), 1)))
            aoe = str(component.get("target", "single")).lower() == "all"
            value += coefficient * duration * (2.2 if aoe else 1.0) * 0.65
            recognized = True
        elif tag == "revive":
            targets = 3 if component.get("target") == "all_ally" else max(1, int(number(component.get("count"), 1)))
            value += number(component.get("hp_percent"), 0.5) * targets * 1.5
            recognized = True
        elif tag == "self_destruct":
            coefficient = abs(number(component.get("ad_ratio"))) + abs(number(component.get("ap_ratio")))
            charge = max(1, int(number(component.get("charge_turns"), 1)))
            value += coefficient * 2.2 / charge
            recognized = True
        elif tag == "self_damage":
            value -= number(component.get("hp_cost")) * 1.5
            recognized = True
    return max(0.05, value) if recognized else 0.0


def _scale_skill_components(config: dict[str, Any], factor: float) -> None:
    for component in config.get("components", []):
        tag = component.get("tag")
        if tag in {"attack", "lifesteal"}:
            for key in ("ad_ratio", "ap_ratio", "damage"):
                if key in component:
                    component[key] = round(number(component[key]) * factor, 4)
            if "armor_pen" in component:
                component["armor_pen"] = min(BALANCE_V2.max_penetration, number(component["armor_pen"]))
        elif tag == "heal":
            key = "percent" if "percent" in component else "heal_percent"
            if key in component:
                component[key] = round(number(component.get(key)) * factor, 4)
            elif component.get("heal_type") == "hp_restore_snapshot":
                component["power_scale"] = round(number(component.get("power_scale"), 1.0) * factor, 4)
        elif tag == "shield" and "percent" in component:
            component["percent"] = round(number(component["percent"]) * factor, 4)
        elif tag in {"buff", "debuff"}:
            scalable = False
            for key, value in list(component.items()):
                if key not in {"tag", "duration", "target", "power_scale"} and isinstance(value, (int, float)):
                    component[key] = round(number(value) * factor, 4)
                    scalable = True
            if not scalable:
                component["power_scale"] = round(number(component.get("power_scale"), 1.0) * factor, 4)
        elif tag == "status":
            if factor <= 1.0:
                component["chance"] = min(1.0, round(number(component.get("chance"), 1.0) * factor, 4))
            elif "stacks" in component:
                component["stacks"] = max(1, round(number(component["stacks"], 1.0) * factor))
            else:
                component["duration"] = max(1, round(number(component.get("duration"), 1.0) * factor))
        elif tag == "cleanse" and "count" in component and number(component["count"]) < 99:
            component["count"] = max(1, round(number(component["count"]) * factor))
        elif tag == "combo":
            ratio_keys = [key for key in ("ad_ratio", "ap_ratio") if key in component]
            effective_ratio_keys = [key for key in ratio_keys if number(component.get(key)) != 0]
            if effective_ratio_keys:
                for key in effective_ratio_keys:
                    component[key] = round(number(component[key]) * factor, 4)
            elif "damage_multiplier" in component and number(component.get("damage_multiplier")) != 0:
                component["damage_multiplier"] = round(number(component["damage_multiplier"]) * factor, 4)
            else:
                component["power_scale"] = round(number(component.get("power_scale"), 1.0) * factor, 4)
        elif tag == "consume":
            for key in ("ad_ratio", "ap_ratio", "per_stack_ratio", "base_damage"):
                if key in component:
                    component[key] = round(number(component[key]) * factor, 4)
        elif tag == "summon":
            component["power_scale"] = round(number(component.get("power_scale"), 1.0) * factor, 4)
        elif tag == "dot":
            for key in ("ad_ratio", "ap_ratio"):
                if key in component:
                    component[key] = round(number(component[key]) * factor, 4)
        elif tag == "revive":
            component["hp_percent"] = min(1.0, round(number(component.get("hp_percent"), 0.5) * factor, 4))
        elif tag == "self_destruct":
            for key in ("ad_ratio", "ap_ratio"):
                if key in component:
                    component[key] = round(number(component[key]) * factor, 4)


def generate_skills(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    from service.skill.design_v3 import apply_authored_design, describe_skill_config

    generated: list[dict[str, str]] = []
    for source in rows:
        row = dict(source)
        try:
            config = json.loads(row["config"])
        except json.JSONDecodeError:
            generated.append(row)
            continue
        # The named Blessing skill is the canonical producer for the
        # radiance payoff ecosystem. Legacy data described only its stat buff,
        # leaving Holy Explosion's `blessing` consumption impossible at runtime.
        if int(row["ID"]) == 1504 and not any(
            component.get("tag") == "status" and component.get("type") == "blessing"
            for component in config.get("components", [])
        ):
            config.setdefault("components", []).append({
                "tag": "status", "type": "blessing", "chance": 1.0,
                "duration": 3, "stacks": 1,
            })
        # V3 identity and mechanics are authored per ID. Balance generation
        # audits the numeric outcome but never rescales or reclassifies content.
        apply_authored_design(int(row["ID"]), config)
        row["효과"] = describe_skill_config(config)
        row["config"] = json.dumps(config, ensure_ascii=False, separators=(",", ":"))
        generated.append(row)
    return generated


def benchmark_stats(level: int) -> dict[str, float]:
    # Use the same +5 gear, four-set, passive-stack and allocated-stat model as
    # the headless runtime simulator. The previous reference omitted all level
    # stat points, causing generated monsters to be tuned against an impossible
    # under-built player.
    from tools.headless_balance_runtime import balanced_reference_stats

    return balanced_reference_stats(level)


def _monster_skill_channels(row: dict[str, str], skills_by_id: dict[int, dict[str, str]]) -> tuple[bool, bool, float]:
    try:
        ids = [int(value) for value in json.loads(row.get("skill_ids") or "[]") if int(value)]
    except (ValueError, TypeError, json.JSONDecodeError):
        ids = []
    physical = magical = False
    has_stat_independent_damage = False
    coefficients: list[float] = []
    for skill_id in ids:
        skill = skills_by_id.get(skill_id)
        if not skill:
            continue
        try:
            config = json.loads(skill.get("config") or "{}")
        except json.JSONDecodeError:
            continue
        skill_coefficient = 0.0
        for component in config.get("components", []):
            tag = component.get("tag")
            if tag not in {"attack", "lifesteal", "dot", "consume", "self_destruct", "combo"}:
                continue
            ad, ap = number(component.get("ad_ratio")), number(component.get("ap_ratio"))
            stat_independent = component.get("damage_type") in {
                "instant_kill", "current_hp_percent", "max_hp_percent"
            }
            has_stat_independent_damage |= stat_independent
            physical |= not stat_independent and (ad > 0 or (ad == 0 and ap == 0))
            magical |= ap > 0
            component_coefficient = (ad + ap) * max(1, int(component.get("hit_count", 1)))
            if tag == "consume":
                component_coefficient = max(0.25, component_coefficient)
            skill_coefficient += component_coefficient
        # Monster.next_skill shuffles every non-passive skill, including pure
        # support/control actions. Those turns must count as zero damage rather
        # than disappearing from the average.
        coefficients.append(max(0.0, skill_coefficient))
    if not physical and not magical and not has_stat_independent_damage:
        physical = True
    return physical, magical, sum(coefficients) / len(coefficients) if coefficients else 1.0


def _phase_entries(phase_text: str) -> list[dict[str, Any]]:
    """Convert the legacy boss prose into deterministic runtime phase data.

    Percentages outside the ``HP ...`` clause describe effects, not additional
    phase thresholds.  Parsing the whole sentence used to turn e.g. ``+30%``
    attack into an accidental second phase at 30% HP.
    """
    entries: list[dict[str, Any]] = []
    for segment in (value.strip() for value in phase_text.split("|") if value.strip()):
        hp_clause = re.search(r"HP\s+([0-9%/]+)", segment, flags=re.IGNORECASE)
        if not hp_clause:
            continue
        thresholds = [int(value) for value in re.findall(r"\d+", hp_clause.group(1))]
        attack_match = re.search(r"공격력\s*\+?(\d+)%", segment)
        speed_match = re.search(r"공격속도\s*\+?(\d+)%", segment)
        all_stat_match = re.search(r"모든\s*스탯\s*\+?(\d+)%", segment)
        attack_pct = int(attack_match.group(1)) / 100 if attack_match else 0.15
        speed_pct = int(speed_match.group(1)) / 100 if speed_match else 0.10
        defense_pct = 0.0
        if all_stat_match:
            all_stat_pct = int(all_stat_match.group(1)) / 100
            attack_pct = max(attack_pct, all_stat_pct)
            speed_pct = max(speed_pct, all_stat_pct)
            defense_pct = all_stat_pct
        if "공격속도 2배" in segment or "매 턴 2회 행동" in segment:
            speed_pct = max(speed_pct, 1.0)

        summon_matches = re.findall(r"(\d+)(?:체|마리|개의).*?소환", segment)
        summon_count = max((int(value) for value in summon_matches), default=0)
        invulnerable = "본체 무적" in segment and summon_count > 0
        for threshold in sorted(set(thresholds), reverse=True):
            entries.append({
                "hp_threshold": threshold / 100.0,
                "attack_pct": attack_pct,
                "speed_pct": speed_pct,
                "defense_pct": max(
                    defense_pct,
                    0.10 if any(token in segment for token in ("방어", "형태")) else 0.0,
                ),
                "shield_pct": 0.10 if "무적" in segment and not invulnerable else 0.0,
                "heal_pct": 0.10 if any(token in segment for token in ("재생", "역류")) else 0.0,
                "summon_count": min(4, summon_count),
                "invulnerable_until_summons": invulnerable,
                "description": segment,
            })
    return sorted(entries, key=lambda value: value["hp_threshold"], reverse=True)


def generate_monsters(rows: list[dict[str, str]], skills: list[dict[str, str]]) -> tuple[list[str], list[dict[str, str]]]:
    skills_by_id = {int(row["ID"]): row for row in skills}
    generated: list[dict[str, str]] = []
    for source in rows:
        row = dict(source)
        from config.beginner_balance import MONSTER_STATS
        entry = MONSTER_STATS.get(int(row["ID"]))
        if entry is not None:
            hp, ad, ap, defense = entry
            row.update({"HP": str(hp), "Attack": str(ad), "AP_Attack": str(ap),
                        "Defense": str(defense), "AP_Defense": str(defense)})
            generated.append(row)
            continue
        level = max(1, min(100, int(number(row.get("레벨"), 1))))
        kind = row.get("타입", "CommonMob")
        phase_text = row.get("페이즈", "").strip()
        phase_entries = _phase_entries(phase_text)
        reference = benchmark_stats(level)
        actions = BALANCE_V2.monster_action_targets.get(kind, 2.5)
        incoming_fraction = BALANCE_V2.monster_incoming_fraction(kind, level)
        defense = max(1, round(reference["attack"] * (0.22 if kind == "CommonMob" else 0.30)))
        mitigation = BALANCE_V2.defense_reduction(defense)
        grade = next(grade for cap, grade in GRADE_BY_LEVEL if level <= cap)
        expected_crit = 1.0 + 0.05 * 0.50
        expected_offense_share = 0.75
        expected_hit = BALANCE_V2.hit_rate(95, 5)
        player_action_damage = (
            reference["attack"]
            * BALANCE_V2.action_values[grade]
            * expected_offense_share
            * expected_hit
            * expected_crit
            * (1.0 - mitigation)
        )
        phase_durability = 1.0 + sum(
            float(phase.get("heal_pct", 0))
            + float(phase.get("shield_pct", 0))
            + min(2, int(phase.get("summon_count", 0) or 0)) * .30
            for phase in phase_entries
        )
        hp = max(10, round(player_action_damage * actions / phase_durability))
        physical, magical, coefficient = _monster_skill_channels(row, skills_by_id)
        player_mitigation = BALANCE_V2.defense_reduction(reference["defense"])
        desired_damage = reference["hp"] * incoming_fraction
        expected_monster_hit_crit = BALANCE_V2.hit_rate(95, 5) * 1.025
        phase_pressure = 1.0 + sum(
            float(phase["hp_threshold"]) * (
                float(phase.get("attack_pct", 0))
                + float(phase.get("speed_pct", 0))
                + min(2, int(phase.get("summon_count", 0) or 0)) * .50
            )
            for phase in phase_entries
        )
        source_attack = desired_damage / max(
            0.005,
            coefficient * expected_monster_hit_crit * (1.0 - player_mitigation),
        ) / phase_pressure
        row["HP"] = str(hp)
        row["Attack"] = str(max(1, round(source_attack))) if physical else "0"
        row["AP_Attack"] = str(max(1, round(source_attack))) if magical else "0"
        row["Defense"] = str(defense)
        row["AP_Defense"] = str(defense)
        row["Accuracy"] = "95"
        row["Evasion"] = "5"
        row["Speed"] = "100"
        if phase_entries:
            row["phase_config"] = json.dumps({"phases": phase_entries}, ensure_ascii=False, separators=(",", ":"))
        else:
            row["phase_config"] = "{}"
        generated.append(row)
    headers = list(rows[0].keys()) if rows else []
    for field in ("AP_Defense", "Accuracy", "Evasion", "phase_config"):
        if field not in headers:
            insert_at = headers.index("Defense") + 1 if "Defense" in headers else len(headers)
            headers.insert(insert_at, field)
    return headers, generated


def generate_sets(rows: list[dict[str, str]], equipment_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    counts = Counter(row.get("세트", "").strip() for row in equipment_rows if row.get("세트", "").strip())
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row["세트이름"]].append(dict(row))
    generated: list[dict[str, str]] = []
    for name, effects in grouped.items():
        pieces = counts.get(name, max(int(row["필요수"]) for row in effects))
        if pieces >= 6:
            thresholds = (2, 4, 6)
            cumulative_caps = (0.04, 0.10, 0.18)
        elif pieces == 5:
            thresholds = (2, 3, 5)
            cumulative_caps = (0.04, 0.08, 0.14)
        elif pieces >= 3:
            thresholds = (2, pieces)
            cumulative_caps = (0.04, 0.10)
        elif pieces == 2:
            thresholds = (2,)
            cumulative_caps = (0.06,)
        else:
            # Single-piece definitions are treated as unique effects at 1.
            thresholds = (1,)
            cumulative_caps = (0.06,)
        incremental_caps = tuple(
            cumulative_caps[index] - (cumulative_caps[index - 1] if index else 0.0)
            for index in range(len(cumulative_caps))
        )
        buckets: dict[int, list[dict[str, Any]]] = defaultdict(list)
        descriptions: dict[int, list[str]] = defaultdict(list)
        for effect in effects:
            old = int(effect["필요수"])
            target = min(thresholds, key=lambda value: (abs(value - min(old, pieces)), value))
            try:
                buckets[target].append(json.loads(effect["효과config"]))
            except json.JSONDecodeError:
                buckets[target].append({})
            descriptions[target].append(effect["효과설명"])
        for threshold in thresholds:
            configs = buckets.get(threshold, [])
            if not configs:
                continue
            merged: dict[str, float] = defaultdict(float)
            for config in configs:
                for key, value in config.items():
                    if isinstance(value, (int, float)):
                        merged[key] += value
            # Set budgets are expressed as percentages of reference CP. Legacy
            # flat stats are converted to same-direction percentage modifiers,
            # then every unlock is normalized to its incremental budget.
            flat_to_percent = {
                "hp": "hp_pct", "attack": "attack_pct", "ap_attack": "ap_attack_pct",
                "ad_defense": "ad_defense_pct", "ap_defense": "ap_defense_pct", "speed": "speed_pct",
            }
            normalized: dict[str, float] = defaultdict(float)
            for key, value in merged.items():
                normalized[flat_to_percent.get(key, key)] += value
            budget_points = incremental_caps[thresholds.index(threshold)] * 100.0
            raw_total = sum(abs(value) for value in normalized.values())
            if raw_total > 0:
                scale = budget_points / raw_total
                normalized = {key: round(value * scale, 4) for key, value in normalized.items()}
            generated.append({
                "세트이름": name,
                "설명": effects[0]["설명"],
                "필요수": str(threshold),
                "효과설명": f"V2 세트 전투력 예산 +{budget_points:g}%",
                "효과config": json.dumps(dict(normalized), ensure_ascii=False, separators=(",", ":")),
            })
    return generated


def generate(write: bool) -> dict[str, Any]:
    equipment_headers, equipment = read_csv(DATA / "items_equipment.csv")
    skill_headers, skills = read_csv(DATA / "skills.csv")
    monster_headers, monsters = read_csv(DATA / "monsters.csv")
    set_headers, sets = read_csv(DATA / "set_effects.csv")
    new_equipment = generate_equipment(equipment)
    new_skills = generate_skills(skills)
    new_monster_headers, new_monsters = generate_monsters(monsters, new_skills)
    new_sets = generate_sets(sets, new_equipment)
    if write:
        write_csv(DATA / "items_equipment.csv", equipment_headers, new_equipment)
        write_csv(DATA / "skills.csv", skill_headers, new_skills)
        write_csv(DATA / "monsters.csv", new_monster_headers, new_monsters)
        write_csv(DATA / "set_effects.csv", set_headers, new_sets)
        generate_docs()
    return {
        "equipment": len(new_equipment), "skills": len(new_skills),
        "monsters": len(new_monsters), "set_effects": len(new_sets), "written": write,
    }


def generate_docs() -> None:
    docs = ROOT / "docs"
    start_marker = "<!-- BALANCE_V2_GENERATED_START -->"
    end_marker = "<!-- BALANCE_V2_GENERATED_END -->"

    def write_generated(path: Path, generated: str) -> None:
        block = f"{start_marker}\n{generated.rstrip()}\n{end_marker}"
        existing = path.read_text(encoding="utf-8") if path.exists() else ""
        if start_marker in existing and end_marker in existing:
            prefix, remainder = existing.split(start_marker, 1)
            _, suffix = remainder.split(end_marker, 1)
            content = f"{prefix}{block}{suffix}"
        elif existing:
            content = f"{block}\n\n{existing}"
        else:
            content = block + "\n"
        with path.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)

    grade_rows = "\n".join(f"| {grade} | {BALANCE_V2.grade_multipliers[grade]:.2f} |" for grade in GRADE_ORDER)
    slot_rows = "\n".join(f"| {slot} | {weight:.0%} |" for slot, weight in BALANCE_V2.slot_budget_weights.items())
    write_generated(docs / "Balance.md",
        "# Balance V2\n\n이 문서는 `config/balance_v2.py`에서 생성됩니다. 수동으로 수치를 복사하지 마세요.\n\n"
        "- 권장 장비 로그라이크 클리어율: 80~90%\n- 일반/정예/보스 목표 행동 수: 2~3 / 4~6 / 8~12\n"
        "- Lv.100 목표: 약 225런, 36~44시간\n- 피해 변동: ±8%, 관통 상한 50%, 방어 감소 상한 70%\n"
        "- 명중 75~98%, 치명타 70%, 치명타 피해 250%, 드롭 보너스 100% 상한\n",
    )
    write_generated(docs / "Stats.md",
        "# Stats V2\n\n이 문서는 `config/balance_v2.py`에서 생성됩니다.\n\n"
        "`O=max(0,L-50)`\n\n"
        "- HP: `300 + 18×(L-1) + floor(0.20×O²)`\n"
        "- AD/AP: `15 + 2×(L-1) + floor(0.02×O²)`\n"
        "- 물리/마법 방어: `8 + floor(1.05×(L-1)) + floor(0.012×O²)`\n"
        "- 행동률: `clamp(1+(속도-100)/200, 0.75, 1.50)`\n"
        "- 명중률: `clamp(명중-회피, 75%, 98%)`\n"
        "- 피해 감소: `min(70%, 유효방어/(유효방어+100))`\n",
    )
    write_generated(docs / "Items.md",
        "# Items V2\n\n이 문서는 `config/balance_v2.py`와 `data/items_equipment.csv`에서 생성됩니다.\n\n"
        "총 D등급 장비 예산: `B(L)=80+4.2L+0.02L²`\n\n## 등급 배율\n\n| 등급 | 배율 |\n|---|---:|\n"
        f"{grade_rows}\n\n## 슬롯 예산\n\n| 슬롯 | 비중 |\n|---|---:|\n{slot_rows}\n\n"
        "강화는 단계당 기본 스탯 +2%이며 +15에서 +30%입니다. 판매가는 구매가의 25%입니다.\n",
    )
    write_generated(docs / "Monsters.md",
        "# Monsters V2\n\n이 문서는 `config/balance_v2.py`와 `data/monsters.csv`에서 생성됩니다.\n\n"
        "| 유형 | 플레이어 행동 | 몬스터 행동당 최대 HP 피해 |\n|---|---:|---:|\n"
        "| 일반 | 2~3 | 6~9% |\n| 정예 | 4~6 | 9~13% |\n| 보스 | 8~12 | 12~16% |\n\n"
        "파티 HP/공격/보상 배율은 각각 `1+0.75(n-1)`, `1+0.12(n-1)`, `1+0.65(n-1)`입니다.\n"
        "몬스터 데이터는 AP_Defense, Accuracy, Evasion을 명시하며 공격 스킬의 참조 공격력은 0일 수 없습니다.\n",
    )
    _, skills = read_csv(DATA / "skills.csv")
    from service.skill.design_system import audit_skill_ecosystem

    ecosystem = audit_skill_ecosystem(skills)
    role_rows = "\n".join(
        f"| {name} | {count} |" for name, count in ecosystem["roles"].items()
    )
    archetype_rows = "\n".join(
        f"| {name} | {count} |" for name, count in ecosystem["archetypes"].items()
    )
    write_text_lf(docs / "Skills.md",
        "# Skills V2\n\n이 문서는 `data/skills.csv`의 `config.design`에서 생성됩니다.\n\n"
        f"- 설계 계약이 있는 스킬: {ecosystem['skills_designed']}\n"
        f"- 플레이어 획득 가능 스킬: {ecosystem['player_skills_designed']}\n"
        "- 모든 스킬은 역할, 아키타입, 권장 덱 슬롯, 설계 의도, 셋업/피니셔 태그를 갖습니다.\n"
        "- 조건부 피니셔는 같은 플레이어/몬스터 생태계 안에 대응 셋업 스킬이 있어야 합니다.\n\n"
        "## 역할 분포\n\n| 범위:역할 | 개수 |\n|---|---:|\n"
        f"{role_rows}\n\n## 아키타입 분포\n\n| 범위:아키타입 | 개수 |\n|---|---:|\n{archetype_rows}\n",
    )


def audit() -> dict[str, Any]:
    _, equipment = read_csv(DATA / "items_equipment.csv")
    _, skills = read_csv(DATA / "skills.csv")
    _, monsters = read_csv(DATA / "monsters.csv")
    _, sets = read_csv(DATA / "set_effects.csv")
    errors: list[str] = []
    cp_deviation: list[float] = []
    final_cp_violations: list[int] = []
    for row in equipment:
        try:
            slot = classify_slot(row)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        level = int(number(row.get("Lv"), 1))
        target = BALANCE_V2.slot_budget(level, slot)
        cp = equipment_cp(row)
        if cp <= 0:
            errors.append(f"equipment {row['ID']} has non-positive CP")
        cp_deviation.append(abs(cp - target) / max(1.0, target))
        previous_final = 0.0
        for grade in GRADE_ORDER:
            final_cp = equipment_final_cp(row, grade, 15)
            theoretical_max = (
                cp * BALANCE_V2.grade_multipliers[grade]
                * BALANCE_V2.enhancement_stat_multiplier(15)
                * (1.0 + BALANCE_V2.effect_budget_caps[grade])
            )
            if final_cp < previous_final or final_cp > theoretical_max + 1e-6:
                final_cp_violations.append(int(row["ID"]))
                break
            previous_final = final_cp
    zero_attack = []
    skill_outliers: list[int] = []
    passive_contract_errors: list[int] = []
    active_evaluated = 0
    passive_evaluated = 0
    skills_by_id = {int(row["ID"]): row for row in skills}
    from service.dungeon.components import skill_component_register

    from service.item.equipment_component_loader import (
        EQUIPMENT_RUNTIME_CONSUMERS,
        load_equipment_components,
        normalize_equipment_component_config,
    )
    missing_equipment_component_tags: set[str] = set()
    missing_equipment_runtime_consumers: set[str] = set()
    equipment_components_evaluated = 0
    for row in equipment:
        try:
            config = json.loads(row.get("config") or "{}")
            load_equipment_components(config)
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            errors.append(f"equipment {row['ID']} component load failed: {exc}")
            continue
        for raw_component in config.get("components", []):
            component = normalize_equipment_component_config(raw_component)
            tag = str(component.get("tag") or "")
            equipment_components_evaluated += 1
            if tag not in skill_component_register:
                missing_equipment_component_tags.add(tag or "<empty>")
            if tag not in EQUIPMENT_RUNTIME_CONSUMERS:
                missing_equipment_runtime_consumers.add(tag or "<empty>")

    missing_runtime_component_tags: set[str] = set()
    for row in skills:
        try:
            config = json.loads(row.get("config") or "{}")
        except json.JSONDecodeError:
            skill_outliers.append(int(row["ID"]))
            continue
        for component in config.get("components", []):
            tag = str(component.get("tag") or "")
            if tag not in skill_component_register:
                missing_runtime_component_tags.add(tag or "<empty>")
        if row.get("타입") == "passive":
            from service.dungeon.skill import PASSIVE_TAGS

            passive_evaluated += 1
            components = config.get("components", [])
            if not components or any(
                component.get("tag") not in PASSIVE_TAGS
                or not any(key != "tag" for key in component)
                for component in components
            ):
                passive_contract_errors.append(int(row["ID"]))
            continue
        if row.get("타입") != "active":
            continue
        target = 3.75 if row.get("카테고리") == "ultimate" else BALANCE_V2.action_values[_grade_key(row.get("등급", "D"))]
        actual = skill_action_value(row, config)
        active_evaluated += 1
        if abs(actual - target) / target > 0.10:
            skill_outliers.append(int(row["ID"]))
    for row in monsters:
        physical, magical, _ = _monster_skill_channels(row, skills_by_id)
        if (physical and number(row.get("Attack")) <= 0) or (magical and number(row.get("AP_Attack")) <= 0):
            zero_attack.append(int(row["ID"]))
    phase_monsters = 0
    phase_transition_errors: list[int] = []
    for row in monsters:
        try:
            phases = json.loads(row.get("phase_config") or "{}").get("phases", [])
            if phases:
                phase_monsters += 1
            thresholds = [float(phase["hp_threshold"]) for phase in phases]
            if (
                thresholds != sorted(thresholds, reverse=True)
                or len(thresholds) != len(set(thresholds))
                or any(not 0 < value < 1 for value in thresholds)
            ):
                phase_transition_errors.append(int(row["ID"]))
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            phase_transition_errors.append(int(row["ID"]))
    unknown_set_keys: set[str] = set()
    set_budget_usage: dict[str, float] = defaultdict(float)
    from service.combat.stats import ModifierBundle
    for row in sets:
        try:
            config = json.loads(row["효과config"])
            ModifierBundle.from_mapping(config, strict=True, percentage_points=True)
            ModifierBundle.assert_runtime_consumers(set(config))
            set_budget_usage[row["세트이름"]] += sum(abs(number(value)) for value in config.values()) / 100.0
        except (ValueError, json.JSONDecodeError) as exc:
            unknown_set_keys.add(str(exc))
    from service.skill.design_system import audit_skill_ecosystem

    ecosystem = audit_skill_ecosystem(skills)
    result = {
        "profile": BALANCE_V2.version,
        "counts": {"equipment": len(equipment), "skills": len(skills), "monsters": len(monsters), "sets": len({r['세트이름'] for r in sets})},
        "equipment_max_cp_deviation": max(cp_deviation, default=0.0),
        "equipment_outside_10_percent": sum(value > 0.10 for value in cp_deviation),
        "final_equipment_cp_violations": sorted(set(final_cp_violations)),
        "zero_attack_monsters": zero_attack,
        "skills_evaluated": active_evaluated + passive_evaluated,
        "active_action_values_evaluated": active_evaluated,
        "passive_contracts_evaluated": passive_evaluated,
        "skill_action_value_outliers": skill_outliers,
        "passive_contract_errors": passive_contract_errors,
        "missing_runtime_component_tags": sorted(missing_runtime_component_tags),
        "equipment_components_evaluated": equipment_components_evaluated,
        "missing_equipment_component_tags": sorted(missing_equipment_component_tags),
        "missing_equipment_runtime_consumers": sorted(missing_equipment_runtime_consumers),
        "unknown_set_effects": sorted(unknown_set_keys),
        "set_budget_violations": sorted(name for name, usage in set_budget_usage.items() if usage > 0.1801),
        "phase_monsters": phase_monsters,
        "phase_transition_errors": sorted(set(phase_transition_errors)),
        "skill_ecosystem": ecosystem,
        "errors": errors,
    }
    result["passed"] = (
        not errors and not zero_attack and not unknown_set_keys and not skill_outliers and not passive_contract_errors
        and not missing_runtime_component_tags and not missing_equipment_component_tags
        and not missing_equipment_runtime_consumers and not result["phase_transition_errors"]
        and not result["set_budget_violations"] and result["equipment_outside_10_percent"] == 0
        and not result["final_equipment_cp_violations"]
        and ecosystem["passed"]
    )
    return result


def simulate(iterations: int, seed: int = 20260814) -> dict[str, Any]:
    from tools.headless_balance_runtime import run_runtime_simulation

    runtime = run_runtime_simulation(iterations, seed)
    results = runtime["levels"]
    economy = runtime["economy"]
    targets_passed = True
    for level_results in results.values():
        clear_rates, previous_rates, elite_rates, common_actions = [], [], [], []
        for values in level_results.values():
            clear_rates.append(values["clear_rate"])
            previous_rates.append(values["previous_gear_clear_rate"])
            elite_rates.append(values["elite_route_clear_rate"])
            common_actions.append(values["common_actions"])
            # Monte Carlo and discrete action counts need a small measurement
            # margin around the published 2-3 / 4-6 / 8-12 envelopes.
            targets_passed &= 1.85 <= values["common_actions"] <= 3.15
            targets_passed &= 3.80 <= values["elite_actions"] <= 6.70
            targets_passed &= 7.50 <= values["boss_actions"] <= 12.50
        targets_passed &= 0.80 <= median(clear_rates) <= 0.90
        targets_passed &= 0.60 <= median(previous_rates) <= 0.75
        targets_passed &= 0.55 <= median(elite_rates) <= 0.70
        targets_passed &= max(clear_rates) - min(clear_rates) <= 0.10
    targets_passed &= 36 <= economy["median_hours_to_100"] <= 44
    targets_passed &= 2 <= economy["meaningful_replacement_runs"] <= 4
    targets_passed &= 0.65 <= economy["gold_spend_ratio"] <= 0.80
    targets_passed &= economy["median_level_50_grade"] == "A"
    targets_passed &= economy["median_level_70_grade"] == "S"
    targets_passed &= economy["median_level_90_grade"] == "SS"
    targets_passed &= economy["level_100_ss_slots"] == 9
    targets_passed &= 2 <= economy["level_100_sss_items"] <= 3
    return {
        "iterations_per_build": iterations,
        "engine": runtime["engine"],
        "combat_iterations_per_build": runtime["combat_iterations_per_build"],
        "economy_seasons": runtime["economy_seasons"],
        "levels": results,
        "target_runs_to_100": economy["target_runs"],
        "median_hours_to_100": economy["median_hours_to_100"],
        "economy": economy,
        "targets_passed": bool(targets_passed),
    }


def report(output: Path, iterations: int, simulation_file: Path | None = None) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    audit_result = audit()
    simulation = (
        json.loads(simulation_file.read_text(encoding="utf-8-sig"))
        if simulation_file else simulate(iterations)
    )
    payload = {
        "passed": bool(audit_result["passed"] and simulation["targets_passed"]),
        "audit": audit_result,
        "simulation": simulation,
    }
    write_text_lf(output / "balance_v2_report.json", json.dumps(payload, ensure_ascii=False, indent=2))
    lines = [
        "# CUHABot Balance V2 Report", "", f"- Profile: `{BALANCE_V2.version}`",
        f"- Audit passed: `{audit_result['passed']}`",
        f"- Equipment: {audit_result['counts']['equipment']}",
        f"- Skills: {audit_result['counts']['skills']}",
        f"- Monsters: {audit_result['counts']['monsters']}",
        f"- Sets: {audit_result['counts']['sets']}",
        f"- Median Lv.100 time: {simulation['median_hours_to_100']:.2f} hours", "",
        f"- Simulation targets passed: `{simulation['targets_passed']}`",
        f"- Meaningful replacement interval: {simulation['economy']['meaningful_replacement_runs']:.2f} runs",
        f"- Gold spend ratio: {simulation['economy']['gold_spend_ratio']:.2%}", "",
        "## Reference clear rates", "",
        "| Level | Build | Normal | Previous gear | Elite route | Common/Elite/Boss actions |",
        "|---:|---|---:|---:|---:|---:|",
    ]
    for level, builds in simulation["levels"].items():
        for build, values in builds.items():
            lines.append(
                f"| {level} | {build} | {values['clear_rate']:.2%} | "
                f"{values['previous_gear_clear_rate']:.2%} | {values['elite_route_clear_rate']:.2%} | "
                f"{values['common_actions']:.2f}/{values['elite_actions']:.2f}/{values['boss_actions']:.2f} |"
            )
    write_text_lf(output / "balance_v2_report.md", "\n".join(lines) + "\n")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("audit")
    generate_parser = subparsers.add_parser("generate")
    generate_parser.add_argument("--write", action="store_true")
    simulate_parser = subparsers.add_parser("simulate")
    simulate_parser.add_argument("--iterations", type=int, default=100_000)
    report_parser = subparsers.add_parser("report")
    report_parser.add_argument("--iterations", type=int, default=100_000)
    report_parser.add_argument("--output", type=Path, default=ROOT / "reports" / "balance_v2")
    report_parser.add_argument("--simulation-file", type=Path)
    args = parser.parse_args()
    if args.command == "audit":
        result = audit()
    elif args.command == "generate":
        result = generate(args.write)
    elif args.command == "simulate":
        result = simulate(args.iterations)
    else:
        result = report(args.output, args.iterations, args.simulation_file)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not isinstance(result, dict) or result.get("passed", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
