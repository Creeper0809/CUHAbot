from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from models import Item, User
from models.user_inventory import UserInventory
from models.user_owned_skill import UserOwnedSkill
from models.user_skill_deck import UserSkillDeck
from resources.item_emoji import ItemType
from service.player.starter_recovery import ensure_account
from service.skill.skill_ownership_service import SkillOwnershipService
from tools.beginner_runtime import seed_fixture
from views.inventory.components import ItemSelectDropdown
from views.inventory.list_view import InventoryView
from views.inventory.select_view import (
    InventorySelectView,
    InventorySelectButton,
    InventoryUseButton,
    QuantityButton,
    _open_inventory_skill_deck,
)
from views.skill_deck import SkillDeckView


@pytest.mark.asyncio
async def test_static_cache_reload_preserves_early_import_references():
    from tortoise import Tortoise
    from models.repos import static_cache
    from cogs.dungeon_command import skill_cache_by_id as command_skills
    from views.skill_deck.main import skill_cache_by_id as deck_skills
    from views.user_info_view import item_cache as info_items

    skill_ref = static_cache.skill_cache_by_id
    item_ref = static_cache.item_cache
    await seed_fixture()
    try:
        assert skill_ref is command_skills is deck_skills is static_cache.skill_cache_by_id
        assert item_ref is info_items is static_cache.item_cache
        assert len(deck_skills) == 647 and 1001 in deck_skills and 8105 in deck_skills
        counts = (len(static_cache.spawn_info), len(static_cache.box_drop_table))
        await static_cache.load_static_data()
        assert counts == (len(static_cache.spawn_info), len(static_cache.box_drop_table))
    finally:
        await Tortoise.close_connections()


@pytest.mark.asyncio
async def test_material_is_labeled_as_material_and_has_no_use_action():
    user = User(discord_id=100, username="material")
    item = Item(id=7002, name="늑대 가죽", description="가죽 장비 제작", type=ItemType.ETC)
    inventory = SimpleNamespace(item=item, quantity=2, enhancement_level=0,
                                instance_grade=0, is_blessed=False, is_cursed=False)
    view = InventoryView(SimpleNamespace(id=100), user, [inventory])
    view.current_tab = ItemType.ETC
    view.inventory = view._filter_and_sort()
    view._update_select_button()
    payload = view.create_embed().to_dict()
    text = str(payload)
    assert "늑대 가죽" in text and "재료" in text
    assert "소모품" not in text
    assert not any(isinstance(child, InventorySelectButton) for child in view.children)


@pytest.mark.asyncio
async def test_action_selector_keeps_only_the_originating_category():
    user = User(discord_id=101, username="category")
    consume = SimpleNamespace(
        id=1,
        item=Item(id=5911, name="물약", type=ItemType.CONSUME),
        quantity=2,
        enhancement_level=0,
        instance_grade=0,
    )
    equip = SimpleNamespace(
        id=2,
        item=Item(id=2001, name="검", type=ItemType.EQUIP),
        quantity=1,
        enhancement_level=0,
        instance_grade=1,
    )
    material = SimpleNamespace(
        id=3,
        item=Item(id=7002, name="늑대 가죽", type=ItemType.ETC),
        quantity=1,
        enhancement_level=0,
        instance_grade=0,
    )
    list_view = InventoryView(SimpleNamespace(id=101), user, [consume, equip, material])
    list_view.current_tab = ItemType.CONSUME
    # Simulate a stale or accidentally widened parent list.
    list_view.inventory = [consume, equip, material]

    select_view = InventorySelectView(SimpleNamespace(id=101), user, list_view)
    dropdown = next(child for child in select_view.children if child.__class__.__name__ == "ItemSelectDropdown")
    assert select_view.item_type == ItemType.CONSUME
    assert select_view.inventory == [consume]
    assert [option.value for option in dropdown.options] == ["1"]


@pytest.mark.asyncio
async def test_action_selector_refresh_and_callback_reject_category_or_owner_bypass():
    from tortoise import Tortoise

    await seed_fixture()
    try:
        owner = await ensure_account(81058106, "selector-owner")
        other = await ensure_account(81058107, "selector-other")
        potion = await Item.get(id=8001)
        equipment = await Item.get(id=1001)
        own_potion = await UserInventory.create(user=owner, item=potion, quantity=2)
        own_equipment = await UserInventory.create(user=owner, item=equipment, quantity=1)
        other_potion = await UserInventory.create(user=other, item=potion, quantity=1)
        await own_potion.fetch_related("item")

        list_view = InventoryView(SimpleNamespace(id=owner.discord_id), owner, [own_potion])
        select_view = InventorySelectView(SimpleNamespace(id=owner.discord_id), owner, list_view)
        await select_view.refresh_items()
        assert [row.id for row in select_view.inventory] == [own_potion.id]

        dropdown = next(child for child in select_view.children if isinstance(child, ItemSelectDropdown))
        response = SimpleNamespace(send_message=AsyncMock(), edit_message=AsyncMock())
        interaction = SimpleNamespace(response=response)

        dropdown._values = [str(own_equipment.id)]
        await dropdown.callback(interaction)
        assert select_view.selected_inventory_item is None
        response.send_message.assert_awaited_once()

        response.send_message.reset_mock()
        dropdown._values = [str(other_potion.id)]
        await dropdown.callback(interaction)
        assert select_view.selected_inventory_item is None
        response.send_message.assert_awaited_once()
    finally:
        await Tortoise.close_connections()


@pytest.mark.asyncio
async def test_skill_tab_routes_to_deck_editor(monkeypatch):
    opened = AsyncMock()
    monkeypatch.setattr("views.inventory.select_view._open_inventory_skill_deck", opened)
    button = InventorySelectButton(ItemType.SKILL)
    button._view = SimpleNamespace(db_user="db-user")
    interaction = SimpleNamespace(user=SimpleNamespace(id=5))
    await button.callback(interaction)
    opened.assert_awaited_once_with(interaction, "db-user")
    assert button.label == "스킬 장착"


@pytest.mark.asyncio
async def test_inventory_deck_editor_persists_selected_owned_skill(monkeypatch):
    from tortoise import Tortoise

    await seed_fixture()
    try:
        user = await ensure_account(81058105, "deck-owner")
        await SkillOwnershipService.add_skill(user, 8105, 1)

        async def save_one_owned_skill(view):
            view.current_deck[0] = 8105
            view.changes_made = True
            view.saved = True

        monkeypatch.setattr(SkillDeckView, "wait", save_one_owned_skill)
        interaction = SimpleNamespace(
            user=SimpleNamespace(id=user.discord_id),
            response=SimpleNamespace(send_message=AsyncMock()),
            original_response=AsyncMock(return_value=SimpleNamespace()),
            followup=SimpleNamespace(send=AsyncMock()),
        )

        await _open_inventory_skill_deck(interaction, user)

        slot = await UserSkillDeck.get(user=user, slot_index=0)
        owned = await UserOwnedSkill.get(user=user, skill_id=8105)
        assert slot.skill_id == 8105
        assert owned.quantity == 1 and owned.equipped_count == 1
        interaction.response.send_message.assert_awaited_once()
        interaction.followup.send.assert_not_awaited()
    finally:
        await Tortoise.close_connections()


@pytest.mark.asyncio
async def test_box_quantity_adjusts_then_use_button_opens(monkeypatch):
    item = SimpleNamespace(id=5940, type=ItemType.CONSUME)
    selected = SimpleNamespace(item=item, quantity=5)
    view = SimpleNamespace(selected_inventory_item=selected, use_quantity=1,
                           create_embed=lambda: "embed")
    response = SimpleNamespace(edit_message=AsyncMock(), send_message=AsyncMock())
    interaction = SimpleNamespace(response=response)

    quantity = QuantityButton("+1", 1)
    quantity._view = view
    await quantity.callback(interaction)
    assert view.use_quantity == 2
    response.edit_message.assert_awaited_once_with(embed="embed", view=view)

    opened = AsyncMock()
    monkeypatch.setattr("views.inventory.select_view.is_box_reveal_enabled", lambda: True)
    monkeypatch.setattr(InventoryUseButton, "_open_boxes", opened)
    use = InventoryUseButton()
    use._view = view
    await use.callback(interaction)
    opened.assert_awaited_once_with(view, interaction)
