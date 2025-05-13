import asyncio
from collections import deque

import discord
from discord import Embed

from DTO.dungeon_control import DungeonControlView
from DTO.fight_or_flee import FightOrFleeView
from models import Monster
from models.repos.dungeon_repo import find_all_dungeon_spawn_monster_by
from models.repos.monster_repo import find_monster_by_id
from service.dungeon.skill import Skill
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

async def fight(session: DungeonSession, interaction: discord.Interaction):
    # 몬스터 스폰 확률에 따라 선택
    monsters_spawn = find_all_dungeon_spawn_monster_by(session.dungeon.id)
    random_monster_spawn = random.choices(
        population=monsters_spawn,
        weights=[spawn.prob for spawn in monsters_spawn],
        k=1
    )[0]
    monster = find_monster_by_id(random_monster_spawn.monster_id)
    if not monster:
        return "몬스터 정보를 찾을 수 없습니다."

    # 전투 여부 확인
    will_fight = await ask_to_fight(interaction, monster)
    if will_fight is None:
        return f"{session.user.get_name()}은 아무 행동도 하지 않았다..."
    elif not will_fight:
        return f"{session.user.get_name()}은 도망쳤다!"

    logs = deque(maxlen=6)
    embed = create_battle_embed(session.user, monster, logs)
    combat_message = await interaction.user.send(embed=embed)
    turn_count = 1

    def determine_turn_order(user, monster):
        speed_diff = user.speed - monster.speed
        advantage = max(min(speed_diff, 50), -50)
        user_prob = 50 + advantage
        return "user" if random.random() < (user_prob / 100) else "monster"

    while True:
        first, second = (session.user, monster) if determine_turn_order(session.user, monster) == "user" else (
        monster, session.user)
        first_skill = first.next_skill()
        second_skill = second.next_skill()

        start_logs = [
            log for log in [
                first_skill.on_turn_start(first, second),
                second_skill.on_turn_start(second, first)
            ] if log and log.strip()
        ]
        if start_logs:
            logs.append(f"[{turn_count}턴 시작 페이즈]\n" + "\n".join(start_logs))
            await combat_message.edit(embed=create_battle_embed(session.user, monster, logs))
            await asyncio.sleep(1)

        attack_logs = []
        first_log = first_skill.on_turn(first, second)
        if first_log and first_log.strip():
            attack_logs.append(first_log)

        if session.user.now_hp <= 0 or monster.now_hp <= 0:
            if attack_logs:
                logs.append(f"[{turn_count}턴 공격 페이즈]\n" + "\n".join(attack_logs))
            break

        second_log = second_skill.on_turn(second, first)
        if second_log and second_log.strip():
            attack_logs.append(second_log)

        if attack_logs:
            logs.append(f"[{turn_count}턴 공격 페이즈]\n" + "\n".join(attack_logs))
            await combat_message.edit(embed=create_battle_embed(session.user, monster, logs))
            await asyncio.sleep(1)

        end_logs = [
            log for log in [
                first_skill.on_turn_end(first, second),
                second_skill.on_turn_end(second, first)
            ] if log and log.strip()
        ]
        if end_logs:
            logs.append(f"[{turn_count}턴 엔드 페이즈]\n" + "\n".join(end_logs))
            await combat_message.edit(embed=create_battle_embed(session.user, monster, logs))
            await asyncio.sleep(1)

        turn_count += 1

    await combat_message.edit(embed=create_battle_embed(session.user, monster, logs))
    await asyncio.sleep(2)
    await combat_message.delete()

    # 승자 판단
    if session.user.now_hp <= 0 and monster.now_hp <= 0:
        return f"{session.user.get_name()}과 {monster.name}은 동시에 쓰러졌다!"
    elif session.user.now_hp <= 0:
        return f"{session.user.get_name()}은 {monster.name}에게 패배했다..."
    else:
        return f"{session.user.get_name()}의 승리!"


def create_battle_embed(player : User, monster : Monster,log):
    embed = Embed(
        title=f"{player.get_name()} 와 {monster.get_name()} 의 전투",
        color=0xFF5733
    )

    embed.add_field(
        name=f"👤 {player.get_name()}",
        value=f"체력:{player.now_hp}/{player.hp}\n**버프**\n" + ("\n".join(player.status) or "없음"),
        inline=True
    )

    embed.add_field(
        name=f"👹 {monster.get_name()}",
        value=f"체력:{monster.now_hp}/{monster.hp}\n**버프**\n" + ("\n".join(monster.status) or "없음"),
        inline=True
    )

    embed.add_field(
        name="⚔️ 전투 로그",
        value="\n".join(log) or "전투 시작 전입니다.",
        inline=False
    )
    return embed

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
