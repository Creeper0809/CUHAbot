"""
전투 실행기 - 전투 루프, 턴 처리, 행동 게이지 시스템

1:N 전투를 행동 게이지 기반으로 처리합니다.
"""
import asyncio
import logging
from collections import deque
from typing import Union

import discord

from config import COMBAT
from models import User, Monster, UserStatEnum
from service.dungeon.status import (
    can_entity_act, get_cc_effect_name, process_status_ticks,
)
from service.dungeon.combat_context import CombatContext
from service.player.stat_synergy_combat import (
    has_first_strike, roll_extra_action, get_hp_regen_per_turn_pct,
)
from service.session import set_combat_state

logger = logging.getLogger(__name__)


async def execute_combat_context(session, interaction: discord.Interaction, context: CombatContext) -> str:
    """
    전투 실행 (1:N 지원)

    Args:
        session: 던전 세션
        interaction: Discord 인터랙션
        context: 전투 컨텍스트

    Returns:
        전투 결과 메시지
    """
    from service.dungeon.dungeon_ui import create_battle_embed_multi
    from service.dungeon.reward_calculator import process_combat_result_multi

    user = session.user
    session.combat_context = context

    logger.info(
        f"Combat started: user={user.discord_id}, "
        f"monsters={[m.name for m in context.monsters]}"
    )

    set_combat_state(user.discord_id, True)

    try:
        combat_log: deque[str] = deque(maxlen=COMBAT.COMBAT_LOG_MAX_LENGTH)
        embed = create_battle_embed_multi(user, context, combat_log)
        combat_message = await interaction.user.send(embed=embed)

        turn_count = 1

        while user.now_hp > 0 and not context.is_all_dead():
            combat_ended = await _process_turn_multi(
                user, context, turn_count, combat_log, combat_message
            )
            if combat_ended:
                break
            turn_count += 1

        await combat_message.edit(embed=create_battle_embed_multi(user, context, combat_log))
        await asyncio.sleep(COMBAT.COMBAT_END_DELAY)
        await combat_message.delete()

        return await process_combat_result_multi(session, context, turn_count)

    finally:
        set_combat_state(user.discord_id, False)
        session.combat_context = None
        _reset_all_skill_usage_counts()


# =============================================================================
# 턴 처리 (행동 게이지 시스템)
# =============================================================================


async def _process_turn_multi(
    user: User,
    context: CombatContext,
    turn_count: int,
    combat_log: deque[str],
    combat_message: discord.Message
) -> bool:
    """
    턴 처리 (1:N 지원) - 행동 게이지 시스템

    Returns:
        전투 종료 여부
    """
    from service.dungeon.dungeon_ui import create_battle_embed_multi

    # 게이지 초기화 (첫 호출 시)
    if not context.action_gauges:
        context.user = user
        context.initialize_gauges(user)
        # 시너지: 선공 확정
        if has_first_strike(user):
            context.action_gauges[id(user)] = COMBAT.ACTION_GAUGE_MAX
            combat_log.append("💨 **선공 확정** 시너지 발동!")
        # 패시브 발동 로그
        passive_logs = _apply_combat_start_passives(user, context)
        for log in passive_logs:
            combat_log.append(log)
        combat_log.append(f"━━━ ⚔️ **전투 시작 - 라운드 {context.round_number}** ━━━")

    while context.action_count < COMBAT.MAX_ACTIONS_PER_LOOP:
        if context.is_all_dead() or user.now_hp <= 0:
            return True

        actor = context.get_next_actor(user)
        if not actor:
            context.fill_gauges(user)
            continue

        context.action_count += 1

        # DOT 틱
        status_logs = process_status_ticks(actor)
        for log in status_logs:
            combat_log.append(log)

        # CC 체크
        if not can_entity_act(actor):
            cc_name = get_cc_effect_name(actor)
            combat_log.append(f"💫 **{actor.get_name()}** {cc_name}! 행동 불가")
            context.consume_gauge(actor)
            _decrement_status_durations(actor)
            await combat_message.edit(embed=create_battle_embed_multi(user, context, combat_log))
            await asyncio.sleep(COMBAT.TURN_PHASE_DELAY)

            if context.check_and_advance_round():
                combat_log.append(f"━━━ 🌟 **라운드 {context.round_number}** ━━━")
                await combat_message.edit(embed=create_battle_embed_multi(user, context, combat_log))
                await asyncio.sleep(COMBAT.TURN_PHASE_DELAY * 0.5)
            continue

        # 행동 실행
        alive_before = {id(m) for m in context.get_all_alive_monsters()}
        action_logs = _execute_entity_action(user, actor, context)
        for log in action_logs:
            combat_log.append(log)

        # 사망 트리거 (on_death 컴포넌트)
        death_logs = _check_death_triggers(context, alive_before, user)
        for log in death_logs:
            combat_log.append(log)

        # 패시브: 재생/조건부 처리
        passive_logs = _process_passive_effects(actor)
        for log in passive_logs:
            combat_log.append(log)

        # 시너지: 유저 행동 후 HP 자동회복
        if actor is user:
            regen_log = _apply_synergy_hp_regen(user)
            if regen_log:
                combat_log.append(regen_log)

        context.consume_gauge(actor)

        # 시너지: 유저 추가 행동
        if actor is user and roll_extra_action(user):
            context.action_gauges[id(user)] += COMBAT.ACTION_GAUGE_COST
            combat_log.append("🌀 **잔영** 시너지! 추가 행동!")

        _decrement_status_durations(actor)

        await combat_message.edit(embed=create_battle_embed_multi(user, context, combat_log))
        await asyncio.sleep(COMBAT.TURN_PHASE_DELAY)

        if context.check_and_advance_round():
            combat_log.append(f"━━━ 🌟 **라운드 {context.round_number}** ━━━")
            await combat_message.edit(embed=create_battle_embed_multi(user, context, combat_log))
            await asyncio.sleep(COMBAT.TURN_PHASE_DELAY * 0.5)

        if user.now_hp <= 0 or context.is_all_dead():
            return True

    logger.warning(f"Combat reached max actions: {COMBAT.MAX_ACTIONS_PER_LOOP}")
    return True


# =============================================================================
# 엔티티 행동
# =============================================================================


def _execute_entity_action(
    user: User,
    actor: Union[User, Monster],
    context: CombatContext
) -> list[str]:
    """엔티티의 행동 실행"""
    from models.users import User as UserClass
    from service.dungeon.reward_calculator import get_attack_stat

    if isinstance(actor, UserClass):
        return _execute_user_action(actor, context)
    return _execute_monster_action(actor, user)


def _execute_user_action(user: User, context: CombatContext) -> list[str]:
    """유저 행동"""
    from service.dungeon.reward_calculator import get_attack_stat

    logs = []
    user_skill = user.next_skill()

    if user_skill:
        if _is_skill_aoe(user_skill):
            for monster in context.get_all_alive_monsters():
                log = user_skill.on_turn(user, monster)
                if log and log.strip():
                    logs.append(log)
        else:
            target = context.get_primary_monster()
            log = user_skill.on_turn(user, target)
            if log and log.strip():
                logs.append(log)
    else:
        from service.dungeon.damage_pipeline import process_incoming_damage
        target = context.get_primary_monster()
        damage = get_attack_stat(user)
        event = process_incoming_damage(target, damage, attacker=user)
        logs.extend(event.extra_logs)
        logs.append(f"⚔️ **{user.get_name()}** 기본 공격 → **{target.get_name()}** {event.actual_damage} 데미지")
        if event.reflected_damage > 0:
            reflect_event = process_incoming_damage(user, event.reflected_damage, is_reflected=True)
            logs.append(f"   🔄 반사 데미지 → **{user.get_name()}** {reflect_event.actual_damage}")

    return logs


def _execute_monster_action(monster: Monster, user: User) -> list[str]:
    """몬스터 행동"""
    from service.dungeon.reward_calculator import get_attack_stat
    from service.dungeon.damage_pipeline import process_incoming_damage

    logs = []
    monster_skill = monster.next_skill()

    if monster_skill:
        log = monster_skill.on_turn(monster, user)
        if log and log.strip():
            logs.append(log)
    else:
        damage = get_attack_stat(monster)
        event = process_incoming_damage(user, damage, attacker=monster)
        logs.extend(event.extra_logs)
        logs.append(f"⚔️ **{monster.get_name()}** 기본 공격 → **{user.get_name()}** {event.actual_damage} 데미지")
        if event.reflected_damage > 0:
            reflect_event = process_incoming_damage(monster, event.reflected_damage, is_reflected=True)
            logs.append(f"   🔄 반사 데미지 → **{monster.get_name()}** {reflect_event.actual_damage}")

    return logs


# =============================================================================
# 유틸리티
# =============================================================================


def _apply_combat_start_passives(user: User, context: CombatContext) -> list[str]:
    """전투 시작 시 모든 엔티티의 패시브 발동 로그 출력"""
    from models.repos.skill_repo import get_skill_by_id

    logs = []
    entities = [user] + list(context.monsters)

    for entity in entities:
        skill_ids = getattr(entity, 'equipped_skill', None) or getattr(entity, 'use_skill', [])
        for sid in skill_ids:
            if sid == 0:
                continue
            skill = get_skill_by_id(sid)
            if not skill or not skill.is_passive:
                continue
            log = skill.on_turn_start(entity, context)
            if log and log.strip():
                logs.append(log)

    return logs


def _process_passive_effects(actor) -> list[str]:
    """매 턴 재생/조건부/턴성장 패시브 처리"""
    from models.repos.skill_repo import get_skill_by_id

    logs = []
    skill_ids = getattr(actor, 'equipped_skill', None) or getattr(actor, 'use_skill', [])

    for sid in skill_ids:
        if sid == 0:
            continue
        skill = get_skill_by_id(sid)
        if not skill or not skill.is_passive:
            continue

        for comp in skill.components:
            tag = getattr(comp, '_tag', '')
            log = ""
            if tag == "passive_regen":
                log = comp.process_regen(actor)
            elif tag == "conditional_passive":
                log = comp.process_conditional(actor)
            elif tag == "passive_turn_scaling":
                log = comp.process_turn_scaling(actor)
            if log and log.strip():
                logs.append(log)

    return logs


def _check_death_triggers(
    context: CombatContext,
    alive_before: set[int],
    killer: User,
) -> list[str]:
    """사망한 몬스터의 on_death 컴포넌트 트리거"""
    from models.repos.skill_repo import get_skill_by_id

    logs = []
    for monster in context.monsters:
        if id(monster) not in alive_before:
            continue
        if monster.now_hp > 0:
            continue

        # 이 몬스터가 방금 죽음 → on_death 트리거
        for skill_id in getattr(monster, 'skill_ids', []):
            if skill_id == 0:
                continue
            skill = get_skill_by_id(skill_id)
            if not skill:
                continue
            on_death_handler = getattr(skill, 'on_death', None)
            if callable(on_death_handler):
                log = on_death_handler(monster, killer, context)
                if log and log.strip():
                    logs.append(log)
                continue

            # Fallback: 직접 컴포넌트에서 on_death 처리 (비정상 캐시 방어)
            components = getattr(skill, 'components', [])
            for component in components:
                if hasattr(component, 'on_death'):
                    log = component.on_death(monster, killer, context)
                    if log and log.strip():
                        logs.append(log)
    return logs


def _is_skill_aoe(skill) -> bool:
    """스킬이 AOE(전체 공격)인지 확인"""
    if not skill:
        return False
    for component in skill.components:
        if hasattr(component, 'is_aoe') and component.is_aoe:
            return True
    return False


def _apply_synergy_hp_regen(user: User) -> str:
    """시너지: 턴당 HP 자동회복"""
    regen_pct = get_hp_regen_per_turn_pct(user)
    if regen_pct <= 0:
        return ""

    max_hp = user.get_stat().get(UserStatEnum.HP, user.hp)
    heal = int(max_hp * regen_pct / 100)
    if heal <= 0:
        return ""

    old_hp = user.now_hp
    user.now_hp = min(user.now_hp + heal, max_hp)
    actual = user.now_hp - old_hp
    if actual <= 0:
        return ""
    return f"💖 **영생** 시너지: HP +{actual} 회복"


def _decrement_status_durations(entity) -> None:
    """엔티티의 모든 상태이상 지속시간 감소"""
    for status in entity.status[:]:
        if hasattr(status, 'decrement_duration'):
            status.decrement_duration()
            if hasattr(status, 'is_expired') and status.is_expired():
                entity.status.remove(status)


def _reset_all_skill_usage_counts() -> None:
    """모든 스킬의 사용 횟수 카운터 및 패시브 적용 상태 리셋 (전투 종료 시)"""
    from models.repos.static_cache import skill_cache_by_id

    for skill in skill_cache_by_id.values():
        for component in skill.components:
            if hasattr(component, 'used_count'):
                component.used_count = 0
            if hasattr(component, '_applied_entities'):
                component._applied_entities.clear()
            if hasattr(component, '_turn_counts'):
                component._turn_counts.clear()
            if hasattr(component, '_base_stats'):
                component._base_stats.clear()
