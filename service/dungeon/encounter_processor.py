"""
인카운터 처리 - 몬스터 스폰, 전투/도주, 인카운터 생성

던전 탐험 중 발생하는 인카운터를 처리합니다.
"""
import logging
import random
from typing import Optional

import discord
from discord import Embed

from config import COMBAT, DUNGEON, EmbedColor
from exceptions import MonsterNotFoundError, MonsterSpawnNotFoundError
from models import Monster, UserStatEnum
from models.repos.dungeon_repo import find_all_dungeon_spawn_monster_by
from models.repos.monster_repo import find_monster_by_id
from views.fight_or_flee import FightOrFleeView
from service.dungeon.encounter_service import EncounterFactory
from service.dungeon.encounter_types import EncounterType
from service.dungeon.combat_context import CombatContext
from service.session import DungeonSession

logger = logging.getLogger(__name__)


async def process_encounter(session: DungeonSession, interaction: discord.Interaction) -> str:
    """
    인카운터 처리

    다양한 유형의 인카운터를 확률에 따라 생성하고 처리합니다.

    Args:
        session: 던전 세션
        interaction: Discord 인터랙션

    Returns:
        인카운터 결과 메시지
    """
    session.exploration_step += 1

    # 탐험 버프 처리
    buffs = session.explore_buffs

    # 장비 컴포넌트에서 인카운터 확률 조정
    encounter_weights = _get_modified_encounter_weights(session.user)

    # 전투 회피 버프 (몬스터 기피제)
    if buffs.get("avoid_combat", 0) > 0:
        encounter_type = EncounterFactory.roll_encounter_type(weights=encounter_weights, exclude_monster=True)
        buffs["avoid_combat"] -= 1
        if buffs["avoid_combat"] <= 0:
            del buffs["avoid_combat"]
    # 보물 확정 버프 (보물 지도)
    elif buffs.get("force_treasure", 0) > 0:
        encounter_type = EncounterType.TREASURE
        buffs["force_treasure"] -= 1
        if buffs["force_treasure"] <= 0:
            del buffs["force_treasure"]
    else:
        encounter_type = EncounterFactory.roll_encounter_type(weights=encounter_weights)

    logger.debug(
        f"Encounter rolled: user={session.user.discord_id}, "
        f"step={session.exploration_step}, type={encounter_type.value}"
    )

    if encounter_type == EncounterType.MONSTER:
        return await _process_monster_encounter(session, interaction)

    encounter = EncounterFactory.create_encounter(encounter_type)
    result = await encounter.execute(session, interaction)

    logger.info(
        f"Encounter completed: user={session.user.discord_id}, "
        f"type={encounter_type.value}, gold={result.gold_gained}, exp={result.exp_gained}"
    )

    return result.message


def _get_modified_encounter_weights(user) -> dict:
    """
    장비 컴포넌트에서 탐험 속도/조우율을 반영한 인카운터 확률 가져오기

    Args:
        user: 유저 엔티티

    Returns:
        수정된 인카운터 가중치
    """
    from models.users import User as UserClass
    from config import ENCOUNTER

    weights = {
        EncounterType.MONSTER: ENCOUNTER.MONSTER_WEIGHT,
        EncounterType.TREASURE: ENCOUNTER.TREASURE_WEIGHT,
        EncounterType.TRAP: ENCOUNTER.TRAP_WEIGHT,
        EncounterType.EVENT: ENCOUNTER.EVENT_WEIGHT,
        EncounterType.NPC: ENCOUNTER.NPC_WEIGHT,
        EncounterType.HIDDEN_ROOM: ENCOUNTER.HIDDEN_ROOM_WEIGHT,
    }

    if not isinstance(user, UserClass):
        return weights

    # 장비 컴포넌트 확인
    if not hasattr(user, '_equipment_components_cache'):
        return weights

    components = user._equipment_components_cache

    for comp in components:
        tag = getattr(comp, '_tag', '')

        # 탐험 속도 (몬스터 조우율 조정)
        if tag == "exploration_speed":
            encounter_rate_modifier = getattr(comp, 'encounter_rate', 0.0)
            if encounter_rate_modifier != 0:
                # 음수면 몬스터 조우 감소, 양수면 증가
                weights[EncounterType.MONSTER] = max(1, weights[EncounterType.MONSTER] * (1 + encounter_rate_modifier))

    return weights


async def _process_monster_encounter(session: DungeonSession, interaction: discord.Interaction) -> str:
    """몬스터 인카운터 처리 (그룹 전투 지원)"""
    from service.dungeon.combat_executor import execute_combat_context

    try:
        progress = session.exploration_step / session.max_steps if session.max_steps > 0 else 0.0
        monsters = _spawn_monster_group(session.dungeon.id, progress)
    except (MonsterNotFoundError, MonsterSpawnNotFoundError) as e:
        logger.error(f"Monster spawn error: {e}")
        return "몬스터 정보를 찾을 수 없습니다."

    will_fight = await _ask_fight_or_flee(interaction, monsters)

    if will_fight is None:
        return f"{session.user.get_name()}은 아무 행동도 하지 않았다..."

    if not will_fight:
        return await _attempt_flee(session, monsters[0])

    context = CombatContext.from_group(monsters)

    # 필드 효과 랜덤 발동 (30% 확률)
    if random.random() < COMBAT.FIELD_EFFECT_SPAWN_RATE:
        from service.dungeon.field_effects import roll_random_field_effect
        context.field_effect = roll_random_field_effect()

    return await execute_combat_context(session, interaction, context)


async def _attempt_flee(session: DungeonSession, monster: Monster) -> str:
    """도주 시도"""
    from service.dungeon.reward_calculator import is_boss_monster, get_attack_stat

    if is_boss_monster(monster):
        logger.info(f"Flee blocked (boss): user={session.user.discord_id}, monster={monster.name}")
        return f"⚔️ **{monster.name}**는 도주를 허락하지 않는다! (보스는 도주 불가)"

    if random.random() < COMBAT.FLEE_SUCCESS_RATE:
        logger.info(f"Flee success: user={session.user.discord_id}")
        return f"🏃 **{monster.name}**에게서 도망쳤다!"

    damage = get_attack_stat(monster)
    session.user.now_hp -= damage
    session.user.now_hp = max(session.user.now_hp, 0)

    logger.info(f"Flee failed: user={session.user.discord_id}, damage={damage}")
    return f"💨 도망 실패! **{monster.name}**의 반격으로 **-{damage}** HP"


# =============================================================================
# 몬스터 스폰
# =============================================================================


def _spawn_random_monster(dungeon_id: int, progress: float = 0.0) -> Monster:
    """던전에서 랜덤 몬스터 스폰 (단일)"""
    from service.dungeon.reward_calculator import is_boss_monster

    monsters_spawn = find_all_dungeon_spawn_monster_by(dungeon_id)
    if not monsters_spawn:
        raise MonsterSpawnNotFoundError(dungeon_id)

    boss_spawns = []
    normal_spawns = []

    for spawn in monsters_spawn:
        monster = find_monster_by_id(spawn.monster_id)
        if is_boss_monster(monster):
            boss_spawns.append(spawn)
        else:
            normal_spawns.append(spawn)

    # 진행도 90% 이상일 때만 보스 등장 가능
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
    """던전에서 몬스터 그룹 스폰 (1~N마리) - CSV 기반"""
    from models.repos.static_cache import monster_cache_by_id
    from service.dungeon.reward_calculator import is_boss_monster

    first_monster = _spawn_random_monster(dungeon_id, progress)

    if is_boss_monster(first_monster):
        return [first_monster]

    group_ids = getattr(first_monster, 'group_ids', [])
    if not group_ids:
        return [first_monster]

    if random.random() > DUNGEON.GROUP_SPAWN_RATE:
        return [first_monster]

    group_size = random.randint(2, DUNGEON.MAX_GROUP_SIZE)
    monsters = [first_monster]

    for _ in range(group_size - 1):
        selected_id = random.choice(group_ids)
        if selected_id in monster_cache_by_id:
            additional = monster_cache_by_id[selected_id].copy()
            monsters.append(additional)
        else:
            logger.warning(f"Group monster {selected_id} not found in cache")

    return monsters


# =============================================================================
# 전투/도주 UI
# =============================================================================


async def _ask_fight_or_flee(interaction: discord.Interaction, monsters: list[Monster]) -> Optional[bool]:
    """전투/도주 선택 UI 표시 (그룹 전투 지원)"""
    from models.repos.skill_repo import get_skill_by_id

    # 그룹 전투 여부 확인
    is_group = len(monsters) > 1
    first_monster = monsters[0]

    # 타이틀 및 설명
    if is_group:
        title = f"🐲 {first_monster.name} 외 {len(monsters) - 1}마리 이(가) 나타났다! [그룹 전투]"
        description = f"**{first_monster.name}** ({len(monsters)}마리)\n{first_monster.description or '무서운 기운이 느껴진다...'}"
    else:
        title = f"🐲 {first_monster.name} 이(가) 나타났다!"
        description = first_monster.description or "무서운 기운이 느껴진다..."

    embed = discord.Embed(
        title=title,
        description=description,
        color=EmbedColor.ERROR
    )

    # 첫 번째 몬스터 스탯 표시 (도감과 동일한 이모지 레이아웃)
    monster_stat = first_monster.get_stat()
    evasion = getattr(first_monster, 'evasion', 0)
    attribute = getattr(first_monster, 'attribute', '무속성')

    # 1행: 체력, 공격력
    embed.add_field(
        name="❤️ 체력",
        value=f"{monster_stat[UserStatEnum.HP]:,}",
        inline=True
    )
    embed.add_field(
        name="⚔️ 공격력",
        value=f"{monster_stat[UserStatEnum.ATTACK]}",
        inline=True
    )
    embed.add_field(name="\u200b", value="\u200b", inline=True)  # 공백

    # 2행: 방어력, 마방
    embed.add_field(
        name="🛡️ 방어력",
        value=f"{monster_stat[UserStatEnum.DEFENSE]}",
        inline=True
    )
    embed.add_field(
        name="🌀 마방",
        value=f"{monster_stat[UserStatEnum.AP_DEFENSE]}",
        inline=True
    )
    embed.add_field(name="\u200b", value="\u200b", inline=True)  # 공백

    # 3행: 마공, 속도, 회피
    embed.add_field(
        name="🔮 마공",
        value=f"{monster_stat[UserStatEnum.AP_ATTACK]}",
        inline=True
    )
    embed.add_field(
        name="💨 속도",
        value=f"{monster_stat[UserStatEnum.SPEED]}",
        inline=True
    )
    embed.add_field(
        name="💰 회피",
        value=f"{evasion}%",
        inline=True
    )

    # 스킬 정보 (첫 번째 몬스터 기준)
    active_skill_names = []
    passive_skill_names = []
    monster_skill_ids = getattr(first_monster, 'skill_ids', [])
    for sid in monster_skill_ids:
        if sid != 0:
            skill = get_skill_by_id(sid)
            if not skill:
                continue
            if skill.is_passive:
                if skill.name not in passive_skill_names:
                    passive_skill_names.append(skill.name)
            else:
                if skill.name not in active_skill_names:
                    active_skill_names.append(skill.name)

    if active_skill_names:
        embed.add_field(name="📜 스킬", value=", ".join(active_skill_names), inline=False)
    if passive_skill_names:
        embed.add_field(name="🌟 패시브", value=", ".join(passive_skill_names), inline=False)

    view = FightOrFleeView(user=interaction.user)
    msg = await interaction.user.send(embed=embed, view=view)
    view.message = msg

    await view.wait()
    try:
        await view.message.delete()
    except discord.NotFound:
        pass

    return view.result
