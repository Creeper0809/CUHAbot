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

from config import COMBAT, DUNGEON, DROP, EmbedColor
from DTO.dungeon_control import DungeonControlView
from DTO.fight_or_flee import FightOrFleeView
from exceptions import InventoryFullError, MonsterNotFoundError, MonsterSpawnNotFoundError
from models import Droptable, Item, Monster, MonsterTypeEnum, User
from models.repos.dungeon_repo import find_all_dungeon_spawn_monster_by
from models.repos.monster_repo import find_monster_by_id
from service.collection_service import CollectionService
from service.dungeon.encounter_service import EncounterFactory
from service.dungeon.encounter_types import EncounterType
from service.inventory_service import InventoryService
from service.reward_service import RewardService
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
        return f"🏃 **{monster.name}**에게서 도망쳤다!"

    # 도주 실패 시 몬스터 공격
    damage = monster.attack
    session.user.now_hp -= damage
    session.user.now_hp = max(session.user.now_hp, 0)

    logger.info(f"Flee failed: user={session.user.discord_id}, damage={damage}")
    return f"💨 도망 실패! **{monster.name}**의 반격으로 **-{damage}** HP"


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

    boss_spawns = []
    normal_spawns = []

    for spawn in monsters_spawn:
        monster = find_monster_by_id(spawn.monster_id)
        if _is_boss_monster(monster):
            boss_spawns.append(spawn)
        else:
            normal_spawns.append(spawn)

    if boss_spawns and random.random() < DUNGEON.BOSS_SPAWN_RATE:
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
    embed.add_field(name="❤️ 체력", value=f"{monster.hp}", inline=True)
    embed.add_field(name="⚔️ 공격력", value=f"{monster.attack}", inline=True)
    embed.add_field(name="🔮 마공", value=f"{getattr(monster, 'ap_attack', 0)}", inline=True)
    embed.add_field(name="🛡️ 방어력", value=f"{getattr(monster, 'defense', 0)}", inline=True)
    embed.add_field(name="🌀 마방", value=f"{getattr(monster, 'ap_defense', 0)}", inline=True)
    embed.add_field(name="💨 속도", value=f"{getattr(monster, 'speed', 10)}", inline=True)
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
    전투 실행

    Args:
        session: 던전 세션
        interaction: Discord 인터랙션
        monster: 전투할 몬스터

    Returns:
        전투 결과 메시지
    """
    # 몬스터 복사본 생성 (캐시 원본 보호)
    monster = monster.copy()

    logger.info(f"Combat started: user={session.user.discord_id}, monster={monster.name}")
    logger.info(f"User equipped_skill: {session.user.equipped_skill}")
    logger.info(f"User skill_queue: {session.user.skill_queue}")

    # 전투 상태 설정 (try 블록 전에 설정하되 finally에서 항상 해제)
    set_combat_state(session.user_id, True)

    try:
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

        # 전투 결과 처리 및 보상
        return await _process_combat_result(session, monster, turn_count)

    finally:
        # 전투 상태 해제 (항상 실행)
        set_combat_state(session.user_id, False)


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

    # 상자 드롭 확인
    dropped_chest_msg = await _try_drop_monster_chest(session, monster)

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


def _roll_chest_grade() -> str:
    return random.choices(
        ["normal", "silver", "gold"],
        weights=DROP.CHEST_GRADE_WEIGHTS,
        k=1
    )[0]


def _get_chest_item_id(chest_grade: str) -> Optional[int]:
    chest_item_map = {
        "normal": DROP.CHEST_ITEM_NORMAL_ID,
        "silver": DROP.CHEST_ITEM_SILVER_ID,
        "gold": DROP.CHEST_ITEM_GOLD_ID,
    }
    return chest_item_map.get(chest_grade)


async def _try_drop_monster_chest(
    session: DungeonSession,
    monster: Monster
) -> Optional[str]:
    drop_rate = DROP.CHEST_DROP_RATE * _get_monster_drop_multiplier(monster)
    if random.random() > min(drop_rate, 1.0):
        return None

    chest_grade = _roll_chest_grade()
    chest_item_id = _get_chest_item_id(chest_grade)
    if not chest_item_id:
        return None

    try:
        await InventoryService.add_item(session.user, chest_item_id, 1)
    except InventoryFullError:
        return "📦 상자를 얻었지만 인벤토리가 가득 찼다..."

    item = await Item.get_or_none(id=chest_item_id)
    item_name = item.name if item else "상자"
    chest_emoji = {"normal": "📦", "silver": "🎁", "gold": "💎"}.get(chest_grade, "📦")
    return f"{chest_emoji} 「{item_name}」 획득!"


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

    # 랜덤 스킬 선택
    dropped_skill_id = random.choice(valid_skills)

    # 유저에게 스킬 지급
    try:
        await SkillOwnershipService.add_skill(user, dropped_skill_id, 1)

        # 스킬 이름 조회
        from models.repos.skill_repo import get_skill_by_id
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

    # 턴 시작 효과는 공격 페이즈 전에 별도 표시
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
    공격 페이즈 처리

    Returns:
        전투 종료 여부
    """
    attack_logs = []

    # 턴 헤더
    turn_header = f"━━━ ⚔️ **{turn_count}턴** ━━━"

    # 선공 공격
    if first_skill:
        logger.info(f"First attacker ({first.get_name()}) using skill: {first_skill.name}")
        first_log = first_skill.on_turn(first, second)
        logger.info(f"Skill result: '{first_log}', target HP: {second.now_hp}")
        if first_log and first_log.strip():
            attack_logs.append(first_log)
        else:
            logger.warning(f"Skill {first_skill.name} returned empty log, using basic attack")
            damage = first.attack
            second.now_hp -= damage
            second.now_hp = max(second.now_hp, 0)
            attack_logs.append(_format_attack_log(first.get_name(), "기본 공격", second.get_name(), damage))
    else:
        damage = first.attack
        second.now_hp -= damage
        second.now_hp = max(second.now_hp, 0)
        logger.info(f"First attacker ({first.get_name()}) basic attack: {damage} damage, target HP: {second.now_hp}")
        attack_logs.append(_format_attack_log(first.get_name(), "기본 공격", second.get_name(), damage))

    # 전투 종료 체크 (선공 후)
    if user.now_hp <= 0 or monster.now_hp <= 0:
        if attack_logs:
            combat_log.append(turn_header + "\n" + "\n".join(attack_logs))
        return True

    # 후공 공격
    if second_skill:
        second_log = second_skill.on_turn(second, first)
        if second_log and second_log.strip():
            attack_logs.append(second_log)
        else:
            logger.warning(f"Skill {second_skill.name} returned empty log, using basic attack")
            damage = second.attack
            first.now_hp -= damage
            first.now_hp = max(first.now_hp, 0)
            attack_logs.append(_format_attack_log(second.get_name(), "기본 공격", first.get_name(), damage))
    else:
        damage = second.attack
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

    # 턴 종료 효과 (DOT, 버프 만료 등)
    phase_footer = "🌙 **턴 종료 효과**"
    combat_log.append(phase_footer + "\n" + "\n".join(end_logs))
    await combat_message.edit(embed=_create_battle_embed(user, monster, combat_log))
    await asyncio.sleep(COMBAT.TURN_PHASE_DELAY)


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
    player_hp_bar = _create_hp_bar(player.now_hp, player.hp, 10)
    player_hp_pct = int((player.now_hp / player.hp) * 100) if player.hp > 0 else 0
    player_buffs = " ".join([s.get_emoji() for s in player.status]) if player.status else ""

    embed.add_field(
        name=f"👤 {player.get_name()}",
        value=(
            f"{player_hp_bar}\n"
            f"**{player.now_hp}** / {player.hp} ({player_hp_pct}%)\n"
            f"{player_buffs}" if player_buffs else f"{player_hp_bar}\n**{player.now_hp}** / {player.hp} ({player_hp_pct}%)"
        ),
        inline=True
    )

    # 몬스터 HP 바
    monster_hp_bar = _create_hp_bar(monster.now_hp, monster.hp, 10)
    monster_hp_pct = int((monster.now_hp / monster.hp) * 100) if monster.hp > 0 else 0
    monster_buffs = " ".join([s.get_emoji() for s in monster.status]) if monster.status else ""

    embed.add_field(
        name=f"👹 {monster.get_name()}",
        value=(
            f"{monster_hp_bar}\n"
            f"**{monster.now_hp}** / {monster.hp} ({monster_hp_pct}%)\n"
            f"{monster_buffs}" if monster_buffs else f"{monster_hp_bar}\n**{monster.now_hp}** / {monster.hp} ({monster_hp_pct}%)"
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
    hp_bar = _create_hp_bar(session.user.now_hp, session.user.hp, 8)
    hp_pct = int((session.user.now_hp / session.user.hp) * 100) if session.user.hp > 0 else 0

    embed.add_field(
        name=f"👤 {user_name}",
        value=(
            f"{hp_bar}\n"
            f"HP **{session.user.now_hp}** / {session.user.hp} ({hp_pct}%)"
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
