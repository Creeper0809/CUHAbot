"""
던전 메인 루프 - 탐험 시작, 클리어/사망/귀환, 결과 요약

던전 탐험의 전체 라이프사이클을 관리합니다.
"""
import asyncio
import logging
from collections import deque

import discord

from config import COMBAT, DUNGEON
from models import UserStatEnum
from views.dungeon_control import DungeonControlView
from service.economy.reward_service import RewardService
from service.session import DungeonSession, SessionType
from service.event import EventBus, GameEvent, GameEventType

logger = logging.getLogger(__name__)


async def start_dungeon(session: DungeonSession, interaction: discord.Interaction) -> bool:
    """
    던전 탐험 메인 루프

    Args:
        session: 던전 세션
        interaction: Discord 인터랙션

    Returns:
        탐험 완료 여부 (True: 클리어/귀환, False: 사망)
    """
    from service.dungeon.encounter_processor import process_encounter
    from service.dungeon.dungeon_ui import create_dungeon_embed

    logger.info(f"Dungeon started: user={session.user.discord_id}, dungeon={session.dungeon.id}")

    # 이벤트 발행: 던전 탐험
    event_bus = EventBus()
    await event_bus.publish(GameEvent(
        type=GameEventType.DUNGEON_EXPLORED,
        user_id=session.user.id,
        data={
            "dungeon_id": session.dungeon.id,
            "dungeon_name": session.dungeon.name
        }
    ))

    event_queue: deque[str] = deque(maxlen=COMBAT.EVENT_QUEUE_MAX_LENGTH)
    event_queue.append(f"━━━ 🏰 **탐험 시작** ━━━")
    event_queue.append(f"🚪 {session.dungeon.name}에 입장했다...")

    if session.user.now_hp <= 0:
        session.user.now_hp = 1

    session.max_steps = _calculate_dungeon_steps(session.dungeon)

    # 공개 메시지 전송
    public_embed = create_dungeon_embed(session, event_queue)
    message = await interaction.followup.send(embed=public_embed, wait=True)
    session.message = message

    # DM 컨트롤 메시지 전송
    await _send_control_dm(session, interaction, event_queue)

    await asyncio.sleep(COMBAT.MAIN_LOOP_DELAY)

    # 메인 루프
    while not session.ended and session.user.now_hp > 0:
        if session.is_dungeon_cleared():
            return await _handle_dungeon_clear(session, interaction, event_queue)

        session.status = SessionType.EVENT
        event_result = await process_encounter(session, interaction)
        session.status = SessionType.IDLE
        event_queue.append(event_result)

        await _update_dungeon_log(session, event_queue)
        await asyncio.sleep(COMBAT.MAIN_LOOP_DELAY)

    if session.user.now_hp <= 0:
        return await _handle_player_death(session, interaction, event_queue)

    return await _handle_dungeon_return(session, interaction, event_queue)


def _calculate_dungeon_steps(dungeon) -> int:
    """던전 스텝 수 계산"""
    base_steps = DUNGEON.BASE_STEPS
    level_bonus = (dungeon.require_level // DUNGEON.LEVEL_BONUS_INTERVAL) * DUNGEON.LEVEL_BONUS_PER_INTERVAL if dungeon else 0
    return base_steps + level_bonus


# =============================================================================
# 결과 처리
# =============================================================================


async def _handle_dungeon_clear(session, interaction, event_queue) -> bool:
    """던전 클리어 처리"""
    logger.info(f"Dungeon cleared: user={session.user.discord_id}")

    bonus_exp = int(session.total_exp * DUNGEON.CLEAR_BONUS_MULTIPLIER)
    bonus_gold = int(session.total_gold * DUNGEON.CLEAR_BONUS_MULTIPLIER)

    session.total_exp += bonus_exp
    session.total_gold += bonus_gold

    event_queue.append("━━━ 🏆 **클리어!** ━━━")
    event_queue.append(
        f"🎉 던전을 정복했다!\n"
        f"⭐ 클리어 보너스: **+{bonus_exp}** EXP, **+{bonus_gold}** G"
    )

    await _update_dungeon_log(session, event_queue)

    reward_result = await RewardService.apply_rewards(session.user, session.total_exp, session.total_gold)
    await _send_dungeon_summary(session, interaction, "클리어", reward_result)

    session.ended = True
    return True


async def _handle_player_death(session, interaction, event_queue) -> bool:
    """플레이어 사망 처리"""
    logger.info(f"Player death: user={session.user.discord_id}")

    gold_lost = int(session.total_gold * DUNGEON.DEATH_GOLD_LOSS)
    session.total_gold = max(0, session.total_gold - gold_lost)
    session.user.now_hp = 1

    event_queue.append("━━━ 💀 **사망** ━━━")
    event_queue.append(
        f"💀 쓰러졌다...\n"
        f"💸 골드 **-{gold_lost}** 손실\n"
        f"⚠️ HP가 1로 감소! 회복이 필요합니다."
    )

    await _update_dungeon_log(session, event_queue)

    reward_result = await RewardService.apply_rewards(session.user, session.total_exp, session.total_gold)
    await _send_dungeon_summary(session, interaction, "사망", reward_result)

    session.ended = True
    return False


async def _handle_dungeon_return(session, interaction, event_queue) -> bool:
    """던전 귀환 처리"""
    logger.info(f"Dungeon return: user={session.user.discord_id}")

    event_queue.append("━━━ 🚶 **귀환** ━━━")
    event_queue.append("🚶 던전에서 안전하게 귀환했다...")

    await _update_dungeon_log(session, event_queue)

    reward_result = await RewardService.apply_rewards(session.user, session.total_exp, session.total_gold)
    await _send_dungeon_summary(session, interaction, "귀환", reward_result)

    return True


# =============================================================================
# 요약/DM/로그 업데이트
# =============================================================================


async def _send_dungeon_summary(session, interaction, result_type: str, reward_result=None) -> None:
    """던전 결과 요약 메시지 전송"""
    result_emoji = {"클리어": "🏆", "사망": "💀", "귀환": "🚶"}.get(result_type, "📜")

    embed = discord.Embed(
        title=f"{result_emoji} {session.dungeon.name} - {result_type}",
        color=discord.Color.gold() if result_type == "클리어" else discord.Color.greyple()
    )

    embed.add_field(
        name="탐험 결과",
        value=f"진행도: {session.exploration_step}/{session.max_steps}\n처치 몬스터: {session.monsters_defeated}",
        inline=True
    )

    embed.add_field(
        name="획득 보상",
        value=f"💎 경험치: +{session.total_exp}\n💰 골드: +{session.total_gold}",
        inline=True
    )

    if reward_result and reward_result.level_up:
        lu = reward_result.level_up
        embed.add_field(
            name="🎉 레벨 업!",
            value=f"Lv.{lu.old_level} → Lv.{lu.new_level}\n📊 스탯 포인트 +{lu.stat_points_gained}\n💡 /스탯 명령어로 분배하세요!",
            inline=False
        )

    embed.add_field(
        name="최종 상태",
        value=f"❤️ HP: {session.user.now_hp}/{session.user.hp}\n📊 Lv.{session.user.level} | 💰 {session.user.gold}",
        inline=False
    )

    try:
        await interaction.user.send(embed=embed)
    except discord.Forbidden:
        pass


async def _send_control_dm(session, interaction, event_queue) -> None:
    """DM으로 던전 컨트롤 메시지 전송"""
    from service.dungeon.dungeon_ui import create_dungeon_embed

    control_embed = create_dungeon_embed(session, event_queue)
    control_embed.add_field(
        name="명령",
        value="🛑 던전 종료 버튼을 눌러 탐험을 종료할 수 있습니다."
    )

    try:
        view = DungeonControlView(session)
        dm_msg = await interaction.user.send(embed=control_embed, view=view)
        view.message = dm_msg
        session.dm_message = dm_msg
    except discord.Forbidden:
        await interaction.followup.send(
            "⚠️ DM을 보낼 수 없습니다. 던전 제어가 제한됩니다.",
            ephemeral=True
        )


async def _update_dungeon_log(session, event_queue) -> None:
    """던전 로그 업데이트"""
    from service.dungeon.dungeon_ui import create_dungeon_embed

    update_embed = create_dungeon_embed(session, event_queue)

    if session.dm_message:
        try:
            session.dm_message = await session.dm_message.edit(embed=update_embed)
        except discord.NotFound:
            session.dm_message = None
    if session.message:
        try:
            session.message = await session.message.edit(embed=update_embed)
        except discord.NotFound:
            session.message = None
