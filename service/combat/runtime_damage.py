"""Shared Balance V2 damage path for non-standard skill components.

AttackComponent has richer animation/event handling, while combo, consume, DoT
and self-destruct historically sent raw coefficients straight to HP.  This
module gives those effects the same defense curve, penetration caps, elemental
matchup, runtime modifiers and incoming-damage pipeline.
"""
from __future__ import annotations

from dataclasses import dataclass

from config import DAMAGE, get_attribute_multiplier
from models import UserStatEnum
from service.combat.damage_calculator import DamageCalculator, DamageResult
from service.dungeon.damage_pipeline import DamageEvent, process_incoming_damage
from service.dungeon.status import get_damage_taken_multiplier


@dataclass(frozen=True)
class RuntimeDamageResult:
    calculation: DamageResult
    event: DamageEvent


def deal_runtime_damage(
    attacker,
    target,
    raw_damage: float,
    *,
    is_physical: bool,
    attribute: str = "무속성",
    penetration: float = 0.0,
    force_critical: bool = False,
    can_critical: bool = False,
) -> RuntimeDamageResult:
    attacker_stats = attacker.get_stat() if hasattr(attacker, "get_stat") else {}
    target_stats = target.get_stat() if hasattr(target, "get_stat") else {}
    defense_key = UserStatEnum.DEFENSE if is_physical else UserStatEnum.AP_DEFENSE
    defense = target_stats.get(
        defense_key,
        getattr(target, "defense" if is_physical else "ap_defense", 0),
    )

    multiplier = get_attribute_multiplier(attribute, getattr(target, "attribute", "무속성"))
    multiplier *= get_damage_taken_multiplier(target)
    multiplier *= float(getattr(attacker, "_roguelike_effect_multiplier", 1.0) or 1.0)

    modifier = getattr(attacker, "modifier_bundle", None)
    if modifier is not None:
        multiplier *= 1.0 + (
            modifier.physical_damage_pct if is_physical else modifier.magical_damage_pct
        )
        multiplier *= 1.0 + {
            "화염": modifier.fire_damage_pct,
            "물": modifier.water_damage_pct,
            "수속성": modifier.water_damage_pct,
            "번개": modifier.lightning_damage_pct,
            "신성": modifier.holy_damage_pct,
            "암흑": modifier.dark_damage_pct,
        }.get(attribute, 0.0)
        penetration += modifier.armor_penetration if is_physical else modifier.magic_penetration

    crit_rate = 0.0
    if can_critical or force_critical:
        crit_rate = attacker_stats.get(UserStatEnum.CRITICAL_RATE, 5) / 100.0
    crit_multiplier = attacker_stats.get(UserStatEnum.CRITICAL_DAMAGE, 150) / 100.0
    kwargs = {
        "skill_multiplier": 1.0,
        "critical_rate": crit_rate,
        "critical_multiplier": crit_multiplier,
        "force_critical": force_critical,
        "attribute_multiplier": multiplier,
    }
    if is_physical:
        calculation = DamageCalculator.calculate_physical_damage(
            attack=max(1, int(raw_damage)),
            defense=defense,
            armor_penetration=min(DAMAGE.MAX_ARMOR_PENETRATION, penetration),
            **kwargs,
        )
    else:
        calculation = DamageCalculator.calculate_magical_damage(
            ap_attack=max(1, int(raw_damage)),
            ap_defense=defense,
            magic_penetration=min(DAMAGE.MAX_ARMOR_PENETRATION, penetration),
            **kwargs,
        )
    event = process_incoming_damage(
        target,
        calculation.damage,
        attacker=attacker,
        attribute=attribute,
    )
    return RuntimeDamageResult(calculation=calculation, event=event)
