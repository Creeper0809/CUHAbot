"""Aggregate notable box results into a configured guild channel."""

from __future__ import annotations

import discord

from service.game_settings import get_guild_settings
from service.item.box_open_service import BoxOpenBatch


async def announce_notable_box_results(
    bot: discord.Client,
    guild_id: int | None,
    user: discord.abc.User,
    batch: BoxOpenBatch,
) -> bool:
    if not guild_id:
        return False
    notable = [
        outcome for outcome in batch.outcomes
        if outcome.grade >= 5 or outcome.new_collection or outcome.hard_pity_triggered
    ]
    if not notable:
        return False
    settings = await get_guild_settings(guild_id)
    if not settings or not settings.brag_channel_id:
        return False
    channel = bot.get_channel(settings.brag_channel_id)
    if not channel:
        try:
            channel = await bot.fetch_channel(settings.brag_channel_id)
        except (discord.Forbidden, discord.NotFound, discord.HTTPException):
            return False
    lines = []
    for outcome in notable[:10]:
        badge = " 🎯천장" if outcome.hard_pity_triggered else ""
        first = " 🆕첫 도감" if outcome.new_collection else ""
        lines.append(f"• **[{outcome.grade_name or '골드'}] {outcome.name}**{badge}{first}")
    await channel.send(
        embed=discord.Embed(
            title=f"🌟 {user.display_name}님의 상자 대박!",
            description="\n".join(lines),
            color=discord.Color.gold(),
        ),
        allowed_mentions=discord.AllowedMentions.none(),
    )
    return True
