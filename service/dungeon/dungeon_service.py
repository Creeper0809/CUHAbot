"""
던전 서비스

던전 탐험 및 전투 로직을 담당합니다.
"""
import asyncio
import logging
import random
from collections import deque
from typing import Optional, Union

import discord
from discord import Embed

from config import COMBAT, DUNGEON, DROP, EmbedColor
from DTO.dungeon_control import DungeonControlView
from DTO.fight_or_flee import FightOrFleeView
from exceptions import InventoryFullError, MonsterNotFoundError, MonsterSpawnNotFoundError
from models import Droptable, Item, Monster, MonsterTypeEnum, User, UserStatEnum
from models.repos.dungeon_repo import find_all_dungeon_spawn_monster_by
from models.repos.monster_repo import find_monster_by_id
from service.collection_service import CollectionService
from service.dungeon.buff import (
    can_entity_act, get_cc_effect_name, process_status_ticks,
    decay_all_durations, get_status_icons,
)
from service.dungeon.encounter_service import EncounterFactory
from service.dungeon.encounter_types import EncounterType
from service.inventory_service import InventoryService
from service.reward_service import RewardService
from service.dungeon.combat_context import CombatContext
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
    event_queue.append(f"━━━ 🏰 **탐험 시작** ━━━")
    event_queue.append(f"🚪 {session.dungeon.name}에 입장했다...")

    # HP가 0 이하면 최소 1로 보정 (버그 방지)
    if session.user.now_hp <= 0:
        session.user.now_hp = 1

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

    event_queue.append("━━━ 🏆 **클리어!** ━━━")
    event_queue.append(
        f"🎉 던전을 정복했다!\n"
        f"⭐ 클리어 보너스: **+{bonus_exp}** EXP, **+{bonus_gold}** G"
    )

    await _update_dungeon_log(session, event_queue)

    # 보상 적용 및 레벨업 처리
    reward_result = await RewardService.apply_rewards(
        session.user,
        session.total_exp,
        session.total_gold
    )

    # 결과 요약 메시지
    await _send_dungeon_summary(session, interaction, "클리어", reward_result)

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

    # 사망 시 HP 1로 설정 (치유 필요)
    session.user.now_hp = 1

    event_queue.append("━━━ 💀 **사망** ━━━")
    event_queue.append(
        f"💀 쓰러졌다...\n"
        f"💸 골드 **-{gold_lost}** 손실\n"
        f"⚠️ HP가 1로 감소! 회복이 필요합니다."
    )

    await _update_dungeon_log(session, event_queue)

    # 보상 적용 (사망해도 획득한 경험치/골드는 받음)
    reward_result = await RewardService.apply_rewards(
        session.user,
        session.total_exp,
        session.total_gold
    )

    # 결과 요약 메시지
    await _send_dungeon_summary(session, interaction, "사망", reward_result)

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

    event_queue.append("━━━ 🚶 **귀환** ━━━")
    event_queue.append("🚶 던전에서 안전하게 귀환했다...")

    await _update_dungeon_log(session, event_queue)

    # 보상 적용 (귀환해도 획득한 경험치/골드는 받음)
    reward_result = await RewardService.apply_rewards(
        session.user,
        session.total_exp,
        session.total_gold
    )

    # 결과 요약 메시지
    await _send_dungeon_summary(session, interaction, "귀환", reward_result)

    return True


async def _send_dungeon_summary(
    session: DungeonSession,
    interaction: discord.Interaction,
    result_type: str,
    reward_result=None
) -> None:
    """
    던전 결과 요약 메시지 전송

    Args:
        session: 던전 세션
        interaction: Discord 인터랙션
        result_type: 결과 타입 (클리어/사망/귀환)
        reward_result: 보상 적용 결과
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
            f"💎 경험치: +{session.total_exp}\n"
            f"💰 골드: +{session.total_gold}"
        ),
        inline=True
    )

    # 레벨업 정보
    if reward_result and reward_result.level_up:
        lu = reward_result.level_up
        embed.add_field(
            name="🎉 레벨 업!",
            value=(
                f"Lv.{lu.old_level} → Lv.{lu.new_level}\n"
                f"📊 스탯 포인트 +{lu.stat_points_gained}\n"
                f"💡 /스탯 명령어로 분배하세요!"
            ),
            inline=False
        )

    embed.add_field(
        name="최종 상태",
        value=(
            f"❤️ HP: {session.user.now_hp}/{session.user.hp}\n"
            f"📊 Lv.{session.user.level} | 💰 {session.user.cuha_point}"
        ),
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
        try:
            session.dm_message = await session.dm_message.edit(embed=update_embed)
        except discord.NotFound:
            session.dm_message = None  # 메시지가 삭제된 경우
    if session.message:
        try:
            session.message = await session.message.edit(embed=update_embed)
        except discord.NotFound:
            session.message = None


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
    몬스터 인카운터 처리 (그룹 전투 지원)

    Args:
        session: 던전 세션
        interaction: Discord 인터랙션

    Returns:
        전투 결과 메시지
    """
    try:
        # 진행도 계산
        progress = session.exploration_step / session.max_steps if session.max_steps > 0 else 0.0
        monsters = _spawn_monster_group(session.dungeon.id, progress)
    except (MonsterNotFoundError, MonsterSpawnNotFoundError) as e:
        logger.error(f"Monster spawn error: {e}")
        return "몬스터 정보를 찾을 수 없습니다."

    will_fight = await _ask_fight_or_flee(interaction, monsters[0])

    if will_fight is None:
        return f"{session.user.get_name()}은 아무 행동도 하지 않았다..."

    if not will_fight:
        return await _attempt_flee(session, monsters[0])

    # 전투 시작 (CombatContext 사용)
    context = CombatContext.from_group(monsters)
    return await _execute_combat_context(session, interaction, context)


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

    # 보스는 도주 불가
    if _is_boss_monster(monster):
        logger.info(f"Flee blocked (boss): user={session.user.discord_id}, monster={monster.name}")
        return f"⚔️ **{monster.name}**는 도주를 허락하지 않는다! (보스는 도주 불가)"

    # 도주 확률 판정
    if random.random() < COMBAT.FLEE_SUCCESS_RATE:
        logger.info(f"Flee success: user={session.user.discord_id}")
        return f"🏃 **{monster.name}**에게서 도망쳤다!"

    # 도주 실패 시 몬스터 공격
    damage = _get_attack_stat(monster)
    session.user.now_hp -= damage
    session.user.now_hp = max(session.user.now_hp, 0)

    logger.info(f"Flee failed: user={session.user.discord_id}, damage={damage}")
    return f"💨 도망 실패! **{monster.name}**의 반격으로 **-{damage}** HP"


def _spawn_random_monster(dungeon_id: int, progress: float = 0.0) -> Monster:
    """
    던전에서 랜덤 몬스터 스폰 (단일)

    Args:
        dungeon_id: 던전 ID
        progress: 던전 진행도 (0.0 ~ 1.0)

    Returns:
        스폰된 몬스터 복사본

    Raises:
        MonsterSpawnNotFoundError: 스폰 정보가 없을 때
        MonsterNotFoundError: 몬스터를 찾을 수 없을 때
    """
    monsters_spawn = find_all_dungeon_spawn_monster_by(dungeon_id)
    if not monsters_spawn:
        raise MonsterSpawnNotFoundError(dungeon_id)

    boss_spawns = []
    normal_spawns = []

    for spawn in monsters_spawn:
        monster = find_monster_by_id(spawn.monster_id)
        if _is_boss_monster(monster):
            boss_spawns.append(spawn)
        else:
            normal_spawns.append(spawn)

    # 진행도 90% 이상일 때만 10% 확률로 보스 등장
    can_spawn_boss = progress >= DUNGEON.BOSS_SPAWN_PROGRESS_THRESHOLD
    boss_roll = random.random() < DUNGEON.BOSS_SPAWN_RATE_AT_END

    if boss_spawns and can_spawn_boss and boss_roll:
        spawn_pool = boss_spawns
    else:
        spawn_pool = normal_spawns or monsters_spawn

    random_spawn = random.choices(
        population=spawn_pool,
        weights=[spawn.prob for spawn in spawn_pool],
        k=1
    )[0]

    monster = find_monster_by_id(random_spawn.monster_id)
    if not monster:
        raise MonsterNotFoundError(random_spawn.monster_id)

    return monster


def _spawn_monster_group(dungeon_id: int, progress: float = 0.0) -> list[Monster]:
    """
    던전에서 몬스터 그룹 스폰 (1~N마리) - CSV 기반

    CSV의 '그룹' 열에 설정된 몬스터 ID들 중에서 랜덤하게 그룹을 구성합니다.
    - 빈 값: 솔로 전용
    - ID 나열: 해당 몬스터들과 그룹 가능

    Args:
        dungeon_id: 던전 ID
        progress: 던전 진행도 (0.0 ~ 1.0)

    Returns:
        스폰된 몬스터 리스트 (복사본)

    Raises:
        MonsterSpawnNotFoundError: 스폰 정보가 없을 때
        MonsterNotFoundError: 몬스터를 찾을 수 없을 때
    """
    from models.repos.static_cache import monster_cache_by_id

    # 첫 번째 몬스터 스폰
    first_monster = _spawn_random_monster(dungeon_id, progress)

    # 보스는 항상 단독
    if _is_boss_monster(first_monster):
        return [first_monster]

    # group_ids 확인
    group_ids = getattr(first_monster, 'group_ids', [])

    # 그룹 설정이 없으면 솔로
    if not group_ids:
        return [first_monster]

    # 그룹 스폰 확률 체크 (10%)
    if random.random() > DUNGEON.GROUP_SPAWN_RATE:
        return [first_monster]

    # 그룹 크기 결정 (2~3마리)
    group_size = random.randint(2, DUNGEON.MAX_GROUP_SIZE)
    monsters = [first_monster]

    # 추가 몬스터 스폰 (group_ids에서 선택)
    for _ in range(group_size - 1):
        # group_ids에서 랜덤 선택
        selected_id = random.choice(group_ids)

        # 캐시에서 몬스터 가져오기
        if selected_id in monster_cache_by_id:
            additional = monster_cache_by_id[selected_id].copy()
            monsters.append(additional)
        else:
            logger.warning(f"Group monster {selected_id} not found in cache")

    return monsters


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
    # 몬스터 스킬 이름 조회
    from models.repos.skill_repo import get_skill_by_id
    skill_names = []
    monster_skill_ids = getattr(monster, 'skill_ids', [])
    for sid in monster_skill_ids:
        if sid != 0:
            skill = get_skill_by_id(sid)
            if skill and skill.name not in skill_names:
                skill_names.append(skill.name)

    embed = discord.Embed(
        title=f"🐲 {monster.name} 이(가) 나타났다!",
        description=monster.description or "무서운 기운이 느껴진다...",
        color=EmbedColor.ERROR
    )
    monster_stat = monster.get_stat()
    embed.add_field(name="❤️ 체력", value=f"{monster_stat[UserStatEnum.HP]}", inline=True)
    embed.add_field(name="⚔️ 공격력", value=f"{monster_stat[UserStatEnum.ATTACK]}", inline=True)
    embed.add_field(name="🔮 마공", value=f"{monster_stat[UserStatEnum.AP_ATTACK]}", inline=True)
    embed.add_field(name="🛡️ 방어력", value=f"{monster_stat[UserStatEnum.DEFENSE]}", inline=True)
    embed.add_field(name="🌀 마방", value=f"{monster_stat[UserStatEnum.AP_DEFENSE]}", inline=True)
    embed.add_field(name="💨 속도", value=f"{monster_stat[UserStatEnum.SPEED]}", inline=True)
    embed.add_field(name="💫 회피", value=f"{getattr(monster, 'evasion', 0)}%", inline=True)

    if skill_names:
        embed.add_field(
            name="📜 스킬",
            value=", ".join(skill_names),
            inline=False
        )

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
    전투 실행 (레거시 1:1 전투 래퍼)

    기존 코드와의 호환성을 위한 래퍼 함수입니다.
    내부적으로 CombatContext를 생성하여 _execute_combat_context를 호출합니다.

    Args:
        session: 던전 세션
        interaction: Discord 인터랙션
        monster: 전투할 몬스터

    Returns:
        전투 결과 메시지
    """
    # 몬스터 복사본 생성 (캐시 원본 보호)
    monster = monster.copy()

    # CombatContext 생성 (1:1 전투)
    context = CombatContext.from_single(monster)

    # 새 전투 시스템 호출
    return await _execute_combat_context(session, interaction, context)


async def _process_combat_result(
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
            return f"⚔️ **{user.get_name()}**과 **{monster.name}** 동시에 쓰러졌다!"
        return f"💀 **{monster.name}**에게 패배..."

    # 승리 시 - 보상 계산
    monster_level = session.dungeon.require_level if session.dungeon else 1

    exp_multiplier = _get_monster_exp_multiplier(monster)
    gold_multiplier = _get_monster_gold_multiplier(monster)

    # 경험치 계산: 기본 * (1 + 몬스터레벨/10) * 타입 배율
    exp_gained = int(BASE_EXP_PER_MONSTER * (1 + monster_level / 10) * exp_multiplier)

    # 골드 계산: 기본 * (1 + 몬스터레벨/10) * 타입 배율
    gold_gained = int(BASE_GOLD_PER_MONSTER * (1 + monster_level / 10) * gold_multiplier)

    # 세션에 누적
    session.total_exp += exp_gained
    session.total_gold += gold_gained
    session.monsters_defeated += 1

    # 도감에 몬스터 등록
    await CollectionService.register_monster(user, monster.id)

    logger.info(
        f"Combat victory: user={user.discord_id}, monster={monster.name}, "
        f"exp={exp_gained}, gold={gold_gained}, turns={turn_count}"
    )

    # 보스 전용 드롭 테이블 확인
    dropped_boss_item_msg = await _try_drop_boss_special_item(user, monster)

    # 상자 드롭 확인 (새 시스템)
    dropped_chest_msg = await _try_drop_monster_box(session, monster)

    # 스킬 드롭 확인
    dropped_skill_msg = await _try_drop_monster_skill(user, monster)

    # 결과 메시지 생성
    result_msg = (
        f"🏆 **{monster.name}** 처치! ({turn_count}턴)\n"
        f"   ⭐ +**{exp_gained}** EXP │ 💰 +**{gold_gained}** G"
    )

    if dropped_boss_item_msg:
        result_msg += f"\n   {dropped_boss_item_msg}"

    if dropped_chest_msg:
        result_msg += f"\n   {dropped_chest_msg}"

    if dropped_skill_msg:
        result_msg += f"\n   {dropped_skill_msg}"

    return result_msg


def _normalize_monster_type(monster: Monster) -> Optional[str]:
    monster_type = getattr(monster, "type", None)
    if isinstance(monster_type, MonsterTypeEnum):
        return monster_type.value
    return monster_type


def _is_boss_monster(monster: Monster) -> bool:
    return _normalize_monster_type(monster) == MonsterTypeEnum.BOSS.value


def _get_monster_exp_multiplier(monster: Monster) -> float:
    monster_type = _normalize_monster_type(monster)
    if monster_type == MonsterTypeEnum.ELITE.value:
        return DUNGEON.ELITE_EXP_MULTIPLIER
    if monster_type == MonsterTypeEnum.BOSS.value:
        return DUNGEON.BOSS_EXP_MULTIPLIER
    return 1.0


def _get_monster_gold_multiplier(monster: Monster) -> float:
    monster_type = _normalize_monster_type(monster)
    if monster_type == MonsterTypeEnum.ELITE.value:
        return DUNGEON.ELITE_GOLD_MULTIPLIER
    if monster_type == MonsterTypeEnum.BOSS.value:
        return DUNGEON.BOSS_GOLD_MULTIPLIER
    return 1.0


def _get_monster_drop_multiplier(monster: Monster) -> float:
    monster_type = _normalize_monster_type(monster)
    if monster_type == MonsterTypeEnum.ELITE.value:
        return DROP.ELITE_DROP_MULTIPLIER
    if monster_type == MonsterTypeEnum.BOSS.value:
        return DROP.BOSS_DROP_MULTIPLIER
    return 1.0


def _get_box_pool_by_monster_type(monster: Monster) -> list[tuple[int, float]]:
    """
    몬스터 타입에 따른 상자 풀 조회 (CSV 기반)

    Args:
        monster: 몬스터 객체

    Returns:
        [(box_id, weight), ...] 리스트
    """
    from models.repos.static_cache import get_box_pool_by_monster_type

    monster_type = _normalize_monster_type(monster)
    return get_box_pool_by_monster_type(monster_type)


async def _try_drop_monster_box(
    session: DungeonSession,
    monster: Monster
) -> Optional[str]:
    """
    몬스터 상자 드랍 시도 (새 시스템)

    Args:
        session: 던전 세션
        monster: 몬스터 객체

    Returns:
        드랍 메시지 또는 None
    """
    # 드랍 확률 체크
    drop_rate = DROP.BOX_DROP_RATE * _get_monster_drop_multiplier(monster)
    if random.random() > min(drop_rate, 1.0):
        return None

    # 몬스터 타입에 따라 상자 티어 결정
    box_pool = _get_box_pool_by_monster_type(monster)
    if not box_pool:
        logger.warning(f"No box pool for monster type: {monster.type}")
        return None

    # 가중치 기반 랜덤 선택
    box_ids = [box_id for box_id, weight in box_pool]
    weights = [weight for box_id, weight in box_pool]
    box_id = random.choices(box_ids, weights=weights, k=1)[0]

    # 인벤토리 추가
    try:
        await InventoryService.add_item(session.user, box_id, 1)
    except InventoryFullError:
        return "📦 상자를 얻었지만 인벤토리가 가득 찼다..."

    item = await Item.get_or_none(id=box_id)
    item_name = item.name if item else "상자"
    return f"📦 「{item_name}」 획득!"


async def _try_drop_boss_special_item(user: User, monster: Monster) -> Optional[str]:
    if not _is_boss_monster(monster):
        return None

    drop_rows = await Droptable.filter(drop_monster=monster.id).all()
    if not drop_rows:
        return None

    valid_rows = [row for row in drop_rows if row.item_id]
    if not valid_rows:
        return None

    weights = [float(row.probability or 0) for row in valid_rows]
    if sum(weights) <= 0:
        return None

    chosen = random.choices(valid_rows, weights=weights, k=1)[0]
    item = await Item.get_or_none(id=chosen.item_id)
    if not item:
        return None

    try:
        await InventoryService.add_item(user, item.id, 1)
    except InventoryFullError:
        return "🎖️ 보스 전리품을 얻었지만 인벤토리가 가득 찼다..."

    return f"🎖️ **보스 전리품!** 「{item.name}」 획득!"


async def _try_drop_monster_skill(user: User, monster: Monster) -> Optional[str]:
    """
    몬스터 스킬 드롭 시도

    Args:
        user: 플레이어
        monster: 처치한 몬스터

    Returns:
        드롭 메시지 또는 None
    """
    from config import DROP
    from service.skill_ownership_service import SkillOwnershipService

    # 몬스터가 스킬이 없으면 드롭 없음
    monster_skills = getattr(monster, 'skill_ids', [])
    if not monster_skills:
        return None

    # 0 (빈 슬롯) 제외
    valid_skills = [sid for sid in monster_skills if sid != 0]
    if not valid_skills:
        return None

    # 드롭 확률 판정 (0.1%)
    if random.random() > DROP.SKILL_DROP_RATE:
        return None

    # 플레이어 획득 가능한 스킬만 필터링
    from models.repos.skill_repo import get_skill_by_id

    droppable_skills = []
    for sid in valid_skills:
        skill = get_skill_by_id(sid)
        if skill and getattr(skill.skill_model, 'player_obtainable', True):
            droppable_skills.append(sid)

    # 드롭 가능한 스킬이 없으면 드롭 없음
    if not droppable_skills:
        return None

    # 랜덤 스킬 선택
    dropped_skill_id = random.choice(droppable_skills)

    # 유저에게 스킬 지급
    try:
        await SkillOwnershipService.add_skill(user, dropped_skill_id, 1)

        # 스킬 이름 조회
        skill = get_skill_by_id(dropped_skill_id)
        skill_name = skill.name if skill else f"스킬 #{dropped_skill_id}"

        logger.info(
            f"Skill drop: user={user.discord_id}, monster={monster.name}, "
            f"skill_id={dropped_skill_id}, skill_name={skill_name}"
        )

        return f"✨ **희귀 드롭!** 「{skill_name}」 스킬 획득!"
    except Exception as e:
        logger.error(f"Failed to drop skill: {e}")
        return None


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

    logger.info(
        f"Turn {turn_count}: first={first.get_name()}, "
        f"first_skill={first_skill.name if first_skill else 'None'}, "
        f"second={second.get_name()}, "
        f"second_skill={second_skill.name if second_skill else 'None'}"
    )

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
    user_speed = _get_speed_stat(user)
    monster_speed = _get_speed_stat(monster)
    speed_diff = user_speed - monster_speed
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
    """턴 시작 페이즈 처리 - DOT 데미지 + 스킬 시작 효과"""
    start_logs = []

    # 1. DOT 틱 처리 (화상, 독, 출혈 등)
    dot_logs = []
    dot_logs.extend(process_status_ticks(user))
    dot_logs.extend(process_status_ticks(monster))
    if dot_logs:
        start_logs.extend(dot_logs)

    # 2. 스킬 on_turn_start 효과
    if first_skill and second_skill:
        skill_logs = [
            log for log in [
                first_skill.on_turn_start(first, second),
                second_skill.on_turn_start(second, first)
            ] if log and log.strip()
        ]
        start_logs.extend(skill_logs)

    if not start_logs:
        return

    # 턴 시작 효과 표시
    phase_header = f"🌅 **{turn_count}턴 시작**"
    combat_log.append(phase_header + "\n" + "\n".join(start_logs))
    await combat_message.edit(embed=_create_battle_embed(user, monster, combat_log))
    await asyncio.sleep(COMBAT.TURN_PHASE_DELAY)


def _format_attack_log(attacker_name: str, skill_name: str, target_name: str, damage: int, is_crit: bool = False) -> str:
    """공격 로그 포맷"""
    crit_mark = " 💥**치명타!**" if is_crit else ""
    return f"⚔️ **{attacker_name}** 「{skill_name}」 → **{damage}**{crit_mark}"


def _format_heal_log(healer_name: str, skill_name: str, amount: int) -> str:
    """회복 로그 포맷"""
    return f"💚 **{healer_name}** 「{skill_name}」 → **+{amount}** HP"


def _format_buff_log(caster_name: str, skill_name: str, effect: str) -> str:
    """버프 로그 포맷"""
    return f"✨ **{caster_name}** 「{skill_name}」 → {effect}"


async def _process_attack_phase(
    first, second, first_skill, second_skill,
    turn_count: int,
    combat_log: deque[str],
    combat_message: discord.Message,
    user: User,
    monster: Monster
) -> bool:
    """
    공격 페이즈 처리 - CC 체크 포함

    Returns:
        전투 종료 여부
    """
    attack_logs = []

    # 턴 헤더
    turn_header = f"━━━ ⚔️ **{turn_count}턴** ━━━"

    # 선공 공격 (CC 체크)
    if not can_entity_act(first):
        cc_name = get_cc_effect_name(first)
        attack_logs.append(f"💫 **{first.get_name()}** {cc_name}! 행동 불가")
    elif first_skill:
        logger.info(f"First attacker ({first.get_name()}) using skill: {first_skill.name}")
        first_log = first_skill.on_turn(first, second)
        logger.info(f"Skill result: '{first_log}', target HP: {second.now_hp}")
        if first_log and first_log.strip():
            attack_logs.append(first_log)
        else:
            logger.warning(f"Skill {first_skill.name} returned empty log, using basic attack")
            damage = _get_attack_stat(first)
            second.now_hp -= damage
            second.now_hp = max(second.now_hp, 0)
            attack_logs.append(_format_attack_log(first.get_name(), "기본 공격", second.get_name(), damage))
    else:
        damage = _get_attack_stat(first)
        second.now_hp -= damage
        second.now_hp = max(second.now_hp, 0)
        logger.info(f"First attacker ({first.get_name()}) basic attack: {damage} damage, target HP: {second.now_hp}")
        attack_logs.append(_format_attack_log(first.get_name(), "기본 공격", second.get_name(), damage))

    # 전투 종료 체크 (선공 후)
    if user.now_hp <= 0 or monster.now_hp <= 0:
        if attack_logs:
            combat_log.append(turn_header + "\n" + "\n".join(attack_logs))
        return True

    # 후공 공격 (CC 체크)
    if not can_entity_act(second):
        cc_name = get_cc_effect_name(second)
        attack_logs.append(f"💫 **{second.get_name()}** {cc_name}! 행동 불가")
    elif second_skill:
        second_log = second_skill.on_turn(second, first)
        if second_log and second_log.strip():
            attack_logs.append(second_log)
        else:
            logger.warning(f"Skill {second_skill.name} returned empty log, using basic attack")
            damage = _get_attack_stat(second)
            first.now_hp -= damage
            first.now_hp = max(first.now_hp, 0)
            attack_logs.append(_format_attack_log(second.get_name(), "기본 공격", first.get_name(), damage))
    else:
        damage = _get_attack_stat(second)
        first.now_hp -= damage
        first.now_hp = max(first.now_hp, 0)
        attack_logs.append(_format_attack_log(second.get_name(), "기본 공격", first.get_name(), damage))

    if attack_logs:
        combat_log.append(turn_header + "\n" + "\n".join(attack_logs))
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
    """턴 종료 페이즈 처리 - 스킬 종료 효과 + 버프/상태이상 지속시간 감소"""
    end_logs = []

    # 1. 스킬 on_turn_end 효과
    if first_skill and second_skill:
        skill_logs = [
            log for log in [
                first_skill.on_turn_end(first, second),
                second_skill.on_turn_end(second, first)
            ] if log and log.strip()
        ]
        end_logs.extend(skill_logs)

    # 2. 버프/상태이상 지속시간 감소 + 만료 제거
    decay_logs = []
    decay_logs.extend(decay_all_durations(user))
    decay_logs.extend(decay_all_durations(monster))
    if decay_logs:
        end_logs.extend(decay_logs)

    if not end_logs:
        return

    # 턴 종료 효과 표시
    phase_footer = "🌙 **턴 종료**"
    combat_log.append(phase_footer + "\n" + "\n".join(end_logs))
    await combat_message.edit(embed=_create_battle_embed(user, monster, combat_log))
    await asyncio.sleep(COMBAT.TURN_PHASE_DELAY)


def _get_attack_stat(entity) -> int:
    if hasattr(entity, "get_stat"):
        stat = entity.get_stat()
        return int(stat.get(UserStatEnum.ATTACK, getattr(entity, "attack", 0)))
    return getattr(entity, "attack", 0)


def _get_speed_stat(entity) -> int:
    if hasattr(entity, "get_stat"):
        stat = entity.get_stat()
        return int(stat.get(UserStatEnum.SPEED, getattr(entity, "speed", 0)))
    return getattr(entity, "speed", 0)


# =============================================================================
# 임베드 생성
# =============================================================================


def _create_hp_bar(current: int, maximum: int, length: int = 10) -> str:
    """
    HP 바 생성

    Args:
        current: 현재 HP
        maximum: 최대 HP
        length: 바 길이

    Returns:
        HP 바 문자열
    """
    ratio = max(0, min(current / maximum, 1.0)) if maximum > 0 else 0
    filled = int(ratio * length)
    empty = length - filled

    # HP 비율에 따른 색상 (이모지로 표현)
    if ratio > 0.6:
        bar_char = "🟩"
    elif ratio > 0.3:
        bar_char = "🟨"
    else:
        bar_char = "🟥"

    return bar_char * filled + "⬛" * empty


def _create_gauge_bar(gauge: int, length: int = 8) -> str:
    """
    행동 게이지 바 생성

    Args:
        gauge: 현재 게이지 (0~100+)
        length: 바 길이

    Returns:
        게이지 바 문자열
    """
    ratio = max(0, min(gauge / 100, 1.0))
    filled = int(ratio * length)
    empty = length - filled

    # 게이지 100 이상이면 특수 표시
    if gauge >= 100:
        return "⚡" * length  # 완전 충전
    elif gauge >= 75:
        return "🟦" * filled + "⬜" * empty
    else:
        return "🟦" * filled + "⬜" * empty


def _create_battle_embed(
    player: User,
    monster: Monster,
    combat_log: deque[str]
) -> Embed:
    """전투 임베드 생성"""
    embed = Embed(
        title=f"⚔️ {player.get_name()} vs {monster.get_name()}",
        color=EmbedColor.COMBAT
    )

    # 플레이어 HP 바
    player_stat = player.get_stat()
    player_max_hp = player_stat[UserStatEnum.HP]
    player_hp_bar = _create_hp_bar(player.now_hp, player_max_hp, 10)
    player_hp_pct = int((player.now_hp / player_max_hp) * 100) if player_max_hp > 0 else 0
    player_status_icons = get_status_icons(player)

    embed.add_field(
        name=f"👤 {player.get_name()}",
        value=(
            f"{player_hp_bar}\n"
            f"**{player.now_hp}** / {player_max_hp} ({player_hp_pct}%)\n"
            f"{player_status_icons}" if player_status_icons else f"{player_hp_bar}\n**{player.now_hp}** / {player_max_hp} ({player_hp_pct}%)"
        ),
        inline=True
    )

    # 몬스터 HP 바
    monster_hp_bar = _create_hp_bar(monster.now_hp, monster.hp, 10)
    monster_hp_pct = int((monster.now_hp / monster.hp) * 100) if monster.hp > 0 else 0
    monster_status_icons = get_status_icons(monster)

    embed.add_field(
        name=f"👹 {monster.get_name()}",
        value=(
            f"{monster_hp_bar}\n"
            f"**{monster.now_hp}** / {monster.hp} ({monster_hp_pct}%)\n"
            f"{monster_status_icons}" if monster_status_icons else f"{monster_hp_bar}\n**{monster.now_hp}** / {monster.hp} ({monster_hp_pct}%)"
        ),
        inline=True
    )

    # 전투 로그
    log_text = "\n".join(combat_log) if combat_log else "```전투 준비 중...```"
    embed.add_field(
        name="📜 전투 로그",
        value=log_text,
        inline=False
    )

    return embed


def _create_dungeon_embed(
    session: DungeonSession,
    event_queue: deque[str]
) -> discord.Embed:
    """던전 임베드 생성"""
    user_name = session.user.get_name()
    embed = discord.Embed(
        title=f"🏰 {session.dungeon.name}",
        description=f"**{user_name}**의 탐험\n*{session.dungeon.description}*" if session.dungeon.description else f"**{user_name}**의 탐험",
        color=EmbedColor.DUNGEON
    )

    # 진행도 바 생성 (개선된 버전)
    progress = min(session.exploration_step / session.max_steps, 1.0)
    progress_bar = _create_exploration_bar(progress, 12)
    progress_pct = int(progress * 100)

    embed.add_field(
        name="🗺️ 탐험 진행도",
        value=f"{progress_bar}\n**{session.exploration_step}** / {session.max_steps} 구역 ({progress_pct}%)",
        inline=False
    )

    # 플레이어 상태 (HP 바 포함)
    user_stat = session.user.get_stat()
    max_hp = user_stat[UserStatEnum.HP]
    hp_bar = _create_hp_bar(session.user.now_hp, max_hp, 8)
    hp_pct = int((session.user.now_hp / max_hp) * 100) if max_hp > 0 else 0

    embed.add_field(
        name=f"👤 {user_name}",
        value=(
            f"{hp_bar}\n"
            f"HP **{session.user.now_hp}** / {max_hp} ({hp_pct}%)"
        ),
        inline=True
    )

    # 획득 보상
    embed.add_field(
        name="💎 획득 보상",
        value=(
            f"⭐ 경험치: **{session.total_exp:,}**\n"
            f"💰 골드: **{session.total_gold:,}**\n"
            f"⚔️ 처치: **{session.monsters_defeated}**"
        ),
        inline=True
    )

    # 탐험 로그 (포맷팅 개선)
    log_text = "\n".join(event_queue) if event_queue else "탐험을 시작합니다..."
    embed.add_field(
        name="📜 탐험 로그",
        value=log_text,
        inline=False
    )

    return embed


def _create_exploration_bar(progress: float, length: int = 12) -> str:
    """
    탐험 진행도 바 생성 (플레이어 아이콘 포함)

    Args:
        progress: 진행률 (0.0 ~ 1.0)
        length: 바 길이

    Returns:
        진행도 바 문자열
    """
    filled = int(progress * length)
    empty = length - filled - 1

    if progress >= 1.0:
        return "🚪" + "▓" * (length - 1) + "🏆"

    if filled == 0:
        return "🚪🧑" + "░" * (length - 1) + "🏁"

    return "🚪" + "▓" * filled + "🧑" + "░" * max(0, empty) + "🏁"


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


# =============================================================================
# 1:N 전투 시스템 (다중 몬스터 지원)
# =============================================================================


def _is_skill_aoe(skill) -> bool:
    """
    스킬이 AOE(전체 공격)인지 확인

    Args:
        skill: Skill 객체

    Returns:
        AOE 스킬이면 True
    """
    if not skill:
        return False

    for component in skill.components:
        if hasattr(component, 'is_aoe') and component.is_aoe:
            return True
    return False


async def _user_attack_phase(
    user: User,
    context: CombatContext,
    turn_count: int,
    combat_log: deque[str],
    combat_message: discord.Message
) -> bool:
    """
    유저 공격 페이즈 (다중 몬스터 지원)

    Args:
        user: 유저
        context: 전투 컨텍스트
        turn_count: 현재 턴 수
        combat_log: 전투 로그
        combat_message: 전투 메시지

    Returns:
        전투 종료 여부 (True면 종료)
    """
    attack_logs = []

    # CC 체크
    if not can_entity_act(user):
        cc_name = get_cc_effect_name(user)
        attack_logs.append(f"💫 **{user.get_name()}** {cc_name}! 행동 불가")
    else:
        user_skill = user.next_skill()

        if user_skill:
            # AOE 체크
            is_aoe = _is_skill_aoe(user_skill)

            if is_aoe:
                # 모든 살아있는 몬스터 공격
                for monster in context.get_all_alive_monsters():
                    log = user_skill.on_turn(user, monster)
                    if log and log.strip():
                        attack_logs.append(log)
            else:
                # 단일 타겟
                target = context.get_primary_monster()
                log = user_skill.on_turn(user, target)
                if log and log.strip():
                    attack_logs.append(log)
        else:
            # 기본 공격
            target = context.get_primary_monster()
            damage = _get_attack_stat(user)
            target.take_damage(damage)
            attack_logs.append(
                f"⚔️ **{user.get_name()}** 기본 공격 → **{target.get_name()}** {damage} 데미지"
            )

    # 로그 표시
    if attack_logs:
        header = f"━━━ ⚔️ **{turn_count}턴 - {user.get_name()}** ━━━"
        combat_log.append(header + "\n" + "\n".join(attack_logs))
        await combat_message.edit(embed=_create_battle_embed_multi(user, context, combat_log))
        await asyncio.sleep(COMBAT.TURN_PHASE_DELAY)

    return user.now_hp <= 0 or context.is_all_dead()


async def _monsters_attack_phase(
    user: User,
    context: CombatContext,
    turn_count: int,
    combat_log: deque[str],
    combat_message: discord.Message
) -> bool:
    """
    몬스터들 공격 페이즈

    Args:
        user: 유저
        context: 전투 컨텍스트
        turn_count: 현재 턴 수
        combat_log: 전투 로그
        combat_message: 전투 메시지

    Returns:
        전투 종료 여부 (True면 종료)
    """
    attack_logs = []

    for monster in context.get_all_alive_monsters():
        # CC 체크
        if not can_entity_act(monster):
            cc_name = get_cc_effect_name(monster)
            attack_logs.append(f"💫 **{monster.get_name()}** {cc_name}! 행동 불가")
            continue

        # 몬스터 스킬 (항상 유저를 단일 타겟)
        monster_skill = monster.next_skill()

        if monster_skill:
            log = monster_skill.on_turn(monster, user)
            if log and log.strip():
                attack_logs.append(log)
        else:
            # 기본 공격
            damage = _get_attack_stat(monster)
            user.take_damage(damage)
            attack_logs.append(
                f"⚔️ **{monster.get_name()}** 기본 공격 → **{user.get_name()}** {damage} 데미지"
            )

        # 유저 사망 시 중단
        if user.now_hp <= 0:
            break

    # 로그 표시
    if attack_logs:
        header = f"━━━ 👹 **{turn_count}턴 - 몬스터들** ━━━"
        combat_log.append(header + "\n" + "\n".join(attack_logs))
        await combat_message.edit(embed=_create_battle_embed_multi(user, context, combat_log))
        await asyncio.sleep(COMBAT.TURN_PHASE_DELAY)

    return user.now_hp <= 0


async def _process_turn_start_phase_multi(
    user: User,
    context: CombatContext,
    turn_count: int,
    combat_log: deque[str],
    combat_message: discord.Message
) -> None:
    """
    턴 시작 페이즈 (다중 몬스터)

    DOT 틱 및 턴 시작 효과 처리

    Args:
        user: 유저
        context: 전투 컨텍스트
        turn_count: 현재 턴 수
        combat_log: 전투 로그
        combat_message: 전투 메시지
    """
    dot_logs = []

    # DOT 틱
    dot_logs.extend(process_status_ticks(user))
    for monster in context.get_all_alive_monsters():
        dot_logs.extend(process_status_ticks(monster))

    # 스킬 턴 시작 효과
    user_skill = user.next_skill()
    if user_skill:
        # AOE 스킬이면 모든 몬스터에 적용
        if _is_skill_aoe(user_skill):
            for monster in context.get_all_alive_monsters():
                log = user_skill.on_turn_start(user, monster)
                if log and log.strip():
                    dot_logs.append(log)
        else:
            target = context.get_primary_monster()
            log = user_skill.on_turn_start(user, target)
            if log and log.strip():
                dot_logs.append(log)

    for monster in context.get_all_alive_monsters():
        monster_skill = monster.next_skill()
        if monster_skill:
            log = monster_skill.on_turn_start(monster, user)
            if log and log.strip():
                dot_logs.append(log)

    # 로그 표시
    if dot_logs:
        header = f"━━━ 🌙 **{turn_count}턴 시작** ━━━"
        combat_log.append(header + "\n" + "\n".join(dot_logs))
        await combat_message.edit(embed=_create_battle_embed_multi(user, context, combat_log))
        await asyncio.sleep(COMBAT.TURN_PHASE_DELAY)


async def _process_turn_end_phase_multi(
    user: User,
    context: CombatContext,
    turn_count: int,
    combat_log: deque[str],
    combat_message: discord.Message
) -> None:
    """
    턴 종료 페이즈 (다중 몬스터)

    버프/디버프 지속시간 감소 및 턴 종료 효과 처리

    Args:
        user: 유저
        context: 전투 컨텍스트
        turn_count: 현재 턴 수
        combat_log: 전투 로그
        combat_message: 전투 메시지
    """
    end_logs = []

    # 스킬 턴 종료 효과
    user_skill = user.next_skill()
    if user_skill:
        if _is_skill_aoe(user_skill):
            for monster in context.get_all_alive_monsters():
                log = user_skill.on_turn_end(user, monster)
                if log and log.strip():
                    end_logs.append(log)
        else:
            target = context.get_primary_monster()
            log = user_skill.on_turn_end(user, target)
            if log and log.strip():
                end_logs.append(log)

    for monster in context.get_all_alive_monsters():
        monster_skill = monster.next_skill()
        if monster_skill:
            log = monster_skill.on_turn_end(monster, user)
            if log and log.strip():
                end_logs.append(log)

    # 버프/디버프 지속시간 감소
    decay_logs = []
    decay_logs.extend(decay_all_durations(user))
    for monster in context.get_all_alive_monsters():
        decay_logs.extend(decay_all_durations(monster))

    if decay_logs:
        end_logs.extend(decay_logs)

    # 로그 표시
    if end_logs:
        header = f"━━━ 🌙 **{turn_count}턴 종료** ━━━"
        combat_log.append(header + "\n" + "\n".join(end_logs))
        await combat_message.edit(embed=_create_battle_embed_multi(user, context, combat_log))
        await asyncio.sleep(COMBAT.TURN_PHASE_DELAY)


async def _process_turn_multi(
    user: User,
    context: CombatContext,
    turn_count: int,
    combat_log: deque[str],
    combat_message: discord.Message
) -> bool:
    """
    턴 처리 (1:N 지원) - 행동 게이지 시스템

    행동 게이지 시스템:
    - 각 전투원의 속도에 비례해 게이지 충전
    - 게이지 100 도달 시 행동 가능
    - 속도가 높을수록 더 자주 행동

    Args:
        user: 유저
        context: 전투 컨텍스트
        turn_count: 현재 턴 수 (표시용)
        combat_log: 전투 로그
        combat_message: 전투 메시지

    Returns:
        전투 종료 여부 (True면 종료)
    """
    # 게이지 초기화 (첫 호출 시)
    if not context.action_gauges:
        context.initialize_gauges(user)
        combat_log.append(f"━━━ ⚔️ **전투 시작 - 라운드 {context.round_number}** ━━━")

    # 메인 행동 루프
    while context.action_count < COMBAT.MAX_ACTIONS_PER_LOOP:
        # 모든 몬스터가 죽었는지 체크
        if context.is_all_dead():
            return True

        # 유저가 죽었는지 체크
        if user.now_hp <= 0:
            return True

        # 게이지 충전
        context.fill_gauges(user)

        # 라운드 체크 (속도 20 기준 라운드 마커)
        if context.check_and_advance_round():
            combat_log.append(f"━━━ 🌟 **라운드 {context.round_number}** ━━━")
            await combat_message.edit(embed=_create_battle_embed_multi(user, context, combat_log))
            await asyncio.sleep(COMBAT.TURN_PHASE_DELAY * 0.5)  # 짧은 딜레이

        # 다음 행동자 결정
        actor = context.get_next_actor(user)

        if not actor:
            # 아직 행동 가능한 엔티티가 없음 (게이지 부족)
            # 다음 충전 사이클로
            continue

        # 행동 횟수 증가
        context.action_count += 1

        # 행동 전 상태이상 tick 처리 (DOT 등)
        status_logs = process_status_ticks(actor)
        if status_logs:
            for log in status_logs:
                combat_log.append(log)

        # 행동 불가 상태 확인 (기절, 동결 등)
        if not can_entity_act(actor):
            cc_name = get_cc_effect_name(actor)
            combat_log.append(f"💫 **{actor.get_name()}** {cc_name}! 행동 불가")

            # 게이지 소모
            context.consume_gauge(actor)

            # UI 업데이트
            await combat_message.edit(embed=_create_battle_embed_multi(user, context, combat_log))
            await asyncio.sleep(COMBAT.TURN_PHASE_DELAY)

            # 상태이상 duration 감소
            _decrement_status_durations(actor)
            continue

        # 행동 처리
        action_logs = await _execute_entity_action(user, actor, context)

        if action_logs:
            for log in action_logs:
                combat_log.append(log)

        # 게이지 소모
        context.consume_gauge(actor)

        # 상태이상 duration 감소 (행동 후)
        _decrement_status_durations(actor)

        # UI 업데이트
        await combat_message.edit(embed=_create_battle_embed_multi(user, context, combat_log))
        await asyncio.sleep(COMBAT.TURN_PHASE_DELAY)

        # 전투 종료 체크
        if user.now_hp <= 0 or context.is_all_dead():
            return True

    # 최대 행동 횟수 도달 (무한루프 방지)
    logger.warning(f"Combat reached max actions: {COMBAT.MAX_ACTIONS_PER_LOOP}")
    return True


async def _execute_entity_action(
    user: User,
    actor: Union[User, Monster],
    context: CombatContext
) -> list[str]:
    """
    엔티티의 행동 실행

    Args:
        user: 유저
        actor: 행동하는 엔티티
        context: 전투 컨텍스트

    Returns:
        행동 로그 리스트
    """
    from models.users import User as UserClass

    action_logs = []

    if isinstance(actor, UserClass):
        # 유저 행동
        user_skill = actor.next_skill()

        if user_skill:
            is_aoe = _is_skill_aoe(user_skill)

            if is_aoe:
                # AOE: 모든 살아있는 몬스터 공격
                for monster in context.get_all_alive_monsters():
                    log = user_skill.on_turn(actor, monster)
                    if log and log.strip():
                        action_logs.append(log)
            else:
                # 단일 타겟
                target = context.get_primary_monster()
                log = user_skill.on_turn(actor, target)
                if log and log.strip():
                    action_logs.append(log)
        else:
            # 기본 공격
            target = context.get_primary_monster()
            damage = _get_attack_stat(actor)
            target.take_damage(damage)
            action_logs.append(
                f"⚔️ **{actor.get_name()}** 기본 공격 → **{target.get_name()}** {damage} 데미지"
            )

    else:
        # 몬스터 행동
        monster_skill = actor.next_skill()

        if monster_skill:
            log = monster_skill.on_turn(actor, user)
            if log and log.strip():
                action_logs.append(log)
        else:
            # 기본 공격
            damage = _get_attack_stat(actor)
            user.take_damage(damage)
            action_logs.append(
                f"⚔️ **{actor.get_name()}** 기본 공격 → **{user.get_name()}** {damage} 데미지"
            )

    return action_logs


def _decrement_status_durations(entity) -> None:
    """
    엔티티의 모든 상태이상 지속시간 감소

    Args:
        entity: 엔티티 (User 또는 Monster)
    """
    for status in entity.status[:]:  # 복사본으로 순회
        if hasattr(status, 'decrement_duration'):
            status.decrement_duration()

            # 만료된 상태이상 제거
            if hasattr(status, 'is_expired') and status.is_expired():
                entity.status.remove(status)


def _create_battle_embed_multi(
    player: User,
    context: CombatContext,
    combat_log: deque[str]
) -> Embed:
    """
    전투 임베드 생성 (다중 몬스터 지원)

    Args:
        player: 플레이어
        context: 전투 컨텍스트
        combat_log: 전투 로그

    Returns:
        전투 임베드
    """
    alive = context.get_all_alive_monsters()
    monster_names = " + ".join([m.name for m in alive]) if alive else "없음"

    embed = Embed(
        title=f"⚔️ {player.get_name()} vs {monster_names}",
        color=EmbedColor.COMBAT
    )

    # 플레이어
    player_stat = player.get_stat()
    player_max_hp = player_stat[UserStatEnum.HP]
    player_hp_bar = _create_hp_bar(player.now_hp, player_max_hp, 10)
    player_hp_pct = int((player.now_hp / player_max_hp) * 100) if player_max_hp > 0 else 0
    player_status = get_status_icons(player)

    # 행동 게이지 표시
    player_gauge = context.action_gauges.get(id(player), 0)
    player_gauge_bar = _create_gauge_bar(player_gauge)

    player_value = f"{player_hp_bar}\n**{player.now_hp}** / {player_max_hp} ({player_hp_pct}%)"
    player_value += f"\n⚡ {player_gauge_bar} ({player_gauge}/100)"
    if player_status:
        player_value += f"\n{player_status}"

    embed.add_field(name=f"👤 {player.get_name()}", value=player_value, inline=False)

    # 몬스터들 (최대 3마리)
    for monster in context.monsters:
        hp_bar = _create_hp_bar(monster.now_hp, monster.hp, 8)
        hp_pct = int((monster.now_hp / monster.hp) * 100) if monster.hp > 0 else 0
        status = get_status_icons(monster)

        death_mark = " 💀" if monster.now_hp <= 0 else ""

        # 행동 게이지 표시
        monster_gauge = context.action_gauges.get(id(monster), 0)
        monster_gauge_bar = _create_gauge_bar(monster_gauge)

        monster_value = f"{hp_bar}\n**{monster.now_hp}** / {monster.hp} ({hp_pct}%)"
        monster_value += f"\n⚡ {monster_gauge_bar} ({monster_gauge}/100)"
        if status and monster.now_hp > 0:
            monster_value += f"\n{status}"

        embed.add_field(
            name=f"👹 {monster.get_name()}{death_mark}",
            value=monster_value,
            inline=True
        )

    # 전투 로그
    log_text = "\n".join(combat_log) if combat_log else "```전투 준비 중...```"
    embed.add_field(name="📜 전투 로그", value=log_text, inline=False)

    # Footer에 라운드 정보 표시
    round_marker_pct = int((context.round_marker_gauge / 100) * 100)
    embed.set_footer(text=f"🌟 라운드 {context.round_number} | 다음 라운드까지: {round_marker_pct}%")

    return embed


async def _process_combat_result_multi(
    session,
    context: CombatContext,
    turn_count: int
) -> str:
    """
    전투 결과 처리 (다중 몬스터)

    Args:
        session: 던전 세션
        context: 전투 컨텍스트
        turn_count: 총 턴 수

    Returns:
        결과 메시지
    """
    user = session.user

    if user.now_hp <= 0:
        return "💀 패배..."

    # 승리 - 각 몬스터별 보상 합산
    monster_level = session.dungeon.require_level if session.dungeon else 1
    total_exp = 0
    total_gold = 0
    result_lines = []

    for monster in context.monsters:
        exp_mult = _get_monster_exp_multiplier(monster)
        gold_mult = _get_monster_gold_multiplier(monster)

        exp = int(BASE_EXP_PER_MONSTER * (1 + monster_level / 10) * exp_mult)
        gold = int(BASE_GOLD_PER_MONSTER * (1 + monster_level / 10) * gold_mult)

        total_exp += exp
        total_gold += gold

        await CollectionService.register_monster(user, monster.id)

        # 드롭 시도 (각 몬스터 독립)
        boss_item = await _try_drop_boss_special_item(user, monster)
        if boss_item:
            result_lines.append(f"   {boss_item}")

        chest = await _try_drop_monster_box(session, monster)
        if chest:
            result_lines.append(f"   {chest}")

        skill = await _try_drop_monster_skill(user, monster)
        if skill:
            result_lines.append(f"   {skill}")

    # 그룹 보너스 (2마리 이상)
    if len(context.monsters) >= 2:
        total_exp = int(total_exp * 1.2)  # +20%
        total_gold = int(total_gold * 1.1)  # +10%

    session.total_exp += total_exp
    session.total_gold += total_gold
    session.monsters_defeated += len(context.monsters)

    monster_names = ", ".join([m.name for m in context.monsters])
    result_msg = (
        f"🏆 **{monster_names}** 처치! ({turn_count}턴)\n"
        f"   ⭐ +**{total_exp}** EXP │ 💰 +**{total_gold}** G"
    )

    if result_lines:
        result_msg += "\n" + "\n".join(result_lines)

    return result_msg


async def _execute_combat_context(
    session,
    interaction: discord.Interaction,
    context: CombatContext
) -> str:
    """
    전투 실행 (1:N 지원)

    Args:
        session: 던전 세션
        interaction: Discord 인터랙션
        context: 전투 컨텍스트

    Returns:
        전투 결과 메시지
    """
    user = session.user
    session.combat_context = context
    
    logger.info(
        f"Combat started: user={user.discord_id}, "
        f"monsters={[m.name for m in context.monsters]}"
    )

    set_combat_state(user.discord_id, True)

    try:
        combat_log: deque[str] = deque(maxlen=COMBAT.COMBAT_LOG_MAX_LENGTH)
        embed = _create_battle_embed_multi(user, context, combat_log)
        combat_message = await interaction.user.send(embed=embed)

        turn_count = 1

        # 메인 루프: 유저나 모든 몬스터가 죽을 때까지
        while user.now_hp > 0 and not context.is_all_dead():
            combat_ended = await _process_turn_multi(
                user, context, turn_count, combat_log, combat_message
            )
            if combat_ended:
                break
            turn_count += 1

        await combat_message.edit(embed=_create_battle_embed_multi(user, context, combat_log))
        await asyncio.sleep(COMBAT.COMBAT_END_DELAY)
        await combat_message.delete()

        return await _process_combat_result_multi(session, context, turn_count)

    finally:
        set_combat_state(user.discord_id, False)
        session.combat_context = None
