"""Conservative automatic salvage with mandatory protection rules."""
from __future__ import annotations

from models import (
    EquipmentItem, UserBuildPresetItem, UserEquipment, UserEquipmentAffix,
    UserFarmProgress, UserInventory, UserLootRule,
)
from service.item.progression_service import salvage_equipment


async def should_auto_salvage(user, inventory_item: UserInventory) -> tuple[bool, str]:
    rule = await UserLootRule.get_or_none(user=user)
    if not rule or not rule.enabled:
        return False, "disabled"
    if inventory_item.instance_grade >= 7 or inventory_item.enhancement_level >= 10:
        return False, "high_grade_or_enhancement"
    if inventory_item.is_locked or await UserEquipment.exists(inventory_item=inventory_item):
        return False, "locked_or_equipped"
    if await UserBuildPresetItem.exists(inventory_item=inventory_item):
        return False, "preset"
    if inventory_item.item_id in set(rule.excluded_item_ids or []):
        return False, "excluded"
    if await UserFarmProgress.filter(user=user, target_item_id=inventory_item.item_id).exists():
        return False, "farm_target"
    if await UserInventory.filter(user=user, item_id=inventory_item.item_id).count() <= 1:
        return False, "first_copy"
    equipment = await EquipmentItem.get_or_none(item_id=inventory_item.item_id)
    if not equipment:
        return False, "not_equipment"
    if rule.slots and equipment.equip_pos not in set(int(value) for value in rule.slots):
        return False, "slot_filtered"
    if inventory_item.instance_grade > rule.max_grade:
        return False, "grade_kept"
    if rule.minimum_affix_tier is not None:
        rows = await UserEquipmentAffix.filter(inventory_item=inventory_item)
        if any(row.tier <= rule.minimum_affix_tier for row in rows):
            return False, "valuable_affix"
    return True, "matched"


async def process_auto_salvage(user, inventory_item: UserInventory) -> dict | None:
    matched, _ = await should_auto_salvage(user, inventory_item)
    if not matched:
        return None
    return await salvage_equipment(user, inventory_item.id, f"auto-salvage:{inventory_item.id}", confirmed=True)
