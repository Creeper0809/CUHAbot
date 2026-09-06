"""Verify the inventory/deck repair against an isolated PostgreSQL copy.

The command intentionally imports command/view cache references before loading
static data, matching the bot's real cold-start order.  It also saves an owned
skill through the inventory deck editor and checks the persisted slot/count.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tortoise import Tortoise

from cogs.dungeon_command import skill_cache_by_id as command_skill_cache
from models import Item, User
from models.repos import static_cache
from models.user_inventory import UserInventory
from models.user_owned_skill import UserOwnedSkill
from models.user_skill_deck import UserSkillDeck
from resources.item_emoji import ItemType
from scripts.migrate_roguelike_reward_system import init_db
from service.player.starter_recovery import ensure_account
from service.skill.skill_ownership_service import SkillOwnershipService
from views.inventory.components import ItemSelectDropdown
from views.inventory.list_view import InventoryView
from views.inventory.select_view import (
    InventorySelectButton,
    InventorySelectView,
    _open_inventory_skill_deck,
)
from views.skill_deck import SkillDeckView
from views.skill_deck.main import skill_cache_by_id as deck_view_skill_cache


async def main(output: str) -> None:
    table = os.environ.get("DATABASE_TABLE", "")
    if not table.endswith("_beginner_check"):
        raise RuntimeError("Only the restored isolated database is allowed")

    command_ref = command_skill_cache
    deck_ref = deck_view_skill_cache
    await init_db()
    test_discord_id = 890000000000000105
    try:
        await static_cache.load_static_data()
        assert command_ref is deck_ref is static_cache.skill_cache_by_id
        assert len(command_ref) == 647 and {1001, 8105}.issubset(command_ref)
        await User.filter(discord_id=test_discord_id).delete()

        material = Item(
            id=7002,
            name="늑대 가죽",
            description="가죽 장비 제작 재료",
            type=ItemType.ETC,
        )
        material_row = SimpleNamespace(
            item=material,
            quantity=2,
            enhancement_level=0,
            instance_grade=0,
            is_blessed=False,
            is_cursed=False,
        )
        material_view = InventoryView(SimpleNamespace(id=test_discord_id), None, [material_row])
        material_view.current_tab = ItemType.ETC
        material_view.inventory = material_view._filter_and_sort()
        material_view._update_select_button()
        material_payload = material_view.create_embed().to_dict()
        assert "재료" in json.dumps(material_payload, ensure_ascii=False)
        assert not any(isinstance(child, InventorySelectButton) for child in material_view.children)
        material_view.stop()

        user = await ensure_account(test_discord_id, "인벤토리 덱 검증 계정")
        await SkillOwnershipService.add_skill(user, 8105, 1)

        potion_row = await UserInventory.create(user=user, item_id=8001, quantity=2)
        await UserInventory.create(user=user, item_id=1001, quantity=1, instance_grade=1)
        await UserInventory.create(user=user, item_id=7002, quantity=1)
        await potion_row.fetch_related("item")
        category_list = InventoryView(SimpleNamespace(id=test_discord_id), user, [potion_row])
        category_selector = InventorySelectView(
            SimpleNamespace(id=test_discord_id), user, category_list
        )
        await category_selector.refresh_items()
        category_dropdown = next(
            child for child in category_selector.children if isinstance(child, ItemSelectDropdown)
        )
        assert {row.item.type for row in category_selector.inventory} == {ItemType.CONSUME}
        assert [option.value for option in category_dropdown.options] == [str(potion_row.id)]
        category_selector.stop()
        category_list.stop()

        skill_list_view = InventoryView(
            SimpleNamespace(id=test_discord_id),
            user,
            [],
            await SkillOwnershipService.get_all_owned_skills(user),
        )
        skill_list_view.current_tab = ItemType.SKILL
        skill_list_view.inventory = skill_list_view._filter_and_sort()
        skill_list_view._update_select_button()
        action = next(child for child in skill_list_view.children if isinstance(child, InventorySelectButton))
        assert action.label == "스킬 장착"
        assert "보유한 스킬이 없습니다" not in json.dumps(
            skill_list_view.create_embed().to_dict(), ensure_ascii=False
        )
        skill_list_view.stop()

        async def save_owned_skill(view: SkillDeckView) -> None:
            view.current_deck[0] = 8105
            view.changes_made = True
            view.saved = True

        interaction = SimpleNamespace(
            user=SimpleNamespace(id=test_discord_id),
            response=SimpleNamespace(send_message=AsyncMock()),
            original_response=AsyncMock(return_value=SimpleNamespace()),
            followup=SimpleNamespace(send=AsyncMock()),
        )
        with patch.object(SkillDeckView, "wait", save_owned_skill):
            await _open_inventory_skill_deck(interaction, user)

        slot = await UserSkillDeck.get(user=user, slot_index=0)
        owned = await UserOwnedSkill.get(user=user, skill_id=8105)
        assert slot.skill_id == 8105
        assert owned.quantity == 1 and owned.equipped_count == 1

        result = {
            "passed": True,
            "database": table,
            "cold_start_cache_size": len(command_ref),
            "material_direct_use_hidden": True,
            "inventory_skill_action": action.label,
            "consumable_selector_item_count": len(category_dropdown.options),
            "consumable_selector_categories": [ItemType.CONSUME.value],
            "saved_skill_id": slot.skill_id,
            "saved_equipped_count": owned.equipped_count,
        }
        Path(output).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False))
    finally:
        await User.filter(discord_id=test_discord_id).delete()
        await Tortoise.close_connections()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="inventory-deck-verified.json")
    args = parser.parse_args()
    asyncio.run(main(args.output))
