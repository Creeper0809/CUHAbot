import random

import pytest

from config.itemization_v4 import AFFIX_BY_ID, AFFIX_DEFINITIONS, affix_count
from service.item.affix_service import roll_affixes, sync_affix_definitions
from tools.itemization_v4 import audit, simulate


def test_v4_static_contract_covers_items_sets_and_affixes():
    result = audit()
    assert result["passed"], result["violations"]
    assert result["counts"] == {"equipment": 486, "set_members": 249, "sets": 36, "affixes": 24}


def test_v4_farming_cohort_meets_progression_and_economy_targets():
    result = simulate(500, seed=404)
    assert result["passed"], result["violations"]
    assert result["metrics"]["candidate_interval_runs"] >= 2
    assert result["metrics"]["level_100_median_sss_slots"] == 2


@pytest.mark.parametrize("grade,count", [(1, 0), (3, 0), (4, 1), (5, 2), (6, 2), (7, 3), (8, 3)])
def test_affix_count_and_tiers_are_grade_bound(grade, count):
    rolled = roll_affixes(grade, "weapon", random.Random(grade))
    assert len(rolled) == count == affix_count(grade)
    assert len({AFFIX_BY_ID[row.affix_id].effect_group for row in rolled}) == count
    allowed = {4: {4, 5}, 5: {3, 4}, 6: {2, 3}, 7: {1, 2}, 8: {1, 2}}
    if grade >= 4:
        assert {row.tier for row in rolled} <= allowed[grade]


def test_same_seed_reproduces_affix_identity_value_and_quality():
    first = roll_affixes(8, "ring1", random.Random(8128))
    second = roll_affixes(8, "ring1", random.Random(8128))
    assert first == second


def test_featured_rotation_is_daily_for_dungeons_and_weekly_for_raids():
    from datetime import datetime, timedelta, timezone
    from service.item.progression_service import is_featured_source

    monday = datetime(2026, 8, 10, 12, tzinfo=timezone.utc)
    tuesday = monday + timedelta(days=1)
    next_monday = monday + timedelta(days=7)
    raid_sources = [f"raid-{index}" for index in range(128)]
    dungeon_sources = [f"dungeon-{index}" for index in range(128)]

    assert [is_featured_source("raid", key, now=monday) for key in raid_sources] == [
        is_featured_source("raid", key, now=tuesday) for key in raid_sources
    ]
    assert [is_featured_source("raid", key, now=monday) for key in raid_sources] != [
        is_featured_source("raid", key, now=next_monday) for key in raid_sources
    ]
    assert [is_featured_source("normal", key, now=monday) for key in dungeon_sources] != [
        is_featured_source("normal", key, now=tuesday) for key in dungeon_sources
    ]


@pytest.mark.asyncio
async def test_consumable_inventory_path_remains_independent_from_equipment_storage(test_db):
    from models import Item, User
    from resources.item_emoji import ItemType
    from service.item.inventory_service import InventoryService

    user = await User.create(discord_id=74100, username="consumable")
    item = await Item.create(id=77100, name="V4 물약", description="", cost=10, type=ItemType.CONSUME)
    first = await InventoryService.add_item(user, item.id, quantity=2)
    second = await InventoryService.add_item(user, item.id, quantity=3)
    await first.refresh_from_db()
    assert first.id == second.id
    assert first.quantity == 5


@pytest.mark.asyncio
async def test_source_progress_awards_seal_at_exact_threshold(test_db):
    from models import User, UserCraftingWallet
    from service.item.progression_service import complete_source

    user = await User.create(discord_id=74101, username="farm")
    results = [await complete_source(user, "normal", "테스트 지역") for _ in range(8)]
    wallet = await UserCraftingWallet.get(user=user)
    assert results[-1].seals_awarded == 1
    assert results[-1].progress == 0
    assert wallet.source_seals == {"테스트 지역": 1}


@pytest.mark.asyncio
async def test_auto_salvage_honors_base_and_slot_filters(test_db):
    from models import EquipmentItem, Item, User, UserLootRule
    from resources.item_emoji import ItemType
    from service.item.auto_salvage_service import should_auto_salvage
    from service.item.inventory_service import InventoryService

    user = await User.create(discord_id=74105, username="loot-filter")
    item = await Item.create(id=77105, name="필터 검", description="", cost=100, type=ItemType.EQUIP)
    await EquipmentItem.create(item=item, attack=10, equip_pos=4, require_level=1, acquisition_source="테스트")
    await InventoryService.add_item(user, item.id, instance_grade=3)
    duplicate = await InventoryService.add_item(user, item.id, instance_grade=3)
    rule = await UserLootRule.create(
        user=user, enabled=True, max_grade=3, slots=[4], excluded_item_ids=[item.id],
    )
    assert await should_auto_salvage(user, duplicate) == (False, "excluded")
    rule.excluded_item_ids = []
    rule.slots = [1]
    await rule.save(update_fields=["excluded_item_ids", "slots"])
    assert await should_auto_salvage(user, duplicate) == (False, "slot_filtered")
    rule.slots = [4]
    await rule.save(update_fields=["slots"])
    assert await should_auto_salvage(user, duplicate) == (True, "matched")


@pytest.mark.asyncio
async def test_salvage_is_idempotent_and_reforge_preserves_other_slots(test_db):
    from models import EquipmentItem, Item, User, UserCraftingWallet, UserEquipmentAffix
    from resources.item_emoji import ItemType
    from service.item.inventory_service import InventoryService
    from service.item.progression_service import reforge_affix, salvage_equipment

    await sync_affix_definitions()
    user = await User.create(discord_id=74102, username="economy", gold=1_000_000)
    item = await Item.create(id=77101, name="V4 검", description="", cost=100, type=ItemType.EQUIP)
    await EquipmentItem.create(item=item, attack=10, equip_pos=4, require_level=10, acquisition_source="테스트")
    first = await InventoryService.add_item(user, item.id, instance_grade=5)
    second = await InventoryService.add_item(user, item.id, instance_grade=5)
    before = list(await UserEquipmentAffix.filter(inventory_item=first).order_by("position"))
    wallet = await UserCraftingWallet.get(user=user)
    wallet.equipment_essence = 1000
    await wallet.save()
    result = await reforge_affix(user, first.id, 0, "reforge-1", rng=random.Random(42))
    after = list(await UserEquipmentAffix.filter(inventory_item=first).order_by("position"))
    assert len(before) == len(after) == 2
    assert after[1].affix_definition_id == before[1].affix_definition_id
    assert result["after"]["id"] == after[0].affix_definition_id
    salvage = await salvage_equipment(user, second.id, "salvage-1", confirmed=True)
    replay = await salvage_equipment(user, second.id, "salvage-1", confirmed=True)
    assert salvage == replay and salvage["essence"] == 16


@pytest.mark.asyncio
async def test_integrated_build_preset_restores_stats_skills_and_equipment(test_db):
    from models import EquipmentItem, Item, Skill_Model, User, UserEquipment, UserSkillDeck
    from models.user_equipment import EquipmentSlot
    from resources.item_emoji import ItemType
    from service.buildcraft_service import apply_build, compare_equipment, save_build
    from service.item.inventory_service import InventoryService

    await sync_affix_definitions()
    user = await User.create(discord_id=74103, username="build", level=20, stat_points=57, bonus_str=10)
    item = await Item.create(id=77102, name="프리셋 검", description="", cost=100, type=ItemType.EQUIP)
    await EquipmentItem.create(item=item, attack=10, equip_pos=4, require_level=1, acquisition_source="테스트")
    inventory = await InventoryService.add_item(user, item.id, instance_grade=4)
    await UserEquipment.create(user=user, slot=EquipmentSlot.WEAPON, inventory_item=inventory)
    for index in range(10):
        skill = await Skill_Model.create(id=77110 + index, name=f"스킬 {index}", description="", config={"components": [{"tag": "attack", "ad_ratio": 1.0}], "design": {"role": "basic", "setup_tags": [], "payoff_tags": []}}, player_obtainable=True)
        await UserSkillDeck.create(user=user, slot_index=index, skill=skill)
    preset = await save_build(user, "테스트 빌드")
    user.bonus_str = 0; await user.save(update_fields=["bonus_str"])
    await UserEquipment.filter(user=user).delete()
    result = await apply_build(user, preset.id)
    assert result.missing_slots == ()
    assert user.bonus_str == 10
    assert await UserEquipment.filter(user=user, slot=EquipmentSlot.WEAPON).exists()
    assert await UserSkillDeck.filter(user=user).count() == 10
    comparison = await compare_equipment(user, inventory.id)
    assert comparison["trial"]["after"]["boss_damage_8_actions"] > 0
    assert "estimated_clear_rate" in comparison["trial"]["before"]


@pytest.mark.asyncio
async def test_broken_core_recovers_only_the_same_base_and_is_idempotent(test_db):
    from models import EquipmentItem, Item, User, UserCraftingWallet
    from resources.item_emoji import ItemType
    from service.item.inventory_service import InventoryService
    from service.item.progression_service import recover_destroyed_item

    await sync_affix_definitions()
    user = await User.create(discord_id=74104, username="recovery")
    item = await Item.create(id=77103, name="복구 검", description="", cost=100, type=ItemType.EQUIP)
    await EquipmentItem.create(item=item, attack=10, equip_pos=4, require_level=1, acquisition_source="테스트")
    target = await InventoryService.add_item(user, item.id, instance_grade=6)
    wallet = await UserCraftingWallet.get(user=user)
    wallet.recovery_cores = {str(item.id): 1}
    await wallet.save(update_fields=["recovery_cores"])
    first = await recover_destroyed_item(user, target.id, "recover-1")
    replay = await recover_destroyed_item(user, target.id, "recover-1")
    await target.refresh_from_db(); await wallet.refresh_from_db()
    assert first == replay
    assert target.enhancement_level == 12
    assert wallet.recovery_cores == {}


@pytest.mark.asyncio
async def test_market_summary_uses_recent_seven_day_median(test_db):
    from datetime import datetime, timedelta, timezone
    from models import AuctionHistory
    from models.auction_history import AuctionSaleType
    from service.auction.auction_service import AuctionService

    for price in (100, 300, 200):
        await AuctionHistory.create(
            item_id=77104, sale_price=price, sale_type=AuctionSaleType.BUYNOW,
            seller_id=1, buyer_id=2,
        )
    old = await AuctionHistory.create(
        item_id=77104, sale_price=9999, sale_type=AuctionSaleType.BUYNOW,
        seller_id=1, buyer_id=2,
    )
    old.sold_at = datetime.now(timezone.utc) - timedelta(days=8)
    await old.save(update_fields=["sold_at"])
    summary = await AuctionService.get_market_summary(77104)
    assert summary["transactions"] == 3
    assert summary["median"] == 200
