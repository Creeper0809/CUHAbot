import asyncio
from collections import deque

import discord

from DTO.dungeon_control import DungeonControlView
#from DTO.fight_or_flee import FightOrFleeView
from models.repos.dungeon_repo import find_all_dungeon_spawn_monster_by
from models.repos.monster_repo import find_monster_by_id
from service.session import DungeonSession
from models.repos.users_repo import *

import random

async def start_dungeon(session: DungeonSession, interaction: discord.Interaction):
    event_queue = deque(maxlen=5)
    event_queue.append("...")

    session.user.now_hp = session.user.hp

    public_embed = make_dungeon_embed(session, session.dungeon, event_queue)
    message = await interaction.followup.send(embed=public_embed, wait=True)
    session.message = message

    control_embed = make_dungeon_embed(session, session.dungeon, event_queue)
    control_embed.add_field(name="명령", value="🛑 던전 종료 버튼을 눌러 탐험을 종료할 수 있습니다.")
    try:
        view = DungeonControlView(session)
        dm_msg = await interaction.user.send(embed=control_embed, view=view)
        view.message = dm_msg
        session.dm_message = dm_msg
    except discord.Forbidden:
        await interaction.followup.send("⚠️ DM을 보낼 수 없습니다. 던전 제어가 제한됩니다.", ephemeral=True)
        
    await asyncio.sleep(5)

    while not session.ended and session.user.now_hp > 0:
        event_result = await fight(session, interaction)
        event_queue.append(event_result)

        await update_log(session, event_queue)

        await asyncio.sleep(5)

    return True

async def update_log(session: DungeonSession, log):
    update_embed = make_dungeon_embed(session, session.dungeon, log)

    session.dm_message = await session.dm_message.edit(embed=update_embed)
    session.message = await session.message.edit(embed=update_embed)

async def fight(session : DungeonSession, interaction : discord.Interaction):
    monsters_spawn = find_all_dungeon_spawn_monster_by(session.dungeon.id)

    random_monster_spawn = random.choices(
        population=monsters_spawn,
        weights=[spawn.prob for spawn in monsters_spawn],
        k=1
    )[0]
    monster = find_monster_by_id(random_monster_spawn.monster_id)
    if not monster:
        return "몬스터 정보를 찾을 수 없습니다."

    will_fight = await ask_to_fight(interaction, monster)
    if will_fight is None:
        return f"{interaction.user.display_name}은 아무 행동도 하지 않았다..."
    elif not will_fight:
        return f"{interaction.user.display_name}은 도망쳤다!"
    
    # 임시 전투
    session.user.now_hp -= 1
    return f"{interaction.user.display_name}의 승리"


async def ask_to_fight(interaction: discord.Interaction, monster):
    embed = discord.Embed(
        title=f"🐲 {monster.name} 이(가) 나타났다!",
        description=monster.description or "무서운 기운이 느껴진다...",
        color=discord.Color.red()
    )
    embed.add_field(name="체력", value=f"{monster.hp}")
    embed.add_field(name="공격력", value=f"{monster.attack}")

    view = FightOrFleeView(user=interaction.user)
    msg = await interaction.user.send(embed=embed, view=view)
    view.message = msg

    await view.wait()
    await view.message.delete()
    return view.result

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
