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

from config import COMBAT, DUNGEON, EmbedColor
from DTO.dungeon_control import DungeonControlView
from DTO.fight_or_flee import FightOrFleeView
from exceptions import MonsterNotFoundError, MonsterSpawnNotFoundError
from models import Monster, User
from models.repos.dungeon_repo import find_all_dungeon_spawn_monster_by
from models.repos.monster_repo import find_monster_by_id
from service.dungeon.encounter_service import EncounterFactory
from service.dungeon.encounter_types import EncounterType
from service.session import DungeonSession, SessionType, set_combat_state

logger = logging.getLogger(__name__)


# =============================================================================
# 전투 보상 계산 상수
# =============================================================================

BASE_EXP_PER_MONSTER = 20
"""몬스터당 기본 경험치"""

BASE_GOLD_PER_MONSTER = 10
"""몬스터당 기본 골드"""


# =============================================================================
# 메인 던전 루프
# =============================================================================


async def start_dungeon(
    session: DungeonSession,
    interaction: discord.Interaction
) -> bool:
    """
    던전 탐험 메인 루프

    스텝 기반 진행으로 다양한 인카운터를 처리하고,
    클리어/사망/귀환에 따른 결과를 처리합니다.

    Args:
        session: 던전 세션
        interaction: Discord 인터랙션

    Returns:
        탐험 완료 여부 (True: 클리어/귀환, False: 사망)
    """
    logger.info(f"Dungeon started: user={session.user.discord_id}, dungeon={session.dungeon.id}")

    event_queue: deque[str] = deque(maxlen=COMBAT.EVENT_QUEUE_MAX_LENGTH)
    event_queue.append(f"🚪 {session.dungeon.name}에 입장했다...")

    session.user.now_hp = session.user.hp

    # 던전 레벨에 따른 max_steps 설정
    session.max_steps = _calculate_dungeon_steps(session.dungeon)

    # 공개 메시지 전송
    public_embed = _create_dungeon_embed(session, event_queue)
    message = await interaction.followup.send(embed=public_embed, wait=True)
    session.message = message

    # DM 컨트롤 메시지 전송
    await _send_control_dm(session, interaction, event_queue)

    await asyncio.sleep(COMBAT.MAIN_LOOP_DELAY)

    # 메인 루프
    while not session.ended and session.user.now_hp > 0:
        # 던전 클리어 체크
        if session.is_dungeon_cleared():
            return await _handle_dungeon_clear(session, interaction, event_queue)

        session.status = SessionType.EVENT
        event_result = await _process_encounter(session, interaction)
        session.status = SessionType.IDLE
        event_queue.append(event_result)

        await _update_dungeon_log(session, event_queue)
        await asyncio.sleep(COMBAT.MAIN_LOOP_DELAY)

    # 사망 또는 수동 종료
    if session.user.now_hp <= 0:
        return await _handle_player_death(session, interaction, event_queue)

    # 수동 귀환 (session.ended = True)
    return await _handle_dungeon_return(session, interaction, event_queue)


def _calculate_dungeon_steps(dungeon) -> int:
    """
    던전 스텝 수 계산

    Args:
        dungeon: 던전 객체

    Returns:
        클리어에 필요한 스텝 수
    """
    # 기본 15 + 던전 레벨에 따라 증가
    base_steps = 15
    level_bonus = (dungeon.require_level // 10) * 5 if dungeon else 0
    return base_steps + level_bonus


async def _handle_dungeon_clear(
    session: DungeonSession,
    interaction: discord.Interaction,
    event_queue: deque[str]
) -> bool:
    """
    던전 클리어 처리

    Args:
        session: 던전 세션
        interaction: Discord 인터랙션
        event_queue: 이벤트 큐

    Returns:
        True (성공)
    """
    logger.info(f"Dungeon cleared: user={session.user.discord_id}")

    # 클리어 보너스 (20%)
    bonus_exp = int(session.total_exp * 0.2)
    bonus_gold = int(session.total_gold * 0.2)

    session.total_exp += bonus_exp
    session.total_gold += bonus_gold

    event_queue.append(
        f"🎉 던전 클리어!\n"
        f"   클리어 보너스: 경험치 +{bonus_exp}, 골드 +{bonus_gold}"
    )

    await _update_dungeon_log(session, event_queue)

    # 결과 요약 메시지
    await _send_dungeon_summary(session, interaction, "클리어")

    session.ended = True
    return True


async def _handle_player_death(
    session: DungeonSession,
    interaction: discord.Interaction,
    event_queue: deque[str]
) -> bool:
    """
    플레이어 사망 처리

    Args:
        session: 던전 세션
        interaction: Discord 인터랙션
        event_queue: 이벤트 큐

    Returns:
        False (실패)
    """
    logger.info(f"Player death: user={session.user.discord_id}")

    # 골드 10% 손실
    gold_lost = int(session.total_gold * 0.1)
    session.total_gold = max(0, session.total_gold - gold_lost)

    # HP 50%로 부활
    session.user.now_hp = session.user.hp // 2

    event_queue.append(
        f"💀 사망...\n"
        f"   골드 {gold_lost} 손실, 획득 보상 감소"
    )

    await _update_dungeon_log(session, event_queue)

    # 결과 요약 메시지
    await _send_dungeon_summary(session, interaction, "사망")

    session.ended = True
    return False


async def _handle_dungeon_return(
    session: DungeonSession,
    interaction: discord.Interaction,
    event_queue: deque[str]
) -> bool:
    """
    던전 귀환 처리 (자발적 탈출)

    Args:
        session: 던전 세션
        interaction: Discord 인터랙션
        event_queue: 이벤트 큐

    Returns:
        True (성공)
    """
    logger.info(f"Dungeon return: user={session.user.discord_id}")

    event_queue.append("🚶 던전에서 귀환했다...")

    await _update_dungeon_log(session, event_queue)

    # 결과 요약 메시지
    await _send_dungeon_summary(session, interaction, "귀환")

    return True


async def _send_dungeon_summary(
    session: DungeonSession,
    interaction: discord.Interaction,
    result_type: str
) -> None:
    """
    던전 결과 요약 메시지 전송

    Args:
        session: 던전 세션
        interaction: Discord 인터랙션
        result_type: 결과 타입 (클리어/사망/귀환)
    """
    result_emoji = {"클리어": "🏆", "사망": "💀", "귀환": "🚶"}.get(result_type, "📜")

    embed = discord.Embed(
        title=f"{result_emoji} {session.dungeon.name} - {result_type}",
        color=discord.Color.gold() if result_type == "클리어" else discord.Color.greyple()
    )

    embed.add_field(
        name="탐험 결과",
        value=(
            f"진행도: {session.exploration_step}/{session.max_steps}\n"
            f"처치 몬스터: {session.monsters_defeated}"
        ),
        inline=True
    )

    embed.add_field(
        name="획득 보상",
        value=(
            f"💎 경험치: {session.total_exp}\n"
            f"💰 골드: {session.total_gold}"
        ),
        inline=True
    )

    embed.add_field(
        name="최종 상태",
        value=f"❤️ HP: {session.user.now_hp}/{session.user.hp}",
        inline=False
    )

    try:
        await interaction.user.send(embed=embed)
    except discord.Forbidden:
        pass  # DM 불가능한 경우 무시


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
    인카운터 처리

    다양한 유형의 인카운터를 확률에 따라 생성하고 처리합니다.
    - 몬스터 (60%): 전투 또는 도주
    - 보물상자 (10%): 골드/아이템 획득
    - 함정 (10%): HP 피해
    - 랜덤 이벤트 (10%): 축복/저주
    - NPC (5%): 상인/치료사/현자
    - 숨겨진 방 (5%): 희귀 보상

    Args:
        session: 던전 세션
        interaction: Discord 인터랙션

    Returns:
        인카운터 결과 메시지
    """
    # 탐험 스텝 증가
    session.exploration_step += 1

    # 인카운터 타입 결정
    encounter_type = EncounterFactory.roll_encounter_type()

    logger.debug(
        f"Encounter rolled: user={session.user.discord_id}, "
        f"step={session.exploration_step}, type={encounter_type.value}"
    )

    # 몬스터 인카운터는 별도 처리
    if encounter_type == EncounterType.MONSTER:
        return await _process_monster_encounter(session, interaction)

    # 그 외 인카운터
    encounter = EncounterFactory.create_encounter(encounter_type)
    result = await encounter.execute(session, interaction)

    logger.info(
        f"Encounter completed: user={session.user.discord_id}, "
        f"type={encounter_type.value}, gold={result.gold_gained}, exp={result.exp_gained}"
    )

    return result.message


async def _process_monster_encounter(
    session: DungeonSession,
    interaction: discord.Interaction
) -> str:
    """
    몬스터 인카운터 처리

    Args:
        session: 던전 세션
        interaction: Discord 인터랙션

    Returns:
        전투 결과 메시지
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
        return await _attempt_flee(session, monster)

    return await _execute_combat(session, interaction, monster)


async def _attempt_flee(session: DungeonSession, monster: Monster) -> str:
    """
    도주 시도

    Args:
        session: 던전 세션
        monster: 도주 대상 몬스터

    Returns:
        도주 결과 메시지
    """
    user_name = session.user.get_name()

    # 엘리트/보스는 도주 불가 (현재 몬스터에 타입 필드 없으므로 모두 일반으로 처리)
    # TODO: monster.monster_type 필드 추가 후 조건 추가

    # 도주 확률 판정
    if random.random() < COMBAT.FLEE_SUCCESS_RATE:
        logger.info(f"Flee success: user={session.user.discord_id}")
        return f"🏃 {user_name}은(는) {monster.name}에게서 도망쳤다!"

    # 도주 실패 시 몬스터 공격
    damage = monster.attack
    session.user.now_hp -= damage
    session.user.now_hp = max(session.user.now_hp, 0)

    logger.info(f"Flee failed: user={session.user.discord_id}, damage={damage}")
    return f"💨 도망 실패! {monster.name}의 공격으로 {damage} 피해를 받았다!"


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
    try:
        await view.message.delete()
    except discord.NotFound:
        pass

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

    # 전투 상태 설정
    set_combat_state(session.user_id, True)

    combat_log: deque[str] = deque(maxlen=COMBAT.COMBAT_LOG_MAX_LENGTH)
    embed = _create_battle_embed(session.user, monster, combat_log)
    combat_message = await interaction.user.send(embed=embed)

    turn_count = 1

    try:
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

        # 전투 결과 처리 및 보상
        return _process_combat_result(session, monster, turn_count)

    finally:
        # 전투 상태 해제 (항상 실행)
        set_combat_state(session.user_id, False)


def _process_combat_result(
    session: DungeonSession,
    monster: Monster,
    turn_count: int
) -> str:
    """
    전투 결과 처리 및 보상 지급

    Args:
        session: 던전 세션
        monster: 전투한 몬스터
        turn_count: 전투에 소요된 턴 수

    Returns:
        결과 메시지
    """
    user = session.user

    # 패배 시
    if user.now_hp <= 0:
        logger.info(f"Combat defeat: user={user.discord_id}, monster={monster.name}")
        if monster.now_hp <= 0:
            return f"⚔️ {user.get_name()}과 {monster.name}은 동시에 쓰러졌다!"
        return f"💀 {user.get_name()}은(는) {monster.name}에게 패배했다..."

    # 승리 시 - 보상 계산
    monster_level = session.dungeon.require_level if session.dungeon else 1

    # 경험치 계산: 기본 * (1 + 몬스터레벨/10)
    exp_gained = int(BASE_EXP_PER_MONSTER * (1 + monster_level / 10))

    # 골드 계산: 기본 * (1 + 몬스터레벨/10)
    gold_gained = int(BASE_GOLD_PER_MONSTER * (1 + monster_level / 10))

    # 세션에 누적
    session.total_exp += exp_gained
    session.total_gold += gold_gained
    session.monsters_defeated += 1

    logger.info(
        f"Combat victory: user={user.discord_id}, monster={monster.name}, "
        f"exp={exp_gained}, gold={gold_gained}, turns={turn_count}"
    )

    return (
        f"🏆 {monster.name}에게 승리! ({turn_count}턴)\n"
        f"💎 경험치 +{exp_gained}, 골드 +{gold_gained}"
    )


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
    else:
        # 스킬이 없으면 기본 공격
        damage = first.attack
        second.now_hp -= damage
        second.now_hp = max(second.now_hp, 0)
        attack_logs.append(f"{first.get_name()}의 기본 공격! {second.get_name()}에게 {damage} 피해!")

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
    else:
        # 스킬이 없으면 기본 공격
        damage = second.attack
        first.now_hp -= damage
        first.now_hp = max(first.now_hp, 0)
        attack_logs.append(f"{second.get_name()}의 기본 공격! {first.get_name()}에게 {damage} 피해!")

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

    # 진행도 바 생성
    progress = min(session.exploration_step / session.max_steps, 1.0)
    progress_bar = _create_progress_bar(progress)

    embed.add_field(
        name="탐험 진행도",
        value=f"{progress_bar} {session.exploration_step}/{session.max_steps}",
        inline=False
    )

    embed.add_field(
        name="내 정보",
        value=(
            f"❤️ 체력: {session.user.now_hp}/{session.user.hp}\n"
            f"💎 획득 경험치: {session.total_exp} | 골드: {session.total_gold}\n"
            f"⚔️ 처치 몬스터: {session.monsters_defeated}"
        ),
        inline=False
    )

    log_text = "\n".join(event_queue)
    embed.add_field(
        name="진행 상황",
        value=f"```{log_text}```",
        inline=False
    )

    return embed


def _create_progress_bar(progress: float, length: int = 10) -> str:
    """
    진행도 바 생성

    Args:
        progress: 진행률 (0.0 ~ 1.0)
        length: 바 길이

    Returns:
        진행도 바 문자열
    """
    filled = int(progress * length)
    empty = length - filled
    return "█" * filled + "░" * empty
