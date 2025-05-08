import asyncio
from collections import deque

import discord

from service.session import DungeonSession
from models.repos.users_repo import *

async def start_dungeon(session : DungeonSession, interaction : discord.Interaction):
    event_queue = deque(maxlen=5)
    event_queue.append("...")

    # 임시
    session.user.now_hp = session.user.hp

    embed = make_dungeon_embed(session, session.dungeon, event_queue)
    message = await interaction.followup.send(embed=embed, wait=True)

    session.message = message
    while not session.ended and session.user.now_hp > 0:
        await asyncio.sleep(5)  # 이벤트 간격

        # 랜덤 이벤트 선택 (예: 전투, 상자, 회복)
        event_result = await fight(session, interaction)

        # 로그 저장
        event_queue.append(event_result)
        # UI 갱신
        event_text = make_dungeon_embed(session, session.dungeon, event_queue)
        await message.edit(embed=event_text)

    return True

async def fight(session : DungeonSession, interaction : discord.Interaction):
    session.user.now_hp -= 1
    return f"{interaction.user.display_name}의 승리"

def make_dungeon_embed(session, dungeon, logs) -> discord.Embed:
    embed = discord.Embed(
        title=f"🗺️ 던전: {dungeon.name}",
        description=dungeon.description,
        color=discord.Color.green()
    )
    embed.add_field(
        name="내 정보",
        value=f":heart: 체력: {session.user.now_hp}/{session.user.hp}",
        inline=False
    )
    embed.add_field(
        name="진행 상황",
        value=f"```{"\n".join(logs)}```",
        inline=False
    )
    return embed
