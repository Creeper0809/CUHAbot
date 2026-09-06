"""Load equipment effects through the same component registry as skills.

Equipment data predates the canonical passive component names.  The aliases
below are an explicit migration boundary; silently dropping an unknown effect
would make an item lie to the player, so loading is strict by default.
"""

from __future__ import annotations

from copy import deepcopy
import inspect
from typing import Any


EQUIPMENT_COMPONENT_ALIASES: dict[str, str] = {
    "damage_reflection": "passive_damage_reflection",
    "debuff_reduction": "passive_debuff_reduction",
    "status_immunity": "passive_status_immunity",
    # The game has no mana resource; legacy mana-efficiency items therefore
    # reduce the ultimate cooldown, which is the real reusable resource.
    "mana_cost_reduction": "cooldown_reduction",
}

STATUS_TYPE_ALIASES: dict[str, str] = {
    "기절": "stun",
    "동결": "freeze",
    "속박": "root",
    "침묵": "silence",
    "마비": "paralyze",
    "둔화": "slow",
    "중독": "poison",
    "화상": "burn",
    "출혈": "bleed",
    # Critical immunity is consumed by the hit pipeline rather than the
    # status-effect registry.
    "치명타": "critical",
}

# Every canonical equipment tag must name the executable subsystem that uses
# it.  This registry is audited against all 486 rows during CI.
EQUIPMENT_RUNTIME_CONSUMERS: dict[str, str] = {
    "passive_buff": "equipment_stats",
    "on_attack_proc": "equipment_manager.on_attack",
    "skill_damage_boost": "outgoing_damage",
    "skill_type_damage_boost": "outgoing_damage",
    "conditional_damage_boost": "outgoing_damage",
    "race_bonus": "outgoing_damage",
    "random_damage_variance": "outgoing_damage",
    "attribute_damage_boost": "outgoing_damage",
    "on_kill_stack": "equipment_manager.on_kill",
    "combat_stat_growth": "equipment_manager.passives",
    "cooldown_reduction": "ultimate_cooldown",
    "random_attribute": "outgoing_damage",
    "buff_duration_extension": "buff_duration",
    "heal_blocking": "equipment_manager.on_attack",
    "regeneration": "equipment_manager.turn_start",
    "revive": "combat_revive",
    "extra_attack": "equipment_manager.on_attack",
    "first_strike": "action_gauge",
    "on_kill_heal": "equipment_manager.on_kill",
    "durability_bonus": "incoming_damage",
    "special_drop_bonus": "drop_handler",
    "enhancement_bonus": "enhancement_service",
    "counter_attack": "equipment_manager.on_damaged",
    "exploration_speed": "encounter_processor",
    "trap_detection": "encounter_types",
    "action_prediction": "hit_and_damage_pipeline",
    "conditional_stat_bonus": "outgoing_damage",
    "passive_debuff_reduction": "status_pipeline",
    "passive_status_immunity": "status_pipeline",
    "passive_element_immunity": "damage_pipeline",
    "passive_element_resistance": "damage_pipeline",
    "damage_delay": "incoming_damage",
    "passive_damage_reflection": "damage_pipeline",
    "thorns_damage": "equipment_manager.on_damaged",
    "dungeon_specific_buff": "equipment_manager.combat_start",
    "ally_protection": "incoming_damage",
    "sacrifice_effect": "equipment_manager.combat_start",
    "periodic_invincibility": "damage_pipeline",
    "skill_refresh": "skill_draw",
    "skill_reroll": "skill_draw",
    "double_draw": "skill_draw",
    "hp_cost_empower": "damage_event",
    "defense_to_attack": "equipment_manager.combat_lifecycle",
    "consecutive_skill_bonus": "skill_and_damage_event",
    "skill_variety_bonus": "skill_and_damage_event",
    "turn_count_empower": "turn_and_damage_event",
    "accumulation": "turn_and_damage_event",
}


def assert_equipment_runtime_consumer(tag: str) -> None:
    if tag not in EQUIPMENT_RUNTIME_CONSUMERS:
        raise UnknownEquipmentComponentError(
            f"equipment component has no declared runtime consumer: {tag}"
        )


class UnknownEquipmentComponentError(ValueError):
    """Raised when an equipment effect has no executable runtime component."""


def normalize_equipment_component_config(config: dict[str, Any]) -> dict[str, Any]:
    """Return canonical component config without mutating static item data."""
    result = deepcopy(config)
    original_tag = str(result.get("tag") or "")
    tag = EQUIPMENT_COMPONENT_ALIASES.get(original_tag, original_tag)
    result["tag"] = tag

    if original_tag == "damage_reflection":
        result["reflect_percent"] = result.get(
            "reflect_percent", result.get("reflection_percent", 0.0)
        )
    elif original_tag == "status_immunity":
        raw_types = result.get("immune_types", result.get("immune_statuses", []))
        result["immune_types"] = [
            STATUS_TYPE_ALIASES.get(str(value), str(value)) for value in raw_types
        ]
        result.setdefault("immune_all", False)
    elif original_tag == "mana_cost_reduction":
        result["cooldown_reduction"] = result.get(
            "cooldown_reduction", result.get("reduction_percent", 0.0)
        )
    elif original_tag == "buff_duration_extension":
        multiplier = float(result.get("duration_multiplier", 1.0) or 1.0)
        result["duration_bonus"] = result.get("duration_bonus", max(0.0, multiplier - 1.0))

    return result


def load_equipment_components(config: dict, *, strict: bool = True) -> list[Any]:
    """Create executable components from one equipment config.

    Unknown or malformed effects fail closed.  ``strict=False`` exists only
    for migration/reporting tools that need to collect all bad rows at once.
    """
    if not config or "components" not in config:
        return []

    # Importing the package populates the decorator-backed registry even when
    # this loader is called from an out-of-combat service.
    import service.dungeon.components  # noqa: F401
    from service.dungeon.components.base import skill_component_register

    components: list[Any] = []
    for raw_config in config.get("components", []):
        component_config = normalize_equipment_component_config(raw_config)
        tag = str(component_config.get("tag") or "")
        if not tag:
            if strict:
                raise UnknownEquipmentComponentError("equipment component tag is empty")
            continue

        component_class = skill_component_register.get(tag)
        if component_class is None:
            if strict:
                raise UnknownEquipmentComponentError(
                    f"equipment component has no runtime consumer: {tag}"
                )
            continue

        assert_equipment_runtime_consumer(tag)

        component = component_class()
        parameters = inspect.signature(component.apply_config).parameters
        if "priority" in parameters:
            component.apply_config(component_config, "Equipment", priority=0)
        else:
            component.apply_config(component_config, "Equipment")
        component._tag = tag
        component._source_tag = str(raw_config.get("tag") or tag)
        component._raw_config = component_config
        components.append(component)

    return components


def get_equipment_passive_stats(components: list[Any]) -> dict[str, float]:
    """Aggregate flat/passive equipment stats in the canonical units."""
    totals = {
        "attack": 0,
        "ap_attack": 0,
        "ad_defense": 0,
        "ap_defense": 0,
        "speed": 0,
        "crit_rate": 0.0,
        "crit_damage": 0.0,
        "lifesteal": 0.0,
        "drop_rate": 0.0,
        "evasion": 0.0,
        "accuracy": 0.0,
        "block_rate": 0.0,
        "armor_pen": 0.0,
        "magic_pen": 0.0,
        "fire_resist": 0.0,
        "ice_resist": 0.0,
        "lightning_resist": 0.0,
        "water_resist": 0.0,
        "holy_resist": 0.0,
        "dark_resist": 0.0,
        "fire_damage": 0.0,
        "ice_damage": 0.0,
        "lightning_damage": 0.0,
        "water_damage": 0.0,
        "holy_damage": 0.0,
        "dark_damage": 0.0,
        "exp_bonus": 0.0,
        "bonus_hp_pct": 0.0,
        "bonus_speed_pct": 0.0,
        "bonus_all_stats_pct": 0.0,
    }

    for component in components:
        if getattr(component, "_tag", "") != "passive_buff":
            continue
        for key, value in getattr(component, "_raw_config", {}).items():
            if key in totals:
                totals[key] += value
    return totals


async def load_user_equipment_components(user) -> list[Any]:
    """Load equipped effects for out-of-combat services such as enhancement."""
    from models.equipment_item import EquipmentItem
    from models.user_equipment import UserEquipment

    equipped = await UserEquipment.filter(user=user).prefetch_related(
        "inventory_item__item"
    )
    result: list[Any] = []
    for row in equipped:
        equipment = await EquipmentItem.get_or_none(item=row.inventory_item.item)
        if equipment and equipment.config:
            result.extend(load_equipment_components(equipment.config))
        from service.item.affix_service import get_affix_components
        result.extend(await get_affix_components(row.inventory_item))
    return result
