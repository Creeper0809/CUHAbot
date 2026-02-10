"""
보상 계산기 - 몬스터 타입 판별, 보상 배율, 전투 결과 처리

전투 후 경험치/골드 계산 및 드롭 처리를 담당합니다.
"""
import logging
from typing import Optional

from config import DUNGEON, DROP
from models import Monster, MonsterTypeEnum, User, UserStatEnum
from service.collection_service import CollectionService
from service.event import EventBus, GameEvent, GameEventType

logger = logging.getLogger(__name__)


# =============================================================================
# 몬스터 타입 유틸리티
# =============================================================================


def normalize_monster_type(monster: Monster) -> Optional[str]:
    monster_type = getattr(monster, "type", None)
    if isinstance(monster_type, MonsterTypeEnum):
        return monster_type.value
    return monster_type


def is_boss_monster(monster: Monster) -> bool:
    return normalize_monster_type(monster) == MonsterTypeEnum.BOSS.value


def get_monster_exp_multiplier(monster: Monster) -> float:
    monster_type = normalize_monster_type(monster)
    if monster_type == MonsterTypeEnum.ELITE.value:
        return DUNGEON.ELITE_EXP_MULTIPLIER
    if monster_type == MonsterTypeEnum.BOSS.value:
        return DUNGEON.BOSS_EXP_MULTIPLIER
    return 1.0


def get_monster_gold_multiplier(monster: Monster) -> float:
    monster_type = normalize_monster_type(monster)
    if monster_type == MonsterTypeEnum.ELITE.value:
        return DUNGEON.ELITE_GOLD_MULTIPLIER
    if monster_type == MonsterTypeEnum.BOSS.value:
        return DUNGEON.BOSS_GOLD_MULTIPLIER
    return 1.0


def get_monster_drop_multiplier(monster: Monster) -> float:
    monster_type = normalize_monster_type(monster)
    if monster_type == MonsterTypeEnum.ELITE.value:
        return DROP.ELITE_DROP_MULTIPLIER
    if monster_type == MonsterTypeEnum.BOSS.value:
        return DROP.BOSS_DROP_MULTIPLIER
    return 1.0


def get_box_pool_by_monster(monster: Monster) -> list[tuple[int, float]]:
    """몬스터 타입에 따른 상자 풀 조회 (CSV 기반)"""
    from models.repos.static_cache import get_box_pool_by_monster_type

    monster_type = normalize_monster_type(monster)
    return get_box_pool_by_monster_type(monster_type)


# =============================================================================
# 스탯 유틸리티
# =============================================================================


def get_attack_stat(entity) -> int:
    if hasattr(entity, "get_stat"):
        stat = entity.get_stat()
        return int(stat.get(UserStatEnum.ATTACK, getattr(entity, "attack", 0)))
    return getattr(entity, "attack", 0)


# =============================================================================
# 전투 결과 처리 (다중 몬스터)
# =============================================================================


async def process_combat_result_multi(session, context, turn_count: int) -> str:
    """
    전투 결과 처리 (다중 몬스터)

    Args:
        session: 던전 세션
        context: 전투 컨텍스트
        turn_count: 총 턴 수

    Returns:
        결과 메시지
    """
    from service.dungeon.drop_handler import (
        try_drop_boss_special_item, try_drop_monster_box, try_drop_monster_skill,
    )

    user = session.user

    # 패배 판정: 모든 플레이어(리더 + 난입자)가 죽었을 때
    all_players_dead = True
    if user.now_hp > 0:
        all_players_dead = False
    elif session.participants:
        for participant in session.participants.values():
            if participant.now_hp > 0:
                all_players_dead = False
                break

    if all_players_dead:
        # Phase 5: 전투 기록 저장 (패배)
        try:
            from service.combat_history.history_service import HistoryService

            monster_name = context.monsters[0].name if context.monsters else "Unknown"
            await HistoryService.record_combat(
                user_id=user.discord_id,
                dungeon_id=session.dungeon.id,
                step=session.exploration_step,
                monster_name=monster_name,
                result="defeat",
                damage=sum(session.contribution.values()) if session.contribution else 0,
                turns=turn_count,
                voice_channel_id=session.voice_channel_id
            )
            logger.debug(f"Combat history (defeat) recorded for user {user.discord_id}")
        except Exception as e:
            logger.error(f"Failed to record combat history (defeat): {e}", exc_info=True)

        return "💀 패배... 전원 전투불능"

    # 리더가 죽었으면 던전 탐험 종료 플래그 설정
    leader_died = user.now_hp <= 0
    if leader_died:
        session.pending_exit = True

    # 승리 - 각 몬스터별 보상 합산
    monster_level = session.dungeon.require_level if session.dungeon else 1
    total_exp = 0
    total_gold = 0
    result_lines = []

    # 이벤트 버스 (싱글톤)
    event_bus = EventBus()

    for monster in context.monsters:
        exp_mult = get_monster_exp_multiplier(monster)
        gold_mult = get_monster_gold_multiplier(monster)

        exp = int(DUNGEON.BASE_EXP_PER_MONSTER * (1 + monster_level / 10) * exp_mult)
        gold = int(DUNGEON.BASE_GOLD_PER_MONSTER * (1 + monster_level / 10) * gold_mult)

        total_exp += exp
        total_gold += gold

        await CollectionService.register_monster(user, monster.id)

        # 이벤트 발행: 몬스터 처치
        await event_bus.publish(GameEvent(
            type=GameEventType.MONSTER_KILLED,
            user_id=user.id,
            data={
                "monster_id": monster.id,
                "monster_name": monster.name,
                "monster_attribute": getattr(monster, "attribute", None),
                "is_boss": is_boss_monster(monster),
                "dungeon_id": session.dungeon.id if session.dungeon else None
            }
        ))

        # 드롭 시도 (각 몬스터 독립)
        for drop_msg in await _try_all_drops(session, user, monster):
            result_lines.append(f"   {drop_msg}")

    # 그룹 보너스 (2마리 이상)
    if len(context.monsters) >= 2:
        total_exp = int(total_exp * 1.2)
        total_gold = int(total_gold * 1.1)

    session.monsters_defeated += len(context.monsters)

    # 멀티플레이어 보상 분배
    if session.participants:
        from service.intervention.contribution_tracker import distribute_rewards

        participant_rewards = await distribute_rewards(session, total_exp, total_gold)

        # 각 참가자는 add_gold/add_experience 내부에서 GOLD_OBTAINED 이벤트 발행
        # 여기서는 리더만 전투 승리 이벤트 발행
        await event_bus.publish(GameEvent(
            type=GameEventType.COMBAT_WON,
            user_id=user.id,
            data={
                "is_flawless": user.now_hp == user.get_stat()[UserStatEnum.HP],
                "is_fast": turn_count <= 3,
                "turns": turn_count,
            }
        ))

        monster_names = ", ".join([m.name for m in context.monsters])
        result_msg = f"🏆 **{monster_names}** 처치! ({turn_count}턴)\n"

        # 리더 사망 경고
        if leader_died:
            result_msg += "   ⚠️ **파티 리더 전투불능! 던전 탐험이 종료됩니다.**\n"

        result_msg += (
            f"   💰 총 보상: ⭐ **{total_exp}** EXP │ 💰 **{total_gold}** G\n"
            f"   👥 기여도 비례 분배:\n"
        )

        # 참가자별 보상 표시
        for user_id, rewards in participant_rewards.items():
            participant = session.participants.get(user_id)
            if not participant:
                participant = session.user if user_id == session.user_id else None

            if participant:
                share = session.contribution.get(user_id, 0) / sum(session.contribution.values())
                result_msg += (
                    f"      - {participant.get_name()}: "
                    f"⭐ +{rewards['exp']} │ 💰 +{rewards['gold']} "
                    f"({share:.1%})\n"
                )

        # 세션 누적 (요약용)
        session.total_exp += total_exp
        session.total_gold += total_gold
    else:
        # 단일 플레이어 보상
        session.total_exp += total_exp
        session.total_gold += total_gold

        # 이벤트 발행: 골드 획득
        if total_gold > 0:
            await event_bus.publish(GameEvent(
                type=GameEventType.GOLD_OBTAINED,
                user_id=user.id,
                data={
                    "gold_amount": total_gold
                }
            ))

        # 이벤트 발행: 전투 승리
        await event_bus.publish(GameEvent(
            type=GameEventType.COMBAT_WON,
            user_id=user.id,
            data={
                "is_flawless": user.now_hp == user.get_stat()[UserStatEnum.HP],
                "is_fast": turn_count <= 3,
                "turns": turn_count,
            }
        ))

        monster_names = ", ".join([m.name for m in context.monsters])
        result_msg = (
            f"🏆 **{monster_names}** 처치! ({turn_count}턴)\n"
            f"   ⭐ +**{total_exp}** EXP │ 💰 +**{total_gold}** G"
        )

    if result_lines:
        result_msg += "\n" + "\n".join(result_lines)

    # Phase 5: 전투 기록 저장 (환영 시스템)
    try:
        from service.combat_history.history_service import HistoryService

        monster_name = context.monsters[0].name if context.monsters else "Unknown"
        await HistoryService.record_combat(
            user_id=user.discord_id,
            dungeon_id=session.dungeon.id,
            step=session.exploration_step,
            monster_name=monster_name,
            result="victory",
            damage=sum(session.contribution.values()) if session.contribution else 0,
            turns=turn_count,
            voice_channel_id=session.voice_channel_id
        )
        logger.debug(f"Combat history recorded for user {user.discord_id}")
    except Exception as e:
        logger.error(f"Failed to record combat history: {e}", exc_info=True)

    # Phase 5: 채널 경험치 추가
    if session.voice_channel_id:
        try:
            from service.voice_channel.channel_level_service import ChannelLevelService
            from service.session import get_sessions_in_voice_channel

            # 채널 경험치 추가 (기본 10 EXP)
            total_damage = sum(session.contribution.values()) if session.contribution else 0
            result = await ChannelLevelService.add_channel_exp(
                voice_channel_id=session.voice_channel_id,
                exp=10,
                user_id=user.discord_id,
                damage=total_damage
            )

            # 레벨업 시 같은 채널 전체에 DM 알림
            if result["leveled_up"]:
                other_sessions = get_sessions_in_voice_channel(session.voice_channel_id)
                for other_session in other_sessions:
                    try:
                        # DM 전송
                        from bot import bot
                        other_user = await bot.fetch_user(other_session.user_id)
                        await other_user.send(
                            f"🎉 음성 채널이 레벨 **{result['new_level']}**에 도달했습니다!\n"
                            f"💎 채널 보너스: +{(result['new_level'] - 1) * 5}% 보상"
                        )
                        logger.info(f"Sent level-up notification to user {other_session.user_id}")
                    except Exception:
                        pass  # DM 전송 실패 무시

            logger.debug(f"Channel exp added for channel {session.voice_channel_id}")
        except Exception as e:
            logger.error(f"Failed to add channel exp: {e}", exc_info=True)

    return result_msg


async def _try_all_drops(session, user: User, monster: Monster) -> list[str]:
    """모든 드롭 시도 후 메시지 리스트 반환"""
    from service.dungeon.drop_handler import (
        try_drop_boss_special_item, try_drop_monster_box, try_drop_monster_skill,
        try_drop_monster_material,
    )

    drops = []

    # 보스 전용 아이템
    boss_item = await try_drop_boss_special_item(user, monster)
    if boss_item:
        drops.append(boss_item)

    # 일반 재료 드롭 (일반 몬스터)
    material = await try_drop_monster_material(user, monster)
    if material:
        drops.append(material)

    # 상자 드롭
    chest = await try_drop_monster_box(session, monster)
    if chest:
        drops.append(chest)

    # 스킬 드롭
    skill = await try_drop_monster_skill(user, monster)
    if skill:
        drops.append(skill)

    return drops
