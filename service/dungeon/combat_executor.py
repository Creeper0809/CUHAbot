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


def _all_players_dead(user: User, session) -> bool:
    """
    모든 플레이어(리더 + 난입자)가 죽었는지 확인

    Args:
        user: 리더 유저
        session: 던전 세션

    Returns:
        모두 죽었으면 True, 한 명이라도 살아있으면 False
    """
    # 리더가 살아있으면 False
    if user.now_hp > 0:
        return False

    # 난입자 중 한 명이라도 살아있으면 False
    if session and session.participants:
        for participant in session.participants.values():
            if participant.now_hp > 0:
                return False

    # 모두 죽음
    return True


async def _update_all_combat_messages(
    session,
    combat_message: discord.Message,
    user: User,
    context: CombatContext,
    combat_log: deque[str]
) -> None:
    """
    모든 참가자의 전투 UI 메시지 업데이트 (리더 + 난입자)

    Args:
        session: 던전 세션
        combat_message: 리더의 전투 메시지
        user: 리더 유저
        context: 전투 컨텍스트
        combat_log: 전투 로그
    """
    from service.dungeon.dungeon_ui import create_battle_embed_multi

    embed = create_battle_embed_multi(user, context, combat_log, session.participants)

    # 리더 메시지 업데이트
    await combat_message.edit(embed=embed)

    # 참가자 메시지 업데이트
    for participant_msg in session.participant_combat_messages.values():
        try:
            await participant_msg.edit(embed=embed)
        except Exception as e:
            logger.error(f"Failed to update participant combat UI: {e}")


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
    session.discord_client = interaction.client  # Discord client 저장 (난입자 UI 전송용)

    logger.info(
        f"Combat started: user={user.discord_id}, "
        f"monsters={[m.name for m in context.monsters]}"
    )

    set_combat_state(user.discord_id, True)

    # 전투 알림 게시 (관전 시스템)
    try:
        from service.spectator.spectator_service import SpectatorService
        notification_msg = await SpectatorService.post_combat_notification(session, interaction.channel)
        session.combat_notification_message = notification_msg
    except Exception as e:
        logger.error(f"Failed to post combat notification: {e}")

    try:
        # 전투 UI 생성
        embed = create_battle_embed_multi(user, context, context.combat_log, session.participants)

        # 리더에게 전투 UI 전송
        combat_message = await interaction.user.send(embed=embed)

        # 난입 참가자들에게도 전투 UI 전송
        session.participant_combat_messages.clear()
        for participant_id, participant in session.participants.items():
            try:
                discord_user = await interaction.client.fetch_user(participant.discord_id)
                participant_msg = await discord_user.send(embed=embed)
                session.participant_combat_messages[participant_id] = participant_msg
                logger.info(f"Combat UI sent to participant: {participant.discord_id}")
            except Exception as e:
                logger.error(f"Failed to send combat UI to participant {participant_id}: {e}")

        turn_count = 1

        # 전투 루프: 플레이어 전원 사망 또는 몬스터 전원 사망까지 계속
        while not _all_players_dead(user, session) and not context.is_all_dead():
            combat_ended = await _process_turn_multi(
                session, user, context, turn_count, context.combat_log, combat_message
            )
            if combat_ended:
                break
            turn_count += 1

        # 최종 전투 결과 UI 업데이트 (리더 + 참가자들)
        final_embed = create_battle_embed_multi(user, context, context.combat_log, session.participants)
        await combat_message.edit(embed=final_embed)
        for participant_msg in session.participant_combat_messages.values():
            try:
                await participant_msg.edit(embed=final_embed)
            except Exception as e:
                logger.error(f"Failed to update participant combat message: {e}")

        await asyncio.sleep(COMBAT.COMBAT_END_DELAY)

        # 전투 메시지 삭제 (리더 + 참가자들)
        await combat_message.delete()
        for participant_msg in session.participant_combat_messages.values():
            try:
                await participant_msg.delete()
            except Exception as e:
                logger.error(f"Failed to delete participant combat message: {e}")

        return await process_combat_result_multi(session, context, turn_count)

    finally:
        set_combat_state(user.discord_id, False)
        session.combat_context = None

        # 참가자 전투 메시지 정리
        session.participant_combat_messages.clear()

        # 관전자 및 전투 알림 메시지 정리 (전투 종료 시 항상 실행)
        if session.spectators or session.combat_notification_message:
            try:
                from service.spectator.spectator_service import SpectatorService
                await SpectatorService.cleanup_spectators(session)
            except Exception as e:
                logger.error(f"Failed to cleanup spectators in finally: {e}")

        _reset_all_skill_usage_counts()
        _reset_equipment_component_caches(user)


# =============================================================================
# 턴 처리 (행동 게이지 시스템)
# =============================================================================


async def _process_turn_multi(
    session,
    user: User,
    context: CombatContext,
    turn_count: int,
    combat_log: deque[str],
    combat_message: discord.Message
) -> bool:
    """
    턴 처리 (1:N 지원) - 행동 게이지 시스템

    Args:
        session: 던전 세션 (멀티플레이어 지원)
        user: 유저
        context: 전투 컨텍스트
        turn_count: 턴 수
        combat_log: 전투 로그
        combat_message: 전투 메시지

    Returns:
        전투 종료 여부
    """
    from service.dungeon.dungeon_ui import create_battle_embed_multi

    # 게이지 초기화 (첫 호출 시)
    if not context.action_gauges:
        context.user = user
        context.initialize_gauges(user)
        # 장비 컴포넌트 캐싱 (스킬 데미지 강화용)
        from service.dungeon.equipment_skill_modifier import cache_equipment_components
        try:
            await cache_equipment_components(user)
        except Exception as e:
            logger.warning(f"Failed to cache equipment components: {e}")
        # 시너지: 선공 확정
        if has_first_strike(user):
            context.action_gauges[id(user)] = COMBAT.ACTION_GAUGE_MAX
            combat_log.append("💨 **선공 확정** 시너지 발동!")
        # 패시브 발동 로그
        passive_logs = _apply_combat_start_passives(user, context)
        for log in passive_logs:
            combat_log.append(log)
        # 필드 효과 발동 메시지
        if context.field_effect:
            combat_log.append(f"━━━ {context.field_effect.get_display_text()} 발동! ━━━")
            combat_log.append(f"💬 {context.field_effect.data.description}")
        combat_log.append(f"━━━ ⚔️ **전투 시작 - 라운드 {context.round_number}** ━━━")
        # 필드 효과: 1라운드 시작 시 즉시 처리
        if context.field_effect:
            # 모든 플레이어 수집 (리더 + 난입자)
            all_players = [user]
            if session and session.participants:
                all_players.extend(session.participants.values())
            field_logs = context.field_effect.on_round_start(all_players, context.get_all_alive_monsters())
            for log in field_logs:
                combat_log.append(log)

    while context.action_count < COMBAT.MAX_ACTIONS_PER_LOOP:
        if context.is_all_dead() or _all_players_dead(user, session):
            return True

        actor = context.get_next_actor(user, session.participants)
        if not actor:
            context.fill_gauges(user, session.participants)
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
            # 행동하지 못할 때는 지속시간 감소하지 않음 (행동 후에만 감소)
            await _update_all_combat_messages(session, combat_message, user, context, combat_log)
            await asyncio.sleep(COMBAT.TURN_PHASE_DELAY)

            if context.check_and_advance_round():
                combat_log.append(f"━━━ 🌟 **라운드 {context.round_number}** ━━━")
                await _update_all_combat_messages(session, combat_message, user, context, combat_log)
            continue

        # 행동 실행
        alive_before = {id(m) for m in context.get_all_alive_monsters()}
        action_logs = _execute_entity_action(session, user, actor, context)
        for log in action_logs:
            combat_log.append(log)

        # 신규: 기여도 기록 (파티 리더 + 난입자)
        if isinstance(actor, User):
            from service.intervention.contribution_tracker import record_contribution
            # 로그에서 데미지/치유량 추출
            damage, healing = _parse_combat_metrics_from_logs(action_logs)
            record_contribution(session, actor, damage=damage, healing=healing)

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

        # 필드 효과: 턴 종료 시 처리
        if context.field_effect:
            field_logs = context.field_effect.on_turn_end(actor)
            for log in field_logs:
                combat_log.append(log)

        _decrement_status_durations(actor)

        await _update_all_combat_messages(session, combat_message, user, context, combat_log)

        # 관전자 업데이트
        from service.spectator.spectator_service import SpectatorService
        if session:
            await SpectatorService.update_all_spectators(session)

        await asyncio.sleep(COMBAT.TURN_PHASE_DELAY)

        if context.check_and_advance_round():
            combat_log.append(f"━━━ 🌟 **라운드 {context.round_number}** ━━━")

            # 신규: 난입자 처리
            from service.intervention.intervention_service import InterventionService
            intervention_logs = await InterventionService.process_pending_interventions(session, context)
            for log in intervention_logs:
                combat_log.append(log)

            # 새로 추가된 난입자들에게 전투 UI 전송
            if intervention_logs:
                from service.dungeon.dungeon_ui import create_battle_embed_multi
                for participant_id, participant in session.participants.items():
                    # 이미 UI를 받은 참가자는 건너뛰기
                    if participant_id in session.participant_combat_messages:
                        continue
                    try:
                        discord_user = await session.discord_client.fetch_user(participant.discord_id)
                        embed = create_battle_embed_multi(user, context, combat_log, session.participants)
                        participant_msg = await discord_user.send(embed=embed)
                        session.participant_combat_messages[participant_id] = participant_msg
                        logger.info(f"Combat UI sent to new intervener: {participant.discord_id}")
                    except Exception as e:
                        logger.error(f"Failed to send combat UI to intervener {participant_id}: {e}")

            # 필드 효과: 라운드 시작 시 처리
            if context.field_effect:
                # 모든 플레이어 수집 (리더 + 난입자)
                all_players = [user]
                if session and session.participants:
                    all_players.extend(session.participants.values())
                field_logs = context.field_effect.on_round_start(all_players, context.get_all_alive_monsters())
                for log in field_logs:
                    combat_log.append(log)
            await _update_all_combat_messages(session, combat_message, user, context, combat_log)

        if _all_players_dead(user, session) or context.is_all_dead():
            return True

    logger.warning(f"Combat reached max actions: {COMBAT.MAX_ACTIONS_PER_LOOP}")
    return True


# =============================================================================
# 엔티티 행동
# =============================================================================


def _execute_entity_action(
    session,
    user: User,
    actor: Union[User, Monster],
    context: CombatContext
) -> list[str]:
    """엔티티의 행동 실행"""
    from models.users import User as UserClass
    from service.dungeon.reward_calculator import get_attack_stat

    if isinstance(actor, UserClass):
        return _execute_user_action(actor, context)
    return _execute_monster_action(monster=actor, user=user, context=context, session=session)


def _execute_user_action(user: User, context: CombatContext) -> list[str]:
    """유저 행동"""
    import random
    from service.dungeon.reward_calculator import get_attack_stat

    logs = []
    user_skill = user.next_skill()

    # 랜덤으로 몬스터 선택 (살아있는 몬스터 중)
    alive_monsters = context.get_all_alive_monsters()
    if not alive_monsters:
        return []
    target = random.choice(alive_monsters)

    # 턴 시작 시 장비 효과 (행동 예측 등)
    turn_start_logs = _apply_equipment_turn_start(user, target)
    logs.extend(turn_start_logs)

    if user_skill:
        if _is_skill_aoe(user_skill):
            for monster in alive_monsters:
                log = user_skill.on_turn(user, monster)
                if log and log.strip():
                    logs.append(log)
                # 공격 후 장비 훅 (추가 공격, 회복 봉인 등)
                attack_logs = _apply_equipment_on_attack(user, monster, 0)  # TODO: 실제 데미지 전달
                logs.extend(attack_logs)
        else:
            log = user_skill.on_turn(user, target)
            if log and log.strip():
                logs.append(log)
            # 공격 후 장비 훅
            attack_logs = _apply_equipment_on_attack(user, target, 0)  # TODO: 실제 데미지 전달
            logs.extend(attack_logs)
    else:
        from service.dungeon.damage_pipeline import process_incoming_damage
        damage = get_attack_stat(user)
        event = process_incoming_damage(target, damage, attacker=user)
        logs.extend(event.extra_logs)
        logs.append(f"⚔️ **{user.get_name()}** 기본 공격 → **{target.get_name()}** {event.actual_damage} 데미지")

        # 공격 후 장비 훅 (반격, 추가 공격 등)
        attack_logs = _apply_equipment_on_attack(user, target, event.actual_damage)
        logs.extend(attack_logs)

        if event.reflected_damage > 0:
            reflect_event = process_incoming_damage(user, event.reflected_damage, is_reflected=True)
            logs.append(f"   🔄 반사 데미지 → **{user.get_name()}** {reflect_event.actual_damage}")

    return logs


def _execute_monster_action(monster: Monster, user: User, context: CombatContext, session) -> list[str]:
    """몬스터 행동 (멀티플레이어 대응)"""
    import random
    from service.dungeon.reward_calculator import get_attack_stat
    from service.dungeon.damage_pipeline import process_incoming_damage

    logs = []

    # 공격 대상 선택 (리더 + 난입자 중 생존자)
    alive_players = [user] if user.now_hp > 0 else []

    # 세션에서 난입자 가져오기
    if session and session.participants:
        for participant in session.participants.values():
            if participant.now_hp > 0:
                alive_players.append(participant)

    # 랜덤으로 대상 선택
    if not alive_players:
        # 모두 죽었으면 그냥 user 사용 (어차피 전투 종료됨)
        target = user
    else:
        target = random.choice(alive_players)

    monster_skill = monster.next_skill()

    if monster_skill:
        log = monster_skill.on_turn(monster, target)
        if log and log.strip():
            logs.append(log)
        # 유저 피격 시 장비 훅 (가시 피해, 반격 등)
        damaged_logs = _apply_equipment_on_damaged(target, monster, 0)  # TODO: 실제 데미지 전달
        logs.extend(damaged_logs)
    else:
        damage = get_attack_stat(monster)
        event = process_incoming_damage(target, damage, attacker=monster)
        logs.extend(event.extra_logs)
        logs.append(f"⚔️ **{monster.get_name()}** 기본 공격 → **{target.get_name()}** {event.actual_damage} 데미지")

        # 유저 피격 시 장비 훅
        damaged_logs = _apply_equipment_on_damaged(target, monster, event.actual_damage)
        logs.extend(damaged_logs)

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

    # 패시브 컴포넌트 싱글톤 버그 방지: 전투 시작 시 모든 _applied_entities 초기화
    for entity in entities:
        skill_ids = getattr(entity, 'equipped_skill', None) or getattr(entity, 'use_skill', [])
        for sid in skill_ids:
            if sid == 0:
                continue
            skill = get_skill_by_id(sid)
            if skill:
                for comp in skill.components:
                    if hasattr(comp, '_applied_entities'):
                        comp._applied_entities.clear()

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

    # 장비 컴포넌트 전투 시작 훅 호출
    equipment_logs = _apply_equipment_combat_start(user, context)
    logs.extend(equipment_logs)

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

    # 장비 패시브 효과 처리
    equipment_logs = _apply_equipment_passives(actor)
    logs.extend(equipment_logs)

    return logs


def _check_death_triggers(
    context: CombatContext,
    alive_before: set[int],
    killer: User,
) -> list[str]:
    """사망한 몬스터의 on_death 컴포넌트 트리거 + 유저 장비 부활 효과"""
    from models.repos.skill_repo import get_skill_by_id

    logs = []

    # 몬스터 on_death 트리거
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

    # 유저 사망 시 장비 부활 효과 (revive 컴포넌트)
    if killer.now_hp <= 0:
        equipment_components = _get_equipment_components_sync(killer)
        for comp in equipment_components:
            tag = getattr(comp, '_tag', '')
            if tag == "revive" and hasattr(comp, 'on_death'):
                log = comp.on_death(killer, None)
                if log and log.strip():
                    logs.append(log)
                    # 부활했으면 다른 부활 컴포넌트는 실행 안함
                    if killer.now_hp > 0:
                        break

    return logs


def _is_skill_aoe(skill) -> bool:
    """스킬이 AOE(전체 공격)인지 확인"""
    if not skill:
        return False
    for component in skill.components:
        if hasattr(component, 'is_aoe') and component.is_aoe:
            return True
    return False


def _parse_combat_metrics_from_logs(logs: list[str]) -> tuple[int, int]:
    """
    전투 로그에서 데미지와 치유량을 추출

    로그 패턴:
    - 공격: "⚔️ **공격자** 「스킬명」 → **대상** 150💥..."
    - 치유: "💚 **치유자** 「스킬명」 → **+100** HP"
    - 흡혈: "   💚 흡혈: +50 HP"

    Args:
        logs: 행동 로그 리스트

    Returns:
        (총 데미지, 총 치유량)
    """
    import re

    total_damage = 0
    total_healing = 0

    for log in logs:
        # 공격 데미지 파싱: "→ **대상** 150💥" 또는 "→ **대상** 150"
        # 패턴: "→ **대상** 숫자"에서 숫자 추출
        damage_match = re.search(r'→\s+\*\*[^*]+\*\*\s+(\d+)', log)
        if damage_match and '⚔️' in log:
            damage = int(damage_match.group(1))
            total_damage += damage
            continue

        # 치유량 파싱: "→ **+100** HP" 또는 "흡혈: +50 HP"
        # 패턴: "+숫자 HP" 또는 "**+숫자** HP" (별표는 옵션)
        healing_match = re.search(r'\*?\*?\+(\d+)\*?\*?\s*HP', log)
        if healing_match and ('💚' in log or 'HP' in log):
            healing = int(healing_match.group(1))
            total_healing += healing
            continue

        # 반사 데미지는 제외 (🔄가 있으면 스킵)
        if '🔄' in log:
            continue

    return total_damage, total_healing


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


# =============================================================================
# 장비 컴포넌트 통합
# =============================================================================


def _get_equipment_components_sync(entity) -> list:
    """
    엔티티의 장비 컴포넌트 가져오기 (캐시 사용)

    Args:
        entity: User 또는 Monster

    Returns:
        컴포넌트 리스트
    """
    # 유저만 장비 착용
    from models.users import User as UserClass
    if not isinstance(entity, UserClass):
        return []

    # 캐시에서 가져오기
    if hasattr(entity, '_equipment_components_cache'):
        return entity._equipment_components_cache

    return []


def _apply_equipment_combat_start(user: User, context: CombatContext) -> list[str]:
    """
    전투 시작 시 장비 컴포넌트의 on_combat_start() 호출

    Args:
        user: 유저 엔티티
        context: 전투 컨텍스트

    Returns:
        로그 메시지 리스트
    """
    logs = []
    components = _get_equipment_components_sync(user)

    for comp in components:
        if hasattr(comp, 'on_combat_start'):
            # 대상은 첫 번째 몬스터 (없으면 None)
            target = context.get_primary_monster() if context.monsters else None
            log = comp.on_combat_start(user, target)
            if log and log.strip():
                logs.append(log)

    return logs


def _apply_equipment_turn_start(entity, target=None) -> list[str]:
    """
    턴 시작 시 장비 컴포넌트의 on_turn_start() 호출

    Args:
        entity: 행동하는 엔티티
        target: 대상 엔티티

    Returns:
        로그 메시지 리스트
    """
    logs = []
    components = _get_equipment_components_sync(entity)

    for comp in components:
        if hasattr(comp, 'on_turn_start'):
            log = comp.on_turn_start(entity, target)
            if log and log.strip():
                logs.append(log)

    return logs


def _apply_equipment_on_attack(attacker, target, damage: int) -> list[str]:
    """
    공격 후 장비 컴포넌트의 on_attack() 호출

    Args:
        attacker: 공격자
        target: 대상
        damage: 가한 피해량

    Returns:
        로그 메시지 리스트
    """
    logs = []
    components = _get_equipment_components_sync(attacker)

    for comp in components:
        if hasattr(comp, 'on_attack'):
            log = comp.on_attack(attacker, target, damage)
            if log and log.strip():
                logs.append(log)

    return logs


def _apply_equipment_on_damaged(defender, attacker, damage: int) -> list[str]:
    """
    피격 시 장비 컴포넌트의 on_damaged() 호출

    Args:
        defender: 방어자
        attacker: 공격자
        damage: 받은 피해량

    Returns:
        로그 메시지 리스트
    """
    logs = []
    components = _get_equipment_components_sync(defender)

    for comp in components:
        if hasattr(comp, 'on_damaged'):
            log = comp.on_damaged(defender, attacker, damage)
            if log and log.strip():
                logs.append(log)

    return logs


def _apply_equipment_passives(actor) -> list[str]:
    """
    턴마다 장비 패시브 효과 처리 (재생, 성장 등)

    Args:
        actor: 행동하는 엔티티

    Returns:
        로그 메시지 리스트
    """
    logs = []
    components = _get_equipment_components_sync(actor)

    for comp in components:
        tag = getattr(comp, '_tag', '')
        log = ""

        # 재생 효과
        if tag == "regeneration" and hasattr(comp, 'on_turn_start'):
            log = comp.on_turn_start(actor, None)

        # 전투 성장 효과
        elif tag == "combat_stat_growth" and hasattr(comp, 'on_turn_start'):
            log = comp.on_turn_start(actor, None)

        # 조건부 스탯 보너스
        elif tag == "conditional_stat_bonus" and hasattr(comp, 'on_turn_start'):
            log = comp.on_turn_start(actor, None)

        # 주기적 무적
        elif tag == "periodic_invincibility" and hasattr(comp, 'on_turn_start'):
            log = comp.on_turn_start(actor, None)

        # 아군 보호
        elif tag == "ally_protection" and hasattr(comp, 'on_turn_start'):
            log = comp.on_turn_start(actor, None)

        if log and log.strip():
            logs.append(log)

    return logs


def _reset_equipment_component_caches(user: User) -> None:
    """
    장비 컴포넌트 캐시 및 상태 리셋 (전투 종료 시)

    Args:
        user: 유저 엔티티
    """
    components = _get_equipment_components_sync(user)

    for comp in components:
        # 사용 횟수 리셋
        if hasattr(comp, 'used_count'):
            comp.used_count = 0

        # 적용 대상 리셋
        if hasattr(comp, '_applied_entities'):
            comp._applied_entities.clear()

        # 턴 카운트 리셋
        if hasattr(comp, '_turn_count'):
            comp._turn_count = 0
        if hasattr(comp, '_turn_counts'):
            comp._turn_counts.clear()

        # 이연 피해 리셋
        if hasattr(comp, '_delayed_damage'):
            comp._delayed_damage = 0

        # 무적 상태 리셋
        if hasattr(comp, '_invincible_remaining'):
            comp._invincible_remaining = 0

        # 부활 횟수 리셋
        if hasattr(comp, '_revives_used'):
            comp._revives_used = 0

        # 연쇄 공격 리셋
        if hasattr(comp, '_chain_count'):
            comp._chain_count = 0

        # 예측 상태 리셋
        if hasattr(comp, '_predicted_this_turn'):
            comp._predicted_this_turn = False

        # 보호 상태 리셋
        if hasattr(comp, '_is_protecting'):
            comp._is_protecting = False
        if hasattr(comp, '_taunt_remaining'):
            comp._taunt_remaining = 0

    # 캐시 자체도 제거
    if hasattr(user, '_equipment_components_cache'):
        delattr(user, '_equipment_components_cache')
