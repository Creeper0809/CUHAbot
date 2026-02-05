"""
던전 서비스

던전 탐험 및 전투 로직을 담당합니다.
"""
import asyncio
import logging
import random
from collections import deque
from typing import Optional

import discord
from discord import Embed

from config import COMBAT, EmbedColor
from DTO.dungeon_control import DungeonControlView
from DTO.fight_or_flee import FightOrFleeView
from exceptions import MonsterNotFoundError, MonsterSpawnNotFoundError
from models import Monster, User
from models.repos.dungeon_repo import find_all_dungeon_spawn_monster_by
from models.repos.monster_repo import find_monster_by_id
from service.session import DungeonSession, SessionType

logger = logging.getLogger(__name__)


# =============================================================================
# 메인 던전 루프
# =============================================================================


async def start_dungeon(
    session: DungeonSession,
    interaction: discord.Interaction
) -> bool:
    """
    던전 탐험 메인 루프

    Args:
        session: 던전 세션
        interaction: Discord 인터랙션

    Returns:
        탐험 완료 여부
    """
    logger.info(f"Dungeon started: user={session.user.discord_id}, dungeon={session.dungeon.id}")

    event_queue: deque[str] = deque(maxlen=COMBAT.EVENT_QUEUE_MAX_LENGTH)
    event_queue.append("...")

    session.user.now_hp = session.user.hp

    # 공개 메시지 전송
    public_embed = _create_dungeon_embed(session, event_queue)
    message = await interaction.followup.send(embed=public_embed, wait=True)
    session.message = message

    # DM 컨트롤 메시지 전송
    await _send_control_dm(session, interaction, event_queue)

    await asyncio.sleep(COMBAT.MAIN_LOOP_DELAY)

    # 메인 루프
    while not session.ended and session.user.now_hp > 0:
        session.status = SessionType.EVENT
        event_result = await _process_encounter(session, interaction)
        session.status = SessionType.IDLE
        event_queue.append(event_result)

        await _update_dungeon_log(session, event_queue)
        await asyncio.sleep(COMBAT.MAIN_LOOP_DELAY)

    logger.info(f"Dungeon ended: user={session.user.discord_id}")
    return True


async def _send_control_dm(
    session: DungeonSession,
    interaction: discord.Interaction,
    event_queue: deque[str]
) -> None:
    """DM으로 던전 컨트롤 메시지 전송"""
    control_embed = _create_dungeon_embed(session, event_queue)
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


async def _update_dungeon_log(
    session: DungeonSession,
    event_queue: deque[str]
) -> None:
    """던전 로그 업데이트"""
    update_embed = _create_dungeon_embed(session, event_queue)

    if session.dm_message:
        session.dm_message = await session.dm_message.edit(embed=update_embed)
    if session.message:
        session.message = await session.message.edit(embed=update_embed)


# =============================================================================
# 인카운터 처리
# =============================================================================


async def _process_encounter(
    session: DungeonSession,
    interaction: discord.Interaction
) -> str:
    """
    인카운터 처리 (몬스터 조우)

    Args:
        session: 던전 세션
        interaction: Discord 인터랙션

    Returns:
        인카운터 결과 메시지
    """
    try:
        monster = _spawn_random_monster(session.dungeon.id)
    except (MonsterNotFoundError, MonsterSpawnNotFoundError) as e:
        logger.error(f"Monster spawn error: {e}")
        return "몬스터 정보를 찾을 수 없습니다."

    will_fight = await _ask_fight_or_flee(interaction, monster)

    if will_fight is None:
        return f"{session.user.get_name()}은 아무 행동도 하지 않았다..."

    if not will_fight:
        return f"{session.user.get_name()}은 도망쳤다!"

    return await _execute_combat(session, interaction, monster)


def _spawn_random_monster(dungeon_id: int) -> Monster:
    """
    던전에서 랜덤 몬스터 스폰

    Args:
        dungeon_id: 던전 ID

    Returns:
        스폰된 몬스터 복사본

    Raises:
        MonsterSpawnNotFoundError: 스폰 정보가 없을 때
        MonsterNotFoundError: 몬스터를 찾을 수 없을 때
    """
    monsters_spawn = find_all_dungeon_spawn_monster_by(dungeon_id)
    if not monsters_spawn:
        raise MonsterSpawnNotFoundError(dungeon_id)

    random_spawn = random.choices(
        population=monsters_spawn,
        weights=[spawn.prob for spawn in monsters_spawn],
        k=1
    )[0]

    monster = find_monster_by_id(random_spawn.monster_id)
    if not monster:
        raise MonsterNotFoundError(random_spawn.monster_id)

    return monster


async def _ask_fight_or_flee(
    interaction: discord.Interaction,
    monster: Monster
) -> Optional[bool]:
    """
    전투/도주 선택 UI 표시

    Args:
        interaction: Discord 인터랙션
        monster: 조우한 몬스터

    Returns:
        True: 전투, False: 도주, None: 타임아웃
    """
    embed = discord.Embed(
        title=f"🐲 {monster.name} 이(가) 나타났다!",
        description=monster.description or "무서운 기운이 느껴진다...",
        color=EmbedColor.ERROR
    )
    embed.add_field(name="체력", value=f"{monster.hp}")
    embed.add_field(name="공격력", value=f"{monster.attack}")

    view = FightOrFleeView(user=interaction.user)
    msg = await interaction.user.send(embed=embed, view=view)
    view.message = msg

    await view.wait()
    await view.message.delete()

    return view.result


# =============================================================================
# 전투 시스템
# =============================================================================


async def _execute_combat(
    session: DungeonSession,
    interaction: discord.Interaction,
    monster: Monster
) -> str:
    """
    전투 실행

    Args:
        session: 던전 세션
        interaction: Discord 인터랙션
        monster: 전투할 몬스터

    Returns:
        전투 결과 메시지
    """
    logger.info(f"Combat started: user={session.user.discord_id}, monster={monster.name}")

    combat_log: deque[str] = deque(maxlen=COMBAT.COMBAT_LOG_MAX_LENGTH)
    embed = _create_battle_embed(session.user, monster, combat_log)
    combat_message = await interaction.user.send(embed=embed)

    turn_count = 1

    while session.user.now_hp > 0 and monster.now_hp > 0:
        turn_result = await _process_turn(
            session.user,
            monster,
            turn_count,
            combat_log,
            combat_message
        )

        if turn_result:  # 전투 종료
            break

        turn_count += 1

    # 전투 결과 표시 후 정리
    await combat_message.edit(embed=_create_battle_embed(session.user, monster, combat_log))
    await asyncio.sleep(COMBAT.COMBAT_END_DELAY)
    await combat_message.delete()

    return _get_combat_result_message(session.user, monster)


async def _process_turn(
    user: User,
    monster: Monster,
    turn_count: int,
    combat_log: deque[str],
    combat_message: discord.Message
) -> bool:
    """
    턴 처리

    Args:
        user: 유저
        monster: 몬스터
        turn_count: 현재 턴 수
        combat_log: 전투 로그
        combat_message: 전투 메시지

    Returns:
        전투 종료 여부 (True면 종료)
    """
    first, second = _determine_turn_order(user, monster)
    first_skill = first.next_skill()
    second_skill = second.next_skill()

    # 턴 시작 페이즈
    await _process_turn_start_phase(
        first, second, first_skill, second_skill,
        turn_count, combat_log, combat_message, user, monster
    )

    # 공격 페이즈
    combat_ended = await _process_attack_phase(
        first, second, first_skill, second_skill,
        turn_count, combat_log, combat_message, user, monster
    )

    if combat_ended:
        return True

    # 턴 종료 페이즈
    await _process_turn_end_phase(
        first, second, first_skill, second_skill,
        turn_count, combat_log, combat_message, user, monster
    )

    return False


def _determine_turn_order(user: User, monster: Monster) -> tuple:
    """
    턴 순서 결정

    Args:
        user: 유저
        monster: 몬스터

    Returns:
        (선공, 후공) 튜플
    """
    speed_diff = user.speed - monster.speed
    advantage = max(min(speed_diff, COMBAT.SPEED_ADVANTAGE_CAP), -COMBAT.SPEED_ADVANTAGE_CAP)
    user_prob = COMBAT.BASE_TURN_PROBABILITY + advantage

    if random.random() < (user_prob / 100):
        return user, monster
    return monster, user


async def _process_turn_start_phase(
    first, second, first_skill, second_skill,
    turn_count: int,
    combat_log: deque[str],
    combat_message: discord.Message,
    user: User,
    monster: Monster
) -> None:
    """턴 시작 페이즈 처리"""
    if not first_skill or not second_skill:
        return

    start_logs = [
        log for log in [
            first_skill.on_turn_start(first, second),
            second_skill.on_turn_start(second, first)
        ] if log and log.strip()
    ]

    if not start_logs:
        return

    combat_log.append(f"[{turn_count}턴 시작 페이즈]\n" + "\n".join(start_logs))
    await combat_message.edit(embed=_create_battle_embed(user, monster, combat_log))
    await asyncio.sleep(COMBAT.TURN_PHASE_DELAY)


async def _process_attack_phase(
    first, second, first_skill, second_skill,
    turn_count: int,
    combat_log: deque[str],
    combat_message: discord.Message,
    user: User,
    monster: Monster
) -> bool:
    """
    공격 페이즈 처리

    Returns:
        전투 종료 여부
    """
    attack_logs = []

    # 선공 공격
    if first_skill:
        first_log = first_skill.on_turn(first, second)
        if first_log and first_log.strip():
            attack_logs.append(first_log)

    # 전투 종료 체크 (선공 후)
    if user.now_hp <= 0 or monster.now_hp <= 0:
        if attack_logs:
            combat_log.append(f"[{turn_count}턴 공격 페이즈]\n" + "\n".join(attack_logs))
        return True

    # 후공 공격
    if second_skill:
        second_log = second_skill.on_turn(second, first)
        if second_log and second_log.strip():
            attack_logs.append(second_log)

    if attack_logs:
        combat_log.append(f"[{turn_count}턴 공격 페이즈]\n" + "\n".join(attack_logs))
        await combat_message.edit(embed=_create_battle_embed(user, monster, combat_log))
        await asyncio.sleep(COMBAT.TURN_PHASE_DELAY)

    return False


async def _process_turn_end_phase(
    first, second, first_skill, second_skill,
    turn_count: int,
    combat_log: deque[str],
    combat_message: discord.Message,
    user: User,
    monster: Monster
) -> None:
    """턴 종료 페이즈 처리"""
    if not first_skill or not second_skill:
        return

    end_logs = [
        log for log in [
            first_skill.on_turn_end(first, second),
            second_skill.on_turn_end(second, first)
        ] if log and log.strip()
    ]

    if not end_logs:
        return

    combat_log.append(f"[{turn_count}턴 엔드 페이즈]\n" + "\n".join(end_logs))
    await combat_message.edit(embed=_create_battle_embed(user, monster, combat_log))
    await asyncio.sleep(COMBAT.TURN_PHASE_DELAY)


def _get_combat_result_message(user: User, monster: Monster) -> str:
    """전투 결과 메시지 생성"""
    if user.now_hp <= 0 and monster.now_hp <= 0:
        return f"{user.get_name()}과 {monster.name}은 동시에 쓰러졌다!"

    if user.now_hp <= 0:
        return f"{user.get_name()}은 {monster.name}에게 패배했다..."

    return f"{monster.name}에게 {user.get_name()}의 승리!"


# =============================================================================
# 임베드 생성
# =============================================================================


def _create_battle_embed(
    player: User,
    monster: Monster,
    combat_log: deque[str]
) -> Embed:
    """전투 임베드 생성"""
    embed = Embed(
        title=f"{player.get_name()} vs {monster.get_name()}",
        color=EmbedColor.COMBAT
    )

    player_buffs = "\n".join([s.get_description() for s in player.status]) or "없음"
    embed.add_field(
        name=f"👤 {player.get_name()}",
        value=f"체력: {player.now_hp}/{player.hp}\n**버프**\n{player_buffs}",
        inline=True
    )

    monster_buffs = "\n".join([s.get_description() for s in monster.status]) or "없음"
    embed.add_field(
        name=f"👹 {monster.get_name()}",
        value=f"체력: {monster.now_hp}/{monster.hp}\n**버프**\n{monster_buffs}",
        inline=True
    )

    log_text = "\n".join(combat_log) or "전투 시작 전입니다."
    embed.add_field(
        name="⚔️ 전투 로그",
        value=log_text,
        inline=False
    )

    return embed


def _create_dungeon_embed(
    session: DungeonSession,
    event_queue: deque[str]
) -> discord.Embed:
    """던전 임베드 생성"""
    embed = discord.Embed(
        title=f"🗺️ 던전: {session.dungeon.name}",
        description=session.dungeon.description,
        color=EmbedColor.DUNGEON
    )

    embed.add_field(
        name="내 정보",
        value=f":heart: 체력: {session.user.now_hp}/{session.user.hp}",
        inline=False
    )

    log_text = "\n".join(event_queue)
    embed.add_field(
        name="진행 상황",
        value=f"```{log_text}```",
        inline=False
    )

    return embed
