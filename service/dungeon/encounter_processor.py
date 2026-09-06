"""
인카운터 처리 - 몬스터 스폰, 전투/도주, 인카운터 생성

던전 탐험 중 발생하는 인카운터를 처리합니다.
"""
import logging
import os
import random
from typing import Optional

import discord
from discord import Embed

from config import COMBAT, DUNGEON, EmbedColor
from exceptions import MonsterNotFoundError, MonsterSpawnNotFoundError, WeeklyTowerRestrictionError
from models import Monster, UserStatEnum
from models.repos.dungeon_repo import find_all_dungeon_spawn_monster_by
from models.repos.monster_repo import find_monster_by_id
from views.fight_or_flee import FightOrFleeView
from service.dungeon.encounter_service import EncounterFactory
from service.dungeon.encounter_types import EncounterType
from service.dungeon.combat_context import CombatContext
from service.session import DungeonSession, ContentType, get_session, set_combat_state
from service.tower.tower_restriction import enforce_flee_restriction

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

    # 주간 타워는 "1층 = 1전투" 규칙을 강제한다.
    # 소셜 encounter가 먼저 발동하면 전투 없이 층이 넘어갈 수 있으므로
    # 타워에서는 몬스터 encounter만 허용한다.
    if session.content_type == ContentType.WEEKLY_TOWER:
        return await _process_monster_encounter(session, interaction)
    if session.content_type == ContentType.RAID:
        return await _process_monster_encounter(session, interaction)

    # Phase 3: 멀티유저 encounter 우선 체크
    from service.dungeon.social_encounter_checker import check_social_encounter
    from service.dungeon.social_encounter_types import (
        CrossroadsEncounter,
        CampfireEncounter,
    )

    social_type = check_social_encounter(session)
    if social_type == "crossroads":
        encounter = CrossroadsEncounter()
        try:
            result = await encounter.execute(session, interaction)
            if result:  # 조건 충족됨
                session.encounter_event_cooldown = session.exploration_step
                logger.info(
                    f"Crossroads encounter completed: user={session.user.discord_id}, "
                    f"step={session.exploration_step}"
                )
                return result.message
        except Exception as e:
            logger.error(f"Crossroads encounter error: {e}", exc_info=True)
            # 에러 시 일반 encounter로 fallback
    elif social_type == "campfire":
        encounter = CampfireEncounter()
        try:
            result = await encounter.execute(session, interaction)
            if result:
                session.encounter_event_cooldown = session.exploration_step
                logger.info(
                    f"Campfire encounter completed: user={session.user.discord_id}, "
                    f"step={session.exploration_step}, participants={result.message}"
                )
                return result.message
        except Exception as e:
            logger.error(f"Campfire encounter error: {e}", exc_info=True)
            # 에러 시 일반 encounter로 fallback

    # 탐험 버프 처리
    buffs = session.explore_buffs

    # 장비 컴포넌트에서 인카운터 확률 조정
    encounter_weights = _get_modified_encounter_weights(session.user)

    # 마지막 구역: 보스 확정 (100%)
    if session.exploration_step >= session.max_steps:
        encounter_type = EncounterType.MONSTER
    # 전투 회피 버프 (몬스터 기피제)
    elif buffs.get("avoid_combat", 0) > 0:
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

    from service.dungeon.skill import get_passive_effect_bonuses

    passive = get_passive_effect_bonuses(user)
    weights[EncounterType.MONSTER] *= max(0.10, 1.0 - passive.get("ambush_reduce", 0.0))
    weights[EncounterType.HIDDEN_ROOM] *= max(0.0, 1.0 + passive.get("secret_find", 0.0))
    weights[EncounterType.TREASURE] *= max(0.0, 1.0 + passive.get("chest_find", 0.0))

    components = getattr(user, '_equipment_components_cache', []) or []

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

    progress = session.exploration_step / session.max_steps if session.max_steps > 0 else 0.0

    try:
        if session.content_type == ContentType.WEEKLY_TOWER:
            from service.tower.tower_service import get_floor_monster
            monsters = [await get_floor_monster(session.current_floor)]
        elif session.content_type == ContentType.RAID:
            monsters = [_spawn_raid_boss(session.dungeon.id)]
            from service.raid.raid_service import init_raid_part_state_from_boss
            init_raid_part_state_from_boss(session, monsters[0])
        elif session.roguelike_enabled and session.roguelike_combat_kind:
            monsters = _spawn_roguelike_monsters(
                session.dungeon.id,
                session.roguelike_combat_kind,
                progress,
                rng=random.Random(session.roguelike_resolution_seed),
            )
            if session.roguelike_combat_kind != "boss":
                _apply_roguelike_stat_scale(monsters, session.roguelike_stat_scale)
        else:
            monsters = _spawn_monster_group(session.dungeon.id, progress)
    except (MonsterNotFoundError, MonsterSpawnNotFoundError) as e:
        logger.error(f"Monster spawn error: {e}")
        return "몬스터 정보를 찾을 수 없습니다."

    # Phase 4: 보스방 대기실 체크
    from service.dungeon.reward_calculator import is_boss_monster

    if (
        session.content_type != ContentType.WEEKLY_TOWER
        and len(monsters) == 1
        and is_boss_monster(monsters[0])
        and session.voice_channel_id
    ):
        from service.dungeon.social_encounter_checker import check_boss_waiting_room
        from service.dungeon.social_encounter_types import BossRoomEncounter

        if check_boss_waiting_room(session.dungeon.id, progress):
            # 보스방 대기실 모드로 전환
            boss_encounter = BossRoomEncounter(monsters[0])
            boss_result = await boss_encounter.execute(session, interaction)

            if boss_result:
                # 대기실에서 시작된 멀티플레이어 전투
                if boss_result.context:
                    return await execute_combat_context(session, interaction, boss_result.context)
                else:
                    # context가 없으면 메시지만 반환
                    return boss_result.message
            else:
                # 대기실 취소됨 → 일반 encounter로
                logger.info(f"Boss waiting room cancelled, falling back to normal encounter")

    will_fight = True if session.roguelike_skip_flee else await _ask_fight_or_flee(session, interaction, monsters)

    if will_fight is None:
        return f"{session.user.get_name()}은 아무 행동도 하지 않았다..."

    if not will_fight:
        try:
            return await _attempt_flee(session, monsters[0])
        except WeeklyTowerRestrictionError as e:
            return f"⚠️ {e}"

    if session.roguelike_enabled and session.rest_shield_rate > 0:
        from service.dungeon.status import ShieldBuff
        max_hp = session.user.get_stat()[UserStatEnum.HP]
        shield = ShieldBuff()
        shield.shield_hp = max(1, int(max_hp * session.rest_shield_rate))
        shield.duration = 999
        session.user.status.append(shield)
        session.rest_shield_rate = 0.0

    context = CombatContext.from_group(monsters)
    session.combat_context = context
    session.in_combat = True

    # Phase 4: 동시 조우 체크 (전투 시작 직후)
    if session.voice_channel_id:
        from service.dungeon.social_encounter_checker import check_simultaneous_encounter
        from service.dungeon.social_encounter_types import SimultaneousEncounter

        partner_session = check_simultaneous_encounter(session)
        if partner_session:
            # 동시 조우 발생
            simultaneous_encounter = SimultaneousEncounter(partner_session)
            simultaneous_result = await simultaneous_encounter.execute(session, interaction)

            if simultaneous_result:
                logger.info(f"Simultaneous encounter processed: {simultaneous_result.message}")
                # 협력 모드면 파트너가 이미 participants에 추가됨
                # 경쟁 모드면 race_state가 active_encounter_event에 저장됨
            else:
                # 독립 모드 - 각자 진행
                logger.info(f"Simultaneous encounter: independent mode")

    # 필드 효과 랜덤 발동 (30% 확률)
    if random.random() < COMBAT.FIELD_EFFECT_SPAWN_RATE:
        from config.beginner_balance import AREA_FIELDS
        from service.dungeon.field_effects import roll_random_field_effect, create_field_effect, FieldEffectType
        choices = AREA_FIELDS.get(session.dungeon.id) if session.content_type == ContentType.NORMAL_DUNGEON else None
        if choices is None:
            context.field_effect = roll_random_field_effect()
        elif choices:
            context.field_effect = create_field_effect(FieldEffectType(random.choice(choices)))

    # Phase 3: 교차로 만남 "같이 가기" 자동 합류
    team_up_partner_id = session.explore_buffs.pop("team_up_partner", None)
    if team_up_partner_id:
        partner_session = get_session(team_up_partner_id)
        if partner_session and not partner_session.in_combat and not partner_session.ended:
            # 파트너 자동 합류
            session.participants[team_up_partner_id] = partner_session.user
            session.contribution[team_up_partner_id] = 0
            logger.info(f"Team-up partner {team_up_partner_id} auto-joined combat for {session.user_id}")

    return await execute_combat_context(session, interaction, context)


async def _attempt_flee(session: DungeonSession, monster: Monster) -> str:
    """도주 시도"""
    enforce_flee_restriction(session)
    from service.dungeon.reward_calculator import is_boss_monster, get_attack_stat

    if is_boss_monster(monster):
        logger.info(f"Flee blocked (boss): user={session.user.discord_id}, monster={monster.name}")
        return f"⚔️ **{monster.name}**는 도주를 허락하지 않는다! (보스는 도주 불가)"

    if random.random() < COMBAT.FLEE_SUCCESS_RATE:
        logger.info(f"Flee success: user={session.user.discord_id}")

        # Phase 5: 전투 기록 저장 (도주)
        try:
            from service.combat_history.history_service import HistoryService

            await HistoryService.record_combat(
                user_id=session.user.id,  # User.id (PK), not discord_id
                dungeon_id=session.dungeon.id,
                step=session.exploration_step,
                monster_name=monster.name,
                result="fled",
                damage=0,
                turns=0,
                voice_channel_id=session.voice_channel_id
            )
            logger.debug(f"Combat history (fled) recorded for user {session.user.discord_id}")
        except Exception as e:
            logger.error(f"Failed to record combat history (fled): {e}", exc_info=True)

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

    # 마지막 스텝(100%)에서만 보스 등장 가능 (10% 확률)
    is_final_step = progress >= 1.0
    boss_roll = random.random() < DUNGEON.BOSS_SPAWN_RATE_AT_END

    if boss_spawns and is_final_step and boss_roll:
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

    return monster.copy()


def _spawn_roguelike_monsters(
    dungeon_id: int,
    kind: str,
    progress: float,
    *,
    rng: random.Random | None = None,
) -> list[Monster]:
    """Spawn independent monster copies for a preselected roguelike route."""
    from models.monster import MonsterTypeEnum
    from service.dungeon.reward_calculator import normalize_monster_type

    spawns = find_all_dungeon_spawn_monster_by(dungeon_id)
    if not spawns:
        raise MonsterSpawnNotFoundError(dungeon_id)
    desired = {
        "elite": MonsterTypeEnum.ELITE.value,
        "boss": MonsterTypeEnum.BOSS.value,
    }.get(kind, MonsterTypeEnum.COMMON.value)
    candidates = []
    for spawn in spawns:
        monster = find_monster_by_id(spawn.monster_id)
        if monster and normalize_monster_type(monster) == desired:
            candidates.append(spawn)
    if not candidates and kind == "elite":
        candidates = [
            spawn for spawn in spawns
            if normalize_monster_type(find_monster_by_id(spawn.monster_id)) != MonsterTypeEnum.BOSS.value
        ]
    if not candidates:
        raise MonsterSpawnNotFoundError(dungeon_id)
    rng = rng or random
    picked = rng.choices(candidates, weights=[max(0.0001, spawn.prob) for spawn in candidates], k=1)[0]
    source = find_monster_by_id(picked.monster_id)
    if not source:
        raise MonsterNotFoundError(picked.monster_id)
    monster = source.copy()
    if kind == "elite" and normalize_monster_type(monster) != MonsterTypeEnum.ELITE.value:
        monster.type = MonsterTypeEnum.ELITE
    return [monster]


def _apply_roguelike_stat_scale(monsters: list[Monster], scale: float) -> None:
    """Scale combat copies only; cached static monsters must remain immutable."""
    scale = max(0.1, float(scale))
    for monster in monsters:
        for attribute in ("hp", "attack", "defense", "ap_attack", "ap_defense", "speed"):
            value = getattr(monster, attribute, 0)
            setattr(monster, attribute, max(1 if attribute == "hp" else 0, int(value * scale)))
        monster.now_hp = monster.hp


def _spawn_raid_boss(dungeon_id: int) -> Monster:
    """레이드 보스 1체 스폰 (던전 스폰 정보에서 보스 우선 선택)"""
    from service.dungeon.reward_calculator import is_boss_monster

    monsters_spawn = find_all_dungeon_spawn_monster_by(dungeon_id)
    if not monsters_spawn:
        raise MonsterSpawnNotFoundError(dungeon_id)

    boss_spawns = []
    for spawn in monsters_spawn:
        monster = find_monster_by_id(spawn.monster_id)
        if monster and is_boss_monster(monster):
            boss_spawns.append(spawn)

    spawn_pool = boss_spawns or monsters_spawn
    picked = random.choices(
        population=spawn_pool,
        weights=[max(0.0001, s.prob) for s in spawn_pool],
        k=1
    )[0]

    monster = find_monster_by_id(picked.monster_id)
    if not monster:
        raise MonsterNotFoundError(picked.monster_id)
    return monster.copy()


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


async def _ask_fight_or_flee(
    session: DungeonSession,
    interaction: discord.Interaction,
    monsters: list[Monster]
) -> Optional[bool]:
    """전투/도주 선택 UI 표시 (그룹 전투 지원)"""
    from models.repos.skill_repo import get_skill_by_id

    if session.content_type in (ContentType.WEEKLY_TOWER, ContentType.RAID):
        return True
    if os.getenv("E2E_UI_AUTOPILOT") == "TRUE":
        return True

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
