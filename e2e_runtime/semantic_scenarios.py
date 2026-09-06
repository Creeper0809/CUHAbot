from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import traceback
from typing import Awaitable, Callable

from models import User

from .models import CheckResult, TestRun


Scenario = Callable[[dict[str, User]], Awaitable[dict]]


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


async def run_semantic_scenarios(run: TestRun) -> list[CheckResult]:
    """Run deterministic business-rule scenarios against the isolated E2E DB."""
    seed = int(run.run_id.replace("-", "")[:12], 16) % 100_000_000_000
    discord_ids = [6_000_000_000_000_000_000 + seed * 10 + index for index in range(6)]
    await User.filter(discord_id__in=discord_ids).delete()
    users: dict[str, User] = {}
    checks: list[CheckResult] = []

    try:
        for index, name in enumerate(("primary", "seller", "buyer_a", "buyer_b", "raid", "mail")):
            users[name] = await User.create(
                discord_id=discord_ids[index],
                username=f"E2E semantic {name}",
                gold=0,
                exp=0,
                level=1,
                stat_points=0,
                hp=300,
                now_hp=300,
                attack=10,
                defense=5,
                ap_attack=5,
                ap_defense=5,
                speed=10,
            )

        scenarios: tuple[tuple[str, Scenario], ...] = (
            ("semantic-account-growth-healing", _account_growth_healing),
            ("semantic-inventory-equipment-shop-enhancement", _inventory_equipment_shop_enhancement),
            ("semantic-skill-deck-ultimate-restrictions", _skill_deck_ultimate_restrictions),
            ("semantic-combat-formulas-and-entity-state", _combat_formulas_and_state),
            ("semantic-auction-escrow-refund-sale", _auction_escrow_refund_sale),
            ("semantic-mail-reward-and-collection", _mail_reward_and_collection),
            ("semantic-achievements-events-ranking", _achievements_events_ranking),
            ("semantic-tower-progression-and-rewards", _tower_progression_and_rewards),
            ("semantic-raid-lobby-entry-and-clear", _raid_lobby_entry_and_clear),
            ("semantic-social-proximity-spectator-history", _social_proximity_spectator_history),
            ("semantic-static-content-and-minigames", _static_content_and_minigames),
        )
        for name, scenario in scenarios:
            checks.append(await _execute_scenario(name, scenario, users))
    finally:
        from service.raid.raid_lobby_service import close_raid_lobby
        from service.session import end_session

        for user in users.values():
            close_raid_lobby(user.discord_id)
            await end_session(user.discord_id)
        await User.filter(discord_id__in=discord_ids).delete()

    return checks


async def _execute_scenario(name: str, scenario: Scenario, users: dict[str, User]) -> CheckResult:
    try:
        evidence = await scenario(users)
        return CheckResult(name, "passed", evidence=evidence)
    except Exception as exc:
        return CheckResult(
            name,
            "failed",
            f"{type(exc).__name__}: {exc}\n{traceback.format_exc(limit=8)}",
        )


async def _account_growth_healing(users: dict[str, User]) -> dict:
    from exceptions import AlreadyAttendedError
    from service.economy.reward_service import RewardService, get_exp_to_next_level
    from service.player.healing_service import HealingService
    from service.player.user_service import UserService

    user = users["primary"]
    base_level_one = UserService.calculate_base_stats(1)
    user.hp = base_level_one["hp"]
    user.now_hp = base_level_one["hp"] // 2
    user.attack = base_level_one["attack"]
    user.ap_attack = base_level_one["ap_attack"]
    user.defense = base_level_one["ad_defense"]
    user.ap_defense = base_level_one["ap_defense"]
    user.speed = base_level_one["speed"]
    await user.save()

    attendance = await UserService.process_attendance(user)
    _require(attendance["streak"] == 1, "first attendance streak must be 1")
    _require(attendance["gold_earned"] == 150 and user.gold == 150, "attendance gold mismatch")
    try:
        await UserService.process_attendance(user)
    except AlreadyAttendedError:
        pass
    else:
        raise AssertionError("duplicate attendance was accepted")

    required = get_exp_to_next_level(1)
    result = await RewardService.apply_rewards(user, required, 50)
    _require(result.level_up is not None, "level-up result missing")
    _require((user.level, user.exp, user.stat_points, user.gold) == (2, required, 3, 200), "level reward state mismatch")
    base_level_two = UserService.calculate_base_stats(2)
    _require(
        (user.hp, user.attack, user.ap_attack, user.defense, user.ap_defense, user.speed)
        == (
            base_level_two["hp"], base_level_two["attack"], base_level_two["ap_attack"],
            base_level_two["ad_defense"], base_level_two["ap_defense"], base_level_two["speed"],
        ),
        "level-up base stat persistence mismatch",
    )
    _require(user.now_hp == int(base_level_two["hp"] * 0.5), "level-up HP ratio mismatch")

    parity_user = users["buyer_a"]
    parity_base = UserService.calculate_base_stats(1)
    parity_user.hp = parity_user.now_hp = parity_base["hp"]
    await parity_user.save()
    parity = await UserService.add_experience(parity_user, required)
    _require(
        parity["leveled_up"] and parity_user.level == 2 and parity_user.exp == required,
        "mail/user EXP path diverged from cumulative reward leveling",
    )
    _require(
        parity_user.hp == base_level_two["hp"] and parity_user.now_hp == base_level_two["hp"],
        "mail/user level-up stats mismatch",
    )

    user.now_hp = 100
    user.last_regen_time = datetime.now(timezone.utc) - timedelta(seconds=121)
    await user.save()
    max_hp = user.get_stat_value("HP") if hasattr(user, "get_stat_value") else user.hp
    expected = min(max(1, int(max_hp * user.get_hp_regen_rate() * 2)), max_hp - 100)
    healed = await HealingService.apply_natural_regen(user)
    _require(healed == expected and user.now_hp == 100 + expected, "natural regeneration mismatch")
    full_heal = await HealingService.full_heal(user)
    _require(user.now_hp == max_hp and full_heal == max_hp - (100 + expected), "full heal mismatch")
    return {"attendance_gold": 150, "level": user.level, "exp": user.exp, "regen": healed}


async def _inventory_equipment_shop_enhancement(users: dict[str, User]) -> dict:
    from models.user_equipment import EquipmentSlot
    from service.collection_service import CollectionService
    from service.economy.shop_service import ShopItem, ShopItemType, ShopService
    from service.item.enhancement_service import EnhancementResult, EnhancementService
    from service.item.equipment_service import EquipmentService
    from service.item.inventory_service import InventoryService
    from service.item.item_use_service import ItemUseService

    user = users["primary"]
    await InventoryService.add_item(user, 8001, quantity=2)
    stacked = await InventoryService.add_item(user, 8001, quantity=3)
    _require(stacked.quantity == 5, "stackable item did not merge")
    _require(await InventoryService.get_inventory_count(user) == 1, "stack consumed multiple slots")

    user.now_hp = 100
    await user.save()
    used = await ItemUseService.use_item(user, stacked.id)
    _require(used.success and user.now_hp == 200, "100 HP potion did not heal exactly 100")
    _require(await InventoryService.count_item(user, 8001) == 4, "consumable quantity did not decrement")

    shop = ShopItem(900001, "semantic potion", "", 50, ShopItemType.CONSUMABLE, 8001)
    user.gold = 500
    await user.save()
    purchase = await ShopService.purchase_shop_item(user, shop, quantity=2)
    _require(purchase.total_cost == 100 and user.gold == 400, "shop purchase price mismatch")
    _require(await InventoryService.count_item(user, 8001) == 6, "shop inventory delivery mismatch")
    sale_inv = await InventoryService.get_item_by_item_id(user, 8001)
    sale = await ShopService.sell_item(user, sale_inv.id, quantity=1)
    from config import SHOP
    expected_resale = int(shop.price * SHOP.SELL_PRICE_RATIO)
    _require(sale.total_cost == -expected_resale and user.gold == 400 + expected_resale, "shop resale value mismatch")

    equipment = await InventoryService.add_item(user, 1001, quantity=1, instance_grade=3)
    equipped = await EquipmentService.equip_item(user, equipment.id, EquipmentSlot.WEAPON)
    _require(equipped.inventory_item_id == equipment.id, "equipment slot ownership mismatch")
    stats = await EquipmentService.calculate_equipment_stats(user)
    _require(stats["attack"] > 0, "equipped weapon provided no attack")
    _require(await EquipmentService.unequip_item(user, EquipmentSlot.WEAPON), "unequip returned false")
    _require((await EquipmentService.calculate_equipment_stats(user))["attack"] == 0, "unequip left attack bonus")

    user.gold = 10_000
    await user.save()
    info = await EnhancementService.get_enhancement_info(user, equipment.id)
    _require(info["can_enhance"] and info["success_rate"] == 1.0, "level-zero enhancement must be guaranteed")
    before_gold = user.gold
    attempt = await EnhancementService.attempt_enhancement(user, equipment.id)
    _require(attempt.result_type == EnhancementResult.SUCCESS and attempt.new_level == 1, "guaranteed enhancement failed")
    _require(user.gold == before_gold - attempt.cost, "enhancement cost mismatch")

    stats = await CollectionService.get_collection_stats(user)
    _require(stats.item_collected >= 2, "item acquisition did not update collection")
    return {"potion_count": await InventoryService.count_item(user, 8001), "enhancement": attempt.new_level, "attack_bonus": stats.item_collected}


async def _skill_deck_ultimate_restrictions(users: dict[str, User]) -> dict:
    from exceptions import CombatRestrictionError, DeckSlotLimitError, DuplicatePassiveSkillError
    from models.user_owned_skill import UserOwnedSkill
    from models.user_skill_deck import UserSkillDeck
    from service.session import create_session, end_session
    from service.skill.skill_deck_service import SkillDeckService
    from service.skill.skill_ownership_service import SkillOwnershipService
    from service.skill.ultimate_service import (
        add_ultimate_gauge,
        can_cast_ultimate,
        set_ultimate_skill,
        spend_ultimate_gauge,
        tick_ultimate_cooldown,
    )

    user = users["primary"]
    await UserSkillDeck.filter(user=user).delete()
    await UserOwnedSkill.filter(user=user).delete()
    await SkillOwnershipService.add_skill(user, 1002, quantity=2)
    current = [0] * 10
    target = [1002, 1002] + [0] * 8
    allowed, error = await SkillOwnershipService.can_change_deck(user, current, target)
    _require(allowed and error is None, "owned skill deck was rejected")
    await SkillOwnershipService.apply_deck_change(user, current, target)
    await SkillDeckService.set_skill(user, 0, 1002)
    await SkillDeckService.set_skill(user, 1, 1002)
    owned = await SkillOwnershipService.get_owned_skill(user, 1002)
    _require(owned.equipped_count == 2 and owned.available_count == 0, "equipped skill quantity mismatch")
    allowed, _ = await SkillOwnershipService.can_change_deck(user, target, [1002, 1002, 1002] + [0] * 7)
    _require(not allowed, "deck accepted more copies than owned")
    try:
        await SkillDeckService.set_skill(user, 10, 1002)
    except DeckSlotLimitError:
        pass
    else:
        raise AssertionError("out-of-range deck slot was accepted")

    await SkillOwnershipService.add_skill(user, 6001, quantity=2)
    await SkillDeckService.set_skill(user, 2, 6001)
    try:
        await SkillDeckService.set_skill(user, 3, 6001)
    except DuplicatePassiveSkillError:
        pass
    else:
        raise AssertionError("duplicate passive occupied two deck slots")

    session = await create_session(user.discord_id)
    _require(session is not None, "could not create restriction session")
    session.in_combat = True
    try:
        await SkillDeckService.clear_deck(user)
    except CombatRestrictionError:
        pass
    else:
        raise AssertionError("combat allowed deck mutation")
    await end_session(user.discord_id)

    _require(await set_ultimate_skill(user, 5001), "valid ultimate was rejected")
    _require(not await set_ultimate_skill(user, 1002), "normal skill accepted as ultimate")
    user.equipped_ultimate_skill = 5001
    gauge = add_ultimate_gauge(user, dealt_damage=500, taken_damage=500, acted=True)
    _require(gauge == 58, "ultimate gauge formula mismatch")
    add_ultimate_gauge(user, dealt_damage=1000, taken_damage=1000, acted=True)
    _require(can_cast_ultimate(user), "ultimate gauge did not cap at ready")
    spend_ultimate_gauge(user)
    _require(user.ultimate_gauge == 0 and tick_ultimate_cooldown(user) == 0, "ultimate spend/cooldown baseline mismatch")
    return {"deck": await SkillDeckService.get_deck_as_list(user), "equipped_count": owned.equipped_count, "gauge_formula": gauge}


async def _combat_formulas_and_state(users: dict[str, User]) -> dict:
    from config import DAMAGE, BALANCE_V2
    from service.combat.damage_calculator import DamageCalculator

    original_variance = DamageCalculator._apply_variance
    original_critical = DamageCalculator._roll_critical
    DamageCalculator._apply_variance = staticmethod(lambda damage: damage)
    DamageCalculator._roll_critical = staticmethod(lambda rate: False)
    try:
        physical = DamageCalculator.calculate_physical_damage(attack=100, defense=40, skill_multiplier=1.5, armor_penetration=0.25, critical_rate=0)
        expected_rate = BALANCE_V2.defense_reduction(40, 0.25)
        expected_damage = int(150 * (1 - expected_rate))
        expected_reduction = 150 - expected_damage
        _require(physical.raw_damage == 150, "physical raw damage mismatch")
        _require(physical.defense_reduction == expected_reduction, "physical defense reduction mismatch")
        _require(physical.damage == expected_damage, "physical final damage mismatch")
        critical = DamageCalculator.calculate_magical_damage(100, 20, force_critical=True)
        expected_magic = int(100 * (1 - BALANCE_V2.defense_reduction(20)))
        _require(critical.damage == int(expected_magic * DAMAGE.CRITICAL_MULTIPLIER), "critical magic damage mismatch")
    finally:
        DamageCalculator._apply_variance = original_variance
        DamageCalculator._roll_critical = original_critical

    user = users["buyer_b"]
    user.now_hp = 50
    _require(user.take_damage(80) == 50 and user.now_hp == 0 and user.is_dead(), "lethal damage was not clamped")
    _require(user.heal(9999) == user.hp and user.now_hp == user.hp, "healing was not capped at max HP")
    return {"physical_damage": physical.damage, "magic_critical": critical.damage}


async def _auction_escrow_refund_sale(users: dict[str, User]) -> dict:
    from exceptions import AuctionCannotCancelError, AuctionSelfBidError
    from models.auction_listing import AuctionStatus, AuctionType
    from service.auction.auction_service import AuctionService
    from service.item.inventory_service import InventoryService

    seller, bidder_a, bidder_b = users["seller"], users["buyer_a"], users["buyer_b"]
    for user in (seller, bidder_a, bidder_b):
        user.gold = 1_000
        await user.save()

    bid_item = await InventoryService.add_item(seller, 8002, 1)
    listing = await AuctionService.create_listing(seller, bid_item.id, AuctionType.BID, 100, None, 1)
    await bid_item.refresh_from_db()
    _require(seller.gold == 998 and bid_item.is_locked, "listing fee or item lock mismatch")
    try:
        await AuctionService.place_bid(seller, listing.id, 150)
    except AuctionSelfBidError:
        pass
    else:
        raise AssertionError("seller could bid on own listing")
    first = await AuctionService.place_bid(bidder_a, listing.id, 150)
    _require(bidder_a.gold == 850, "first bid escrow mismatch")
    highest = await AuctionService.place_bid(bidder_b, listing.id, 200)
    await bidder_a.refresh_from_db()
    _require(bidder_a.gold == 1_000, "previous bidder escrow was not refunded")
    await first.refresh_from_db()
    _require(first.is_refunded, "previous bid not marked refunded")
    try:
        await AuctionService.cancel_listing(seller, listing.id)
    except AuctionCannotCancelError:
        pass
    else:
        raise AssertionError("listing with bids was cancellable")
    await AuctionService._finalize_auction(listing, highest)
    await seller.refresh_from_db(); await bidder_b.refresh_from_db(); await listing.refresh_from_db()
    moved = await InventoryService.get_inventory_item(bidder_b, bid_item.id)
    _require(listing.status == AuctionStatus.SOLD and moved is not None, "auction did not transfer item")
    _require(seller.gold == 1_188 and bidder_b.gold == 800, "auction settlement mismatch")

    order = await AuctionService.create_buy_order(bidder_a, 8003, 300, 0, 99, 0, 8, 1)
    _require(bidder_a.gold == 700 and order.escrowed_gold == 300, "buy-order escrow mismatch")
    await AuctionService.cancel_buy_order(bidder_a, order.id)
    _require(bidder_a.gold == 1_000, "buy-order cancellation refund mismatch")
    return {"sale_price": 200, "seller_gold": seller.gold, "buyer_gold": bidder_b.gold, "refund": bidder_a.gold}


async def _mail_reward_and_collection(users: dict[str, User]) -> dict:
    from service.mail import MailService
    from service.mail.exceptions import AlreadyClaimedError
    from models.mail import MailType
    from service.item.inventory_service import InventoryService

    user = users["mail"]
    mail = await MailService.send_mail(
        user.id, MailType.SYSTEM, "E2E", "semantic reward", "contract",
        reward_config={"exp": 50, "gold": 20, "items": [{"id": 8001, "quantity": 2}]},
        expire_days=1,
    )
    _require(await MailService.get_unread_count(user.id) == 1, "unread mail count mismatch")
    paid = await MailService.claim_reward(mail.id, user.id)
    await user.refresh_from_db(); await mail.refresh_from_db()
    _require(paid == {"exp": 50, "gold": 20, "items": [{"id": 8001, "quantity": 2}]}, "mail reward payload mismatch")
    _require((user.exp, user.gold) == (50, 20), "mail did not persist currency rewards")
    _require(await InventoryService.count_item(user, 8001) == 2, "mail did not deliver item reward")
    _require(mail.is_read and mail.is_claimed, "mail claim flags mismatch")
    try:
        await MailService.claim_reward(mail.id, user.id)
    except AlreadyClaimedError:
        pass
    else:
        raise AssertionError("mail reward could be claimed twice")
    return {"exp": user.exp, "gold": user.gold, "items": 2, "claimed": True}


async def _achievements_events_ranking(users: dict[str, User]) -> dict:
    from models.achievement import Achievement, AchievementCategory
    from models.mail import Mail, MailType
    from models.user_achievement import UserAchievement
    from service.event import EventBus, GameEvent, GameEventType
    from service.ranking_service import RankingService

    user = users["buyer_b"]
    achievement_id = 9_000_000 + user.id
    await Achievement.filter(id=achievement_id).delete()
    achievement = await Achievement.create(
        id=achievement_id,
        name="E2E semantic collector",
        description="Collect exactly two items",
        category=AchievementCategory.COLLECTION,
        tier=1,
        objective_config={"type": "item_collected", "count": 2},
        reward_config={"exp": 11, "gold": 7},
    )
    try:
        event_bus = EventBus()
        _require(event_bus.get_subscriber_count(GameEventType.ITEM_OBTAINED) > 0, "achievement tracker is not subscribed")
        await event_bus.publish(GameEvent(GameEventType.ITEM_OBTAINED, user.id, {"quantity": 1}))
        progress = await UserAchievement.get(user=user, achievement=achievement)
        _require((progress.progress_current, progress.progress_required, progress.is_completed) == (1, 2, False), "achievement partial progress mismatch")
        await event_bus.publish(GameEvent(GameEventType.ITEM_OBTAINED, user.id, {"quantity": 1}))
        await progress.refresh_from_db()
        mails = await Mail.filter(user=user, mail_type=MailType.ACHIEVEMENT).all()
        _require(progress.is_completed and progress.progress_current == 2, "achievement completion mismatch")
        _require(len(mails) == 1 and mails[0].reward_config == {"exp": 11, "gold": 7}, "achievement reward mail mismatch")
        await event_bus.publish(GameEvent(GameEventType.ITEM_OBTAINED, user.id, {"quantity": 5}))
        await progress.refresh_from_db()
        _require(progress.progress_current == 2, "completed achievement accepted more progress")
        _require(await Mail.filter(user=user, mail_type=MailType.ACHIEVEMENT).count() == 1, "achievement mailed more than once")

        user.level, user.exp, user.gold = 999, 999_999_999, 999_999_999
        await user.save()
        level_ranking = await RankingService.get_level_ranking(limit=1)
        gold_ranking = await RankingService.get_gold_ranking(limit=1)
        ranks = await RankingService.get_user_rankings(user.id)
        _require(level_ranking[0]["discord_id"] == user.discord_id and gold_ranking[0]["discord_id"] == user.discord_id, "ranking sort order mismatch")
        _require(ranks["level_rank"] == 1 and ranks["gold_rank"] == 1, "personal ranking mismatch")
        return {"achievement_progress": 2, "achievement_mails": 1, "level_rank": 1, "gold_rank": 1}
    finally:
        await UserAchievement.filter(user=user, achievement_id=achievement_id).delete()
        await Mail.filter(user=user, mail_type=MailType.ACHIEVEMENT).delete()
        await Achievement.filter(id=achievement_id).delete()


async def _tower_progression_and_rewards(users: dict[str, User]) -> dict:
    from models.repos.tower_progress_repo import get_or_create_progress
    from service.tower.tower_reward_service import apply_floor_reward, calculate_floor_reward
    from service.tower.tower_season_service import get_current_season
    from service.tower.tower_service import get_dungeon_for_floor, is_boss_floor

    user = users["raid"]
    user.exp = user.gold = 0
    user.level = 1
    user.stat_points = 0
    await user.save()
    normal = calculate_floor_reward(1, False)
    boss = calculate_floor_reward(10, True)
    _require((normal.exp, normal.gold, normal.tower_coins) == (100, 50, 1), "normal tower reward formula mismatch")
    _require((boss.exp, boss.gold, boss.tower_coins) == (2000, 1000, 5), "boss tower reward formula mismatch")
    _require(get_dungeon_for_floor(1) == 1 and get_dungeon_for_floor(100) == 10, "tower dungeon mapping mismatch")
    _require(not is_boss_floor(9) and is_boss_floor(10), "tower boss interval mismatch")
    progress = await get_or_create_progress(user, get_current_season())
    await apply_floor_reward(user, progress, 1, False)
    await user.refresh_from_db(); await progress.refresh_from_db()
    _require((user.exp, user.gold, progress.tower_coins) == (100, 50, 1), "tower reward persistence mismatch")
    return {"normal": [normal.exp, normal.gold, normal.tower_coins], "boss": [boss.exp, boss.gold, boss.tower_coins]}


async def _raid_lobby_entry_and_clear(users: dict[str, User]) -> dict:
    from models.repos.raid_progress_repo import get_or_create_progress
    from service.raid.raid_lobby_service import close_raid_lobby, create_raid_lobby, get_raid_lobby
    from service.raid.raid_progress_service import (
        check_raid_entry, consume_raid_entry, get_raid_clear_bonus, get_week_key,
    )

    user = users["mail"]
    lobby = create_raid_lobby(user.discord_id, 101, "semantic raid", 101, 30, 3, None)
    _require(lobby.party_size() == 1 and lobby.all_ready(), "leader lobby initialization mismatch")
    lobby.participants[user.discord_id + 100] = False
    _require(not lobby.all_ready() and lobby.ready_count() == 1, "raid ready-state mismatch")
    lobby.participants[user.discord_id + 100] = True
    _require(lobby.all_ready() and get_raid_lobby(user.discord_id) is lobby, "raid lobby lookup/readiness mismatch")

    entry = await check_raid_entry(user, 101)
    _require(entry.allowed and entry.remaining_entries == 3, "initial weekly raid entries mismatch")
    for expected in (2, 1, 0):
        remaining, maximum = await consume_raid_entry(user, 101)
        _require((remaining, maximum) == (expected, 3), "raid entry consumption mismatch")
    _require(not (await check_raid_entry(user, 101)).allowed, "weekly raid limit not enforced by entry check")
    first = await get_raid_clear_bonus(user, 101, 12)
    second = await get_raid_clear_bonus(user, 101, 9)
    _require(first == (1500, 1000, True) and second == (300, 200, False), "raid clear bonus mismatch")
    progress = await get_or_create_progress(user, 101, get_week_key())
    _require((progress.clears, progress.best_clear_turns) == (2, 9), "raid clear progress mismatch")
    close_raid_lobby(user.discord_id)
    _require(get_raid_lobby(user.discord_id) is None, "raid lobby cleanup failed")
    return {"weekly_entries": 3, "clears": progress.clears, "best_turns": progress.best_clear_turns}


async def _social_proximity_spectator_history(users: dict[str, User]) -> dict:
    from service.combat_history.history_service import HistoryService
    from service.intervention.contribution_tracker import get_carry_penalty_multiplier
    from service.notification.proximity_reward_calculator import (
        get_intervention_cost,
        get_proximity_reward_multiplier,
    )
    from service.spectator.spectator_state import (
        get_target_id,
        get_target_spectators,
        is_spectating,
        start_spectating,
        stop_spectating,
    )
    from service.voice_channel.proximity_calculator import ProximityCalculator, ProximityLevel
    from service.voice_channel.shared_instance_manager import SharedInstanceManager
    from service.voice_channel.voice_channel_service import VoiceChannelService

    first, second = users["seller"], users["buyer_a"]
    first_id, second_id = first.discord_id, second.discord_id
    voice = VoiceChannelService()
    shared = SharedInstanceManager()
    stop_spectating(first_id)
    stop_spectating(second_id)
    try:
        await voice.user_joined_channel(first_id, 71_001)
        await voice.user_joined_channel(second_id, 71_001)
        _require(voice.are_in_same_channel(first_id, second_id) and voice.get_total_users() == 2, "voice-channel membership mismatch")
        await voice.user_joined_channel(first_id, 71_002)
        _require(not voice.are_in_same_channel(first_id, second_id), "voice-channel move left stale membership")
        _require(voice.get_users_in_channel(71_001) == {second_id} and voice.get_users_in_channel(71_002) == {first_id}, "voice-channel index mismatch")
        await voice.user_left_channel(first_id)
        await voice.user_left_channel(second_id)
        _require(voice.get_channel_count() == 0 and voice.get_total_users() == 0, "empty voice channels were not cleaned")

        same_a = await shared.join_instance(first_id, 71_001, 1)
        same_b = await shared.join_instance(second_id, 71_001, 1)
        _require(same_a is same_b and same_a.session_ids == {first_id, second_id}, "shared dungeon did not coalesce participants")
        moved = await shared.join_instance(first_id, 71_001, 2)
        _require(moved.get_key() == (71_001, 2) and same_a.session_ids == {second_id}, "shared dungeon move left stale participant")
        await shared.leave_instance(first_id)
        await shared.leave_instance(second_id)
        _require(shared.get_instance_count() == 0, "empty shared dungeon instances were not cleaned")

        _require(ProximityCalculator.calculate_distance(2, 12) == 10, "proximity distance mismatch")
        _require([ProximityCalculator.get_proximity_level(value) for value in (3, 4, 10, 11)] == [ProximityLevel.IMMEDIATE, ProximityLevel.NEARBY, ProximityLevel.NEARBY, ProximityLevel.FAR], "proximity boundary mismatch")
        _require([get_intervention_cost(value) for value in (3, 4, 10, 11)] == [0, 100, 100, 500], "intervention cost boundary mismatch")
        _require([get_proximity_reward_multiplier(value) for value in (3, 4, 10, 11)] == [1.1, 1.0, 1.0, 0.8], "proximity reward boundary mismatch")
        _require([get_carry_penalty_multiplier(value, 10) for value in (14, 15, 20, 25)] == [1.0, 0.2, 0.05, 0.0], "carry-penalty boundary mismatch")

        start_spectating(first_id, second_id)
        start_spectating(second_id, second_id)
        _require(is_spectating(first_id) and get_target_id(first_id) == second_id, "spectator lookup mismatch")
        _require({state.spectator_id for state in get_target_spectators(second_id)} == {first_id, second_id}, "target spectator index mismatch")
        stop_spectating(first_id)
        _require(not is_spectating(first_id) and len(get_target_spectators(second_id)) == 1, "spectator cleanup mismatch")

        await HistoryService.record_combat(first.id, 1, 10, "E2E near", "victory", 100, 2, 71_001)
        await HistoryService.record_combat(second.id, 1, 20, "E2E far", "defeat", 50, 4, 71_001)
        nearby = await HistoryService.get_nearby_histories(1, 12, range=3)
        _require([history.monster_name for history in nearby] == ["E2E near"], "combat-history proximity filter mismatch")
        recent = await HistoryService.get_user_recent_histories(first.id, limit=1)
        _require(len(recent) == 1 and recent[0].total_damage == 100 and recent[0].turns_lasted == 2, "recent combat history mismatch")
        return {"voice_cleanup": True, "shared_cleanup": True, "proximity_costs": [0, 100, 100, 500], "nearby_histories": 1}
    finally:
        stop_spectating(first_id)
        stop_spectating(second_id)


async def _static_content_and_minigames(users: dict[str, User]) -> dict:
    from models import Achievement, ConsumeItem, Dungeon, EquipmentItem, Item, Raid, Skill_Model
    from models.item import ItemType
    from service.minigame.minigame_manager import MinigameManager

    counts = {
        "items": await Item.all().count(),
        "skills": await Skill_Model.all().count(),
        "dungeons": await Dungeon.all().count(),
        "raids": await Raid.all().count(),
        "achievements": await Achievement.all().count(),
    }
    _require(all(value > 0 for value in counts.values()), f"empty seeded content table: {counts}")
    consume_items = await Item.filter(type=ItemType.CONSUME).count()
    equipment_items = await Item.filter(type=ItemType.EQUIP).count()
    _require(await ConsumeItem.all().count() == consume_items, "consumable subtype rows do not match item rows")
    _require(await EquipmentItem.all().count() == equipment_items, "equipment subtype rows do not match item rows")
    games = MinigameManager.list_minigames()
    _require(set(games) == {"timing", "sequence", "reaction", "rps", "typing", "math", "memory"}, "minigame registry mismatch")
    for game in games:
        info = MinigameManager.get_minigame_info(game)
        _require(info and info["name"] and info["description"] and info["timeout"] > 0, f"invalid minigame metadata: {game}")
    counts["minigames"] = len(games)
    return counts
