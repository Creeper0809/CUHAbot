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
        context.initialize_gauges(user)
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
        action_logs = _execute_entity_action(user, actor, context)
        for log in action_logs:
            combat_log.append(log)

        context.consume_gauge(actor)
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
        target = context.get_primary_monster()
        damage = get_attack_stat(user)
        target.take_damage(damage)
        logs.append(f"⚔️ **{user.get_name()}** 기본 공격 → **{target.get_name()}** {damage} 데미지")

    return logs


def _execute_monster_action(monster: Monster, user: User) -> list[str]:
    """몬스터 행동"""
    from service.dungeon.reward_calculator import get_attack_stat

    logs = []
    monster_skill = monster.next_skill()

    if monster_skill:
        log = monster_skill.on_turn(monster, user)
        if log and log.strip():
            logs.append(log)
    else:
        damage = get_attack_stat(monster)
        user.take_damage(damage)
        logs.append(f"⚔️ **{monster.get_name()}** 기본 공격 → **{user.get_name()}** {damage} 데미지")

    return logs


# =============================================================================
# 유틸리티
# =============================================================================


def _is_skill_aoe(skill) -> bool:
    """스킬이 AOE(전체 공격)인지 확인"""
    if not skill:
        return False
    for component in skill.components:
        if hasattr(component, 'is_aoe') and component.is_aoe:
            return True
    return False


def _decrement_status_durations(entity) -> None:
    """엔티티의 모든 상태이상 지속시간 감소"""
    for status in entity.status[:]:
        if hasattr(status, 'decrement_duration'):
            status.decrement_duration()
            if hasattr(status, 'is_expired') and status.is_expired():
                entity.status.remove(status)


def _reset_all_skill_usage_counts() -> None:
    """모든 스킬의 사용 횟수 카운터 리셋 (전투 종료 시)"""
    from models.repos.static_cache import skill_cache_by_id

    for skill in skill_cache_by_id.values():
        for component in skill.components:
            if hasattr(component, 'used_count'):
                component.used_count = 0
