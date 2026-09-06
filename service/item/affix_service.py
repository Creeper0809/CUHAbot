"""Authored V4 equipment affix generation, persistence, and runtime overlay."""
from __future__ import annotations

import random
from dataclasses import dataclass

from config.itemization_v4 import (
    AFFIX_BY_ID, AFFIX_DEFINITIONS, MYTHIC_T1_WEIGHT, affix_count, tier_range,
)
from models import EquipmentAffixDefinition, UserEquipmentAffix
from models.user_equipment import EquipmentSlot
from service.combat.stats import ModifierBundle


SLOT_KEYS = {
    EquipmentSlot.WEAPON: "weapon", EquipmentSlot.SUB_WEAPON: "sub_weapon",
    EquipmentSlot.HELMET: "helmet", EquipmentSlot.ARMOR: "armor",
    EquipmentSlot.GLOVES: "gloves", EquipmentSlot.BOOTS: "boots",
    EquipmentSlot.NECKLACE: "necklace", EquipmentSlot.RING1: "ring1",
    EquipmentSlot.RING2: "ring2",
}
EQUIP_POS_SLOT_KEYS = {
    1: "helmet", 2: "armor", 3: "boots", 4: "weapon", 5: "sub_weapon",
    6: "gloves", 7: "necklace", 8: "ring1", 9: "ring2",
}


@dataclass(frozen=True)
class RolledAffix:
    affix_id: str
    tier: int
    value: float
    quality_percentile: int


async def sync_affix_definitions() -> None:
    for definition in AFFIX_DEFINITIONS:
        await EquipmentAffixDefinition.update_or_create(
            id=definition.id,
            defaults={
                "name": definition.name, "family": definition.family,
                "effect_group": definition.effect_group,
                "allowed_slots": list(definition.allowed_slots),
                "setup_tags": list(definition.setup_tags),
                "payoff_tags": list(definition.payoff_tags),
                "runtime_key": definition.runtime_key,
                "tier_values": {str(k): list(v) for k, v in definition.tier_values.items()},
                "weight": definition.weight,
            },
        )


def _choose_tier(grade: int, rng: random.Random) -> int:
    limits = tier_range(grade)
    if not limits:
        raise ValueError(f"grade {grade} cannot roll affixes")
    low, high = limits
    tiers = list(range(low, high - 1, -1))
    weights = [MYTHIC_T1_WEIGHT if grade == 8 and tier == 1 else 1.0 for tier in tiers]
    return rng.choices(tiers, weights=weights, k=1)[0]


def roll_affixes(grade: int, slot_key: str, rng: random.Random | None = None) -> list[RolledAffix]:
    rng = rng or random.Random()
    count = affix_count(grade)
    if count <= 0:
        return []
    candidates = [definition for definition in AFFIX_DEFINITIONS if slot_key in definition.allowed_slots]
    selected = []
    used_groups: set[str] = set()
    while len(selected) < count:
        pool = [definition for definition in candidates if definition.effect_group not in used_groups]
        if not pool:
            raise ValueError(f"not enough compatible affix groups for {slot_key}")
        definition = rng.choices(pool, weights=[entry.weight for entry in pool], k=1)[0]
        tier = _choose_tier(grade, rng)
        minimum, maximum = definition.tier_values[tier]
        raw = rng.uniform(minimum, maximum)
        value = round(raw, 2)
        quality = 100 if maximum == minimum else round((raw - minimum) / (maximum - minimum) * 100)
        selected.append(RolledAffix(definition.id, tier, value, quality))
        used_groups.add(definition.effect_group)
    return selected


def roll_replacement_affix(
    grade: int, slot_key: str, excluded_groups: set[str], rng: random.Random | None = None,
) -> RolledAffix:
    rng = rng or random.Random()
    candidates = [
        definition for definition in AFFIX_DEFINITIONS
        if slot_key in definition.allowed_slots and definition.effect_group not in excluded_groups
    ]
    if not candidates:
        raise ValueError("no compatible affix remains after preserving effect groups")
    definition = rng.choices(candidates, weights=[entry.weight for entry in candidates], k=1)[0]
    tier = _choose_tier(grade, rng)
    minimum, maximum = definition.tier_values[tier]
    raw = rng.uniform(minimum, maximum)
    quality = 100 if maximum == minimum else round((raw - minimum) / (maximum - minimum) * 100)
    return RolledAffix(definition.id, tier, round(raw, 2), quality)


async def persist_affixes(inventory_item, rolled: list[RolledAffix], *, using_db=None) -> None:
    query = UserEquipmentAffix.filter(inventory_item=inventory_item)
    if using_db:
        query = query.using_db(using_db)
    await query.delete()
    for position, affix in enumerate(rolled):
        await UserEquipmentAffix.create(
            inventory_item=inventory_item, affix_definition_id=affix.affix_id,
            position=position, tier=affix.tier, value=affix.value,
            quality_percentile=affix.quality_percentile,
            using_db=using_db,
        )


async def ensure_instance_affixes(
    inventory_item, equip_pos: int, rng: random.Random | None = None, *, using_db=None,
) -> list[UserEquipmentAffix]:
    query = UserEquipmentAffix.filter(inventory_item=inventory_item)
    if using_db:
        query = query.using_db(using_db)
    existing = await query.prefetch_related("affix_definition")
    if existing or affix_count(inventory_item.instance_grade) == 0:
        return list(existing)
    slot_key = EQUIP_POS_SLOT_KEYS.get(equip_pos)
    if not slot_key:
        raise ValueError(f"unsupported equipment position: {equip_pos}")
    await persist_affixes(
        inventory_item, roll_affixes(inventory_item.instance_grade, slot_key, rng),
        using_db=using_db,
    )
    query = UserEquipmentAffix.filter(inventory_item=inventory_item)
    if using_db:
        query = query.using_db(using_db)
    return list(await query.prefetch_related("affix_definition"))


async def get_affix_bundle(inventory_item) -> ModifierBundle:
    rows = await UserEquipmentAffix.filter(inventory_item=inventory_item).prefetch_related("affix_definition")
    bundle = ModifierBundle()
    direct = {"attack", "ap_attack", "ad_defense", "ap_defense", "speed", "critical_rate", "critical_damage", "drop_rate"}
    aliases = {"crit_rate": "critical_rate", "crit_damage": "critical_damage"}
    for row in rows:
        key = aliases.get(row.affix_definition.runtime_key, row.affix_definition.runtime_key)
        percentage_points = key not in direct
        bundle.merge(ModifierBundle.from_mapping({key: row.value}, percentage_points=percentage_points))
    return bundle


async def get_affix_components(inventory_item) -> list:
    from service.item.equipment_component_loader import load_equipment_components

    rows = await UserEquipmentAffix.filter(inventory_item=inventory_item).prefetch_related("affix_definition")
    components = []
    for row in rows:
        definition = AFFIX_BY_ID.get(row.affix_definition_id)
        if definition:
            components.extend(load_equipment_components(definition.runtime_config(row.value)))
    return components


def format_affix(row) -> str:
    definition = AFFIX_BY_ID.get(row.affix_definition_id)
    name = definition.name if definition else row.affix_definition_id
    return f"T{row.tier} {name} +{row.value:g} · 품질 {row.quality_percentile}%"


LEGACY_AFFIX_MAP = {
    "lifesteal": "leech", "crit_rate": "precision", "crit_damage": "brutality",
    "armor_pen": "sunder", "bonus_hp_pct": "vitality", "bonus_speed_pct": "haste",
}


def _legacy_roll(grade: int, effect: dict) -> RolledAffix | None:
    affix_id = LEGACY_AFFIX_MAP.get(str(effect.get("type", "")))
    definition = AFFIX_BY_ID.get(affix_id or "")
    limits = tier_range(grade)
    if not definition or not limits:
        return None
    value = float(effect.get("value", 0) or 0)
    allowed = list(range(limits[0], limits[1] - 1, -1))
    tier = min(allowed, key=lambda candidate: abs(sum(definition.tier_values[candidate]) / 2 - value))
    minimum, maximum = definition.tier_values[tier]
    quality = 100 if maximum == minimum else round(max(0.0, min(1.0, (value - minimum) / (maximum - minimum))) * 100)
    return RolledAffix(affix_id, tier, value, quality)


async def backfill_existing_instances() -> dict[str, int]:
    """Backfill existing equipment without changing legacy rolled values."""
    import random
    from models import EquipmentItem, EquipmentProvenance, UserInventory

    equipment = {row.item_id: row for row in await EquipmentItem.all()}
    rows = await UserInventory.filter(item_id__in=list(equipment)).all()
    migrated = generated = provenance_count = 0
    for row in rows:
        if not await UserEquipmentAffix.exists(inventory_item=row):
            legacy = [value for value in (_legacy_roll(row.instance_grade, effect) for effect in (row.special_effects or [])) if value]
            if legacy:
                unique = []
                groups = set()
                for value in legacy:
                    group = AFFIX_BY_ID[value.affix_id].effect_group
                    if group not in groups and len(unique) < affix_count(row.instance_grade):
                        unique.append(value); groups.add(group)
                await persist_affixes(row, unique)
                migrated += 1
            elif affix_count(row.instance_grade):
                await ensure_instance_affixes(row, equipment[row.item_id].equip_pos, random.Random(row.id))
                generated += 1
        _, created = await EquipmentProvenance.get_or_create(
            inventory_item=row,
            defaults={"source_type": "legacy", "source_key": equipment[row.item_id].acquisition_source or "", "original_owner_id": row.user_id},
        )
        provenance_count += int(created)
    return {"legacy_mapped": migrated, "generated": generated, "provenance": provenance_count}
