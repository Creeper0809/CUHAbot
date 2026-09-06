"""Guild-scoped roguelike records and notable boss reward announcements."""

from __future__ import annotations

import discord

from models.game_system import DungeonRunRecord
from service.game_settings import get_guild_settings


async def _brag_channel(bot, guild_id: int | None):
    settings = await get_guild_settings(guild_id)
    if not settings or not settings.brag_channel_id:
        return None
    channel = bot.get_channel(settings.brag_channel_id)
    if channel:
        return channel
    try:
        return await bot.fetch_channel(settings.brag_channel_id)
    except (discord.Forbidden, discord.NotFound, discord.HTTPException):
        return None


async def record_and_announce_clear(session, interaction: discord.Interaction) -> bool:
    if not session.roguelike_enabled or not session.origin_guild_id:
        return False
    elapsed_ms = max(1, int((__import__("time").monotonic() - session.start_time) * 1000))
    record = await DungeonRunRecord.get_or_none(
        user_id=session.user.id, dungeon_id=session.dungeon.id
    )
    is_record = record is None or elapsed_ms < record.best_clear_milliseconds
    if record is None:
        await DungeonRunRecord.create(
            user_id=session.user.id,
            dungeon_id=session.dungeon.id,
            best_clear_milliseconds=elapsed_ms,
        )
    elif is_record:
        record.best_clear_milliseconds = elapsed_ms
        await record.save(update_fields=["best_clear_milliseconds", "updated_at"])

    best_box = any(box_id in {5943, 5946} for box_id in session.boss_reward_item_ids)
    if not is_record and not best_box:
        return False
    channel = await _brag_channel(interaction.client, session.origin_guild_id)
    if not channel:
        return False
    lines = []
    if is_record:
        lines.append(f"🏁 개인 최고 기록 갱신 · **{elapsed_ms / 1000:.2f}초**")
    if best_box:
        lines.append("🎁 보스 보상에서 **최상급 상자** 획득")
    await channel.send(
        embed=discord.Embed(
            title=f"🏆 {interaction.user.display_name} · {session.dungeon.name}",
            description="\n".join(lines),
            color=discord.Color.gold(),
        ),
        allowed_mentions=discord.AllowedMentions.none(),
    )
    return True
