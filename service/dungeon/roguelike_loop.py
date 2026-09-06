"""Eight-room Discord roguelike loop for normal dungeons."""

from __future__ import annotations

import asyncio
from collections import deque
import os

import discord

from config import BALANCE_V2, DROP, DUNGEON, ROGUELIKE, RouteKind
from exceptions import InventoryFullError
from models import Item, UserStatEnum
from models.repos.skill_repo import get_skill_by_id
from service.dungeon.roguelike_routes import RouteOffer, generate_route_offers, room_stat_scale
from service.dungeon.roguelike_settlement import apply_failure_penalty
from service.item.inventory_service import InventoryService
from service.session import DungeonSession, SessionType
from views.roguelike_dungeon import wait_for_route_choice, wait_for_skill_augment


async def _join_shared_instance(session: DungeonSession) -> None:
    if not session.voice_channel_id or not session.dungeon:
        return
    from service.voice_channel.shared_instance_manager import shared_instance_manager
    try:
        await shared_instance_manager.join_instance(
            session.user_id, session.voice_channel_id, session.dungeon.id
        )
        session.shared_instance_key = (session.voice_channel_id, session.dungeon.id)
    except Exception:
        return


def _active_skills(session: DungeonSession) -> list:
    ids = []
    for skill_id in list(getattr(session.user, "equipped_skill", [])) + [
        getattr(session.user, "equipped_ultimate_skill", 0)
    ]:
        if not skill_id or skill_id == 1001 or skill_id in ids:
            continue
        skill = get_skill_by_id(skill_id)
        if skill and not skill.is_passive:
            ids.append(skill_id)
    return [get_skill_by_id(skill_id) for skill_id in ids]


async def _grant_box(session: DungeonSession, box_id: int) -> tuple[str, object | None]:
    dungeon_level = session.dungeon.require_level if session.dungeon else 0
    item = await Item.get_or_none(id=box_id)
    try:
        inventory = await InventoryService.add_item(
            session.user, box_id, 1, instance_grade=dungeon_level
        )
    except InventoryFullError:
        return "인벤토리가 가득 차 상자를 획득하지 못했습니다.", None
    session.items_found.append(box_id)
    return f"🎁 **{item.name if item else '상자'}** 획득", inventory


class ChestDecisionView(discord.ui.View):
    def __init__(self, owner_id: int, session: DungeonSession, inventory):
        super().__init__(timeout=30)
        self.owner_id = owner_id
        self.session = session
        self.inventory = inventory
        self.done = asyncio.Event()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.owner_id

    @discord.ui.button(label="지금 열기", style=discord.ButtonStyle.success, custom_id="rl:chest:open")
    async def open_now(self, interaction: discord.Interaction, _: discord.ui.Button):
        from service.game_settings import is_box_reveal_enabled
        if not is_box_reveal_enabled():
            await interaction.response.send_message("상자 공개 기능이 비활성화되어 인벤토리에 보관했습니다.", ephemeral=True)
            self.done.set()
            self.stop()
            return
        from service.item.box_announcement import announce_notable_box_results
        from service.item.box_open_service import BoxOpenService
        from views.box_reveal import animate_box_reveal
        batch = await BoxOpenService.open_boxes(
            self.session.user, self.inventory.id, 1, interaction.id
        )
        await interaction.response.edit_message(view=None)
        continue_event = asyncio.Event()
        await animate_box_reveal(
            interaction,
            batch,
            response_already_used=True,
            continue_event=continue_event,
        )
        try:
            await announce_notable_box_results(
                interaction.client, self.session.origin_guild_id, interaction.user, batch
            )
        except Exception:
            __import__("logging").getLogger(__name__).exception(
                "Dungeon box brag announcement failed after commit"
            )
        self.done.set()
        self.stop()

    @discord.ui.button(label="보관하고 계속", style=discord.ButtonStyle.secondary, custom_id="rl:chest:keep")
    async def keep(self, interaction: discord.Interaction, _: discord.ui.Button):
        await interaction.response.edit_message(view=None)
        self.done.set()
        self.stop()


async def _offer_chest_action(session: DungeonSession, discord_user, control_message, inventory) -> None:
    if not inventory or os.getenv("E2E_UI_AUTOPILOT") == "TRUE":
        return
    view = ChestDecisionView(discord_user.id, session, inventory)
    await control_message.edit(
        embed=discord.Embed(
            title="🎁 상자를 발견했습니다",
            description="상자는 이미 인벤토리에 지급되었습니다. 지금 열거나 보관할 수 있습니다.",
            color=discord.Color.gold(),
        ),
        view=view,
    )
    await view.wait()


def _base_route_reward(session: DungeonSession) -> tuple[int, int]:
    from config import BALANCE_V2

    level = max(1, session.dungeon.require_level)
    return (
        round(BALANCE_V2.dungeon_exp(level) * 0.55 / 8),
        round(BALANCE_V2.dungeon_gold(level) * 0.55 / 8),
    )


async def _resolve_route(session: DungeonSession, interaction: discord.Interaction, offer: RouteOffer, control_message) -> str:
    rng = __import__("random").Random(offer.payload["resolution_seed"])
    if offer.kind in {RouteKind.COMBAT, RouteKind.ELITE}:
        avoid = session.explore_buffs.get("avoid_combat", 0)
        if avoid > 0:
            session.explore_buffs["avoid_combat"] = avoid - 1
            if session.explore_buffs["avoid_combat"] <= 0:
                session.explore_buffs.pop("avoid_combat", None)
            base_exp, base_gold = _base_route_reward(session)
            session.total_exp += int(base_exp * 0.25)
            session.total_gold += int(base_gold * 0.25)
            return "🫥 전투 회피 효과로 적을 지나쳤습니다. 경로 보상 25% 획득"
        from service.dungeon.encounter_processor import _process_monster_encounter
        session.roguelike_combat_kind = offer.kind.value
        session.roguelike_resolution_seed = int(offer.payload["resolution_seed"])
        session.roguelike_stat_scale = room_stat_scale(offer.room)
        session.roguelike_skip_flee = True
        try:
            return await _process_monster_encounter(session, interaction)
        finally:
            session.roguelike_combat_kind = None
            session.roguelike_resolution_seed = None
            session.roguelike_stat_scale = 1.0
            session.roguelike_skip_flee = False

    if offer.kind == RouteKind.TREASURE:
        box_id = {"normal": DROP.CHEST_ITEM_NORMAL_ID, "silver": DROP.CHEST_ITEM_SILVER_ID, "gold": DROP.CHEST_ITEM_GOLD_ID}[offer.payload["chest_grade"]]
        result, inventory = await _grant_box(session, box_id)
        await _offer_chest_action(session, interaction.user, control_message, inventory)
        return result
    if offer.kind == RouteKind.SECRET:
        result, inventory = await _grant_box(session, int(offer.payload["box_id"]))
        await _offer_chest_action(session, interaction.user, control_message, inventory)
        return f"🚪 비밀방 발견! {result}"
    if offer.kind == RouteKind.HAZARD:
        base_exp, base_gold = _base_route_reward(session)
        exp = int(base_exp * ROGUELIKE.HAZARD_REWARD_MULTIPLIER)
        gold = int(base_gold * ROGUELIKE.HAZARD_REWARD_MULTIPLIER)
        session.total_exp += exp
        session.total_gold += gold
        if offer.payload["triggered"]:
            max_hp = session.user.get_stat()[UserStatEnum.HP]
            damage = max(1, int(max_hp * float(offer.payload["damage_rate"])))
            session.user.now_hp = max(0, session.user.now_hp - damage)
            return f"⚠️ 함정 발동! -{damage} HP · +{exp} EXP · +{gold} G"
        return f"🪽 함정을 피했습니다! +{exp} EXP · +{gold} G"
    if offer.kind == RouteKind.REST:
        max_hp = session.user.get_stat()[UserStatEnum.HP]
        if session.user.now_hp >= max_hp:
            session.rest_shield_rate = ROGUELIKE.REST_SHIELD_RATE
            return "🛡️ 충분히 쉬어 다음 전투에 최대 HP 10% 보호막을 준비했습니다."
        healed = min(int(max_hp * ROGUELIKE.REST_HEAL_RATE), max_hp - session.user.now_hp)
        session.user.now_hp += healed
        return f"🏕️ 휴식으로 HP +{healed} 회복"
    if offer.kind == RouteKind.EVENT:
        event_type = offer.payload["event_type"]
        if os.getenv("E2E_UI_AUTOPILOT") != "TRUE":
            from views.encounter_view import RandomEventView
            positive = event_type in {"heal", "attack_boost", "lucky"}
            view = RandomEventView(
                user=interaction.user,
                is_blessing=positive,
                event_type=event_type,
                timeout=ROGUELIKE.CHOICE_TIMEOUT_SECONDS,
            )
            message = await interaction.user.send(embed=view.create_embed(before=True), view=view)
            view.message = message
            await view.wait()
            if not view.accepted:
                return "🚶 사건에 개입하지 않고 지나쳤습니다."
        max_hp = session.user.get_stat()[UserStatEnum.HP]
        if event_type == "heal":
            amount = min(int(max_hp * 0.20), max_hp - session.user.now_hp)
            session.user.now_hp += amount
            return f"✨ 신비로운 샘물 · HP +{amount}"
        if event_type == "attack_boost":
            session.explore_buffs["campfire_atk_bonus"] = {"percent": 0.20, "remaining_combats": 1}
            return "🔥 다음 전투 공격력 +20%"
        if event_type == "lucky":
            level = session.dungeon.require_level if session.dungeon else session.user.level
            base = max(10, round(BALANCE_V2.dungeon_gold(level) * .08))
            gold = round(base * rng.uniform(.8, 1.2))
            session.total_gold += gold
            return f"🍀 행운의 동전 · +{gold} G"
        if event_type == "damage":
            damage = max(1, int(max_hp * 0.05))
            session.user.now_hp = max(0, session.user.now_hp - damage)
            return f"👻 저주 · -{damage} HP"
        level = session.dungeon.require_level if session.dungeon else session.user.level
        loss = min(max(5, round(BALANCE_V2.dungeon_gold(level) * .03)), session.total_gold)
        session.total_gold -= loss
        return f"💸 도둑의 저주 · -{loss} G"
    if offer.kind == RouteKind.NPC:
        from service.dungeon.roguelike_routes import npc_offer_details

        npc_type = offer.payload["npc_type"]
        level = session.dungeon.require_level if session.dungeon else session.user.level
        cost, _ = npc_offer_details(offer, level)
        if session.user.gold < cost:
            return f"🪙 거래 실패 · {cost:,} G 필요 (보유 {session.user.gold:,} G)"
        session.user.gold -= cost
        await session.user.save(update_fields=["gold"])
        if npc_type == "healer":
            max_hp = session.user.get_stat()[UserStatEnum.HP]
            amount = min(int(max_hp * 0.30), max_hp - session.user.now_hp)
            session.user.now_hp += amount
            return f"💚 방랑 치료사 · -{cost:,} G · HP +{amount}"
        if npc_type == "sage":
            exp = max(1, round(BALANCE_V2.dungeon_exp(level) * .08))
            session.total_exp += exp
            return f"📚 현자의 가르침 · -{cost:,} G · +{exp:,} EXP"
        result, inventory = await _grant_box(session, DROP.CHEST_ITEM_NORMAL_ID)
        await _offer_chest_action(session, interaction.user, control_message, inventory)
        return f"🧙 떠돌이 상인 · -{cost:,} G · {result}"
    return "아무 일도 일어나지 않았습니다."


async def start_roguelike_dungeon(session: DungeonSession, interaction: discord.Interaction) -> bool:
    from service.dungeon.dungeon_loop import (
        _handle_dungeon_clear, _handle_dungeon_return, _handle_player_death,
        _update_dungeon_log,
    )
    from service.dungeon.dungeon_ui import create_dungeon_embed

    session.roguelike_enabled = True
    session.max_steps = ROGUELIKE.BOSS_STAGE
    session.exploration_step = 0
    session.origin_guild_id = interaction.guild_id
    session.origin_channel_id = interaction.channel_id
    await _join_shared_instance(session)
    event_queue: deque[str] = deque(maxlen=20)
    event_queue.append(f"🗺️ **{session.dungeon.name} 로그라이크 탐험 시작**")
    event_queue.append("8개의 경로 방을 통과하면 보스가 기다립니다.")
    session.message = await interaction.followup.send(
        embed=create_dungeon_embed(session, event_queue), wait=True
    )
    try:
        control_message = await interaction.user.send(
            embed=discord.Embed(title="🗺️ 경로를 생성하는 중…", color=discord.Color.blurple())
        )
    except discord.Forbidden:
        event_queue.append("⚠️ DM이 닫혀 있어 로그라이크 탐험을 시작할 수 없습니다.")
        await _update_dungeon_log(session, event_queue)
        session.ended = True
        return False
    session.dm_message = control_message

    while session.exploration_step < ROGUELIKE.ROUTE_ROOMS and not session.ended:
        room = session.exploration_step + 1
        if not session.route_offers:
            force_treasure = session.explore_buffs.get("force_treasure", 0) > 0
            from service.dungeon.skill import get_passive_effect_bonuses

            passive = get_passive_effect_bonuses(session.user)
            offers = generate_route_offers(
                room,
                session.run_rng,
                force_treasure=force_treasure,
                secret_find_bonus=passive.get("secret_find", 0.0),
            )
            session.route_offers = [offer.to_dict() for offer in offers]
            if force_treasure:
                session.explore_buffs["force_treasure"] -= 1
                if session.explore_buffs["force_treasure"] <= 0:
                    session.explore_buffs.pop("force_treasure", None)
        session.selected_route_token = None
        offer = await wait_for_route_choice(session, interaction.user, control_message)
        if not offer:
            if session.ended:
                event_queue.append("📜 귀환 스크롤로 현재 보상을 100% 유지하고 귀환합니다.")
                return await _handle_dungeon_return(session, interaction, event_queue)
            apply_failure_penalty(session)
            event_queue.append("⌛ 응답 시간이 지나 미확정 EXP·골드 30%를 잃고 귀환합니다.")
            return await _handle_dungeon_return(session, interaction, event_queue)

        session.status = SessionType.EVENT
        result = await _resolve_route(session, interaction, offer, control_message)
        from service.telemetry import record_game_event
        await record_game_event(
            "roguelike_route_selected",
            user=session.user,
            guild_id=getattr(session, "origin_guild_id", None),
            content_type="roguelike",
            run_nonce=str(getattr(session, "run_nonce", "") or "") or None,
            metrics={
                "room": room,
                "kind": offer.kind.value,
                "risk": offer.risk,
                "reward_grade": offer.reward_grade,
                "hp_after": session.user.now_hp,
            },
        )
        session.status = SessionType.IDLE
        session.exploration_step += 1
        session.route_offers = []
        session.selected_route_token = None
        event_queue.append(f"[{session.exploration_step}방] {result}")
        await _update_dungeon_log(session, event_queue)
        if session.user.now_hp <= 0:
            return await _handle_player_death(session, interaction, event_queue)

        if session.exploration_step in ROGUELIKE.AUGMENT_ROOMS:
            if not await wait_for_skill_augment(session, interaction.user, control_message, _active_skills(session)):
                if session.ended:
                    event_queue.append("📜 귀환 스크롤로 현재 보상을 100% 유지하고 귀환합니다.")
                    return await _handle_dungeon_return(session, interaction, event_queue)
                apply_failure_penalty(session)
                event_queue.append("⌛ 개조 선택 시간이 지나 보상 30%를 잃고 귀환합니다.")
                return await _handle_dungeon_return(session, interaction, event_queue)

    session.exploration_step = ROGUELIKE.BOSS_STAGE
    session.roguelike_combat_kind = "boss"
    session.roguelike_resolution_seed = session.run_rng.getrandbits(63)
    session.roguelike_stat_scale = 1.0
    session.roguelike_skip_flee = True
    event_queue.append("👑 보스방에 도착했습니다!")
    await _update_dungeon_log(session, event_queue)
    from service.dungeon.encounter_processor import _process_monster_encounter
    boss_result = await _process_monster_encounter(session, interaction)
    event_queue.append(boss_result)
    session.roguelike_combat_kind = None
    session.roguelike_skip_flee = False
    if session.user.now_hp <= 0:
        return await _handle_player_death(session, interaction, event_queue)
    return await _handle_dungeon_clear(session, interaction, event_queue)
