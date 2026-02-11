"""
멀티유저 만남 이벤트 발생 조건 체크 (Phase 3 + 4)

exploration_step 증가 시점에 교차로 만남, 캠프파이어,
동시 조우, 보스방 대기실, 위기 목격 이벤트 발생 여부를 결정합니다.
"""
import logging
import random
from typing import TYPE_CHECKING, Optional

from config.social_encounter import SOCIAL_ENCOUNTER
from service.session import get_sessions_in_voice_channel
from service.voice_channel.proximity_calculator import ProximityCalculator

if TYPE_CHECKING:
    from service.session import DungeonSession

logger = logging.getLogger(__name__)


def check_social_encounter(session: "DungeonSession") -> Optional[str]:
    """
    멀티유저 encounter 발생 조건 체크

    교차로 만남 또는 캠프파이어 이벤트 발생 여부를 결정합니다.
    교차로 만남(±2 스텝, 20%)을 먼저 체크하고,
    조건 미충족 시 캠프파이어(±10 스텝, 25%)를 체크합니다.

    Args:
        session: 현재 탐험 중인 DungeonSession

    Returns:
        발생한 이벤트 타입 ("crossroads" or "campfire") 또는 None
    """
    # Guard: 음성 채널 없음
    if not session.voice_channel_id:
        logger.debug(f"User {session.user_id} not in voice channel, skipping social encounter")
        return None

    # Guard: 쿨타임 체크
    steps_since_last = session.exploration_step - session.encounter_event_cooldown
    if steps_since_last < SOCIAL_ENCOUNTER.ENCOUNTER_EVENT_COOLDOWN:
        logger.debug(
            f"User {session.user_id} social encounter on cooldown "
            f"({steps_since_last}/{SOCIAL_ENCOUNTER.ENCOUNTER_EVENT_COOLDOWN} steps)"
        )
        return None

    # Guard: 이미 진행 중인 이벤트
    if session.active_encounter_event:
        logger.debug(f"User {session.user_id} already has active encounter event")
        return None

    # 같은 음성 채널의 다른 세션 조회
    other_sessions = get_sessions_in_voice_channel(session.voice_channel_id)

    # 필터: 같은 던전 + 비전투 + 비종료 + 본인 제외
    eligible = [
        s for s in other_sessions
        if s.user_id != session.user_id
        and s.dungeon
        and s.dungeon.id == session.dungeon.id
        and not s.in_combat
        and not s.ended
    ]

    if not eligible:
        logger.debug(f"No eligible partners for user {session.user_id}")
        return None

    # 1. 교차로 만남 우선 체크 (±2 스텝)
    nearby_sessions = get_nearby_sessions(
        session, eligible, SOCIAL_ENCOUNTER.CROSSROADS_DISTANCE_THRESHOLD
    )
    if nearby_sessions and random.random() < SOCIAL_ENCOUNTER.CROSSROADS_PROBABILITY:
        logger.info(
            f"Crossroads encounter triggered for user {session.user_id}, "
            f"{len(nearby_sessions)} nearby players"
        )
        return "crossroads"

    # 2. 캠프파이어 체크
    if random.random() < SOCIAL_ENCOUNTER.CAMPFIRE_PROBABILITY:
        logger.info(
            f"Campfire encounter triggered for user {session.user_id}, "
            f"{len(eligible)} players in channel"
        )
        return "campfire"

    return None


def get_nearby_sessions(
    session: "DungeonSession",
    candidate_sessions: list["DungeonSession"],
    distance_threshold: int,
) -> list["DungeonSession"]:
    """
    거리 제한 내의 세션 필터링

    Args:
        session: 기준 세션
        candidate_sessions: 후보 세션 목록
        distance_threshold: 최대 거리 (절댓값)

    Returns:
        거리 제한 내의 세션 목록
    """
    nearby = []
    for other_session in candidate_sessions:
        distance = ProximityCalculator.calculate_distance(
            session.exploration_step, other_session.exploration_step
        )
        if distance <= distance_threshold:
            nearby.append(other_session)

    return nearby


# Phase 4: 고급 만남 이벤트 체커 함수들


def check_simultaneous_encounter(session: "DungeonSession") -> Optional["DungeonSession"]:
    """
    동시 조우 체크 (Phase 4)

    같은 스텝에서 전투를 시작한 다른 플레이어를 찾습니다.
    조건: 같은 VC + 같은 던전 + 정확히 같은 스텝 + 5초 이내 전투 시작

    Args:
        session: 현재 세션 (방금 전투 시작)

    Returns:
        동시 전투 시작한 파트너 세션 또는 None
    """
    # Guard: 음성 채널 없음
    if not session.voice_channel_id:
        logger.debug(f"User {session.user_id} not in voice channel, skipping simultaneous encounter")
        return None

    # Guard: 쿨타임
    steps_since_last = session.exploration_step - session.encounter_event_cooldown
    if steps_since_last < SOCIAL_ENCOUNTER.ENCOUNTER_EVENT_COOLDOWN:
        logger.debug(
            f"User {session.user_id} encounter event on cooldown "
            f"({steps_since_last}/{SOCIAL_ENCOUNTER.ENCOUNTER_EVENT_COOLDOWN} steps)"
        )
        return None

    # Guard: 이미 진행 중인 이벤트
    if session.active_encounter_event:
        logger.debug(f"User {session.user_id} already has active encounter event")
        return None

    # 같은 음성 채널의 다른 세션 조회
    other_sessions = get_sessions_in_voice_channel(session.voice_channel_id)

    # 필터: 같은 던전 + 정확히 같은 스텝 + 전투 중 + 5초 이내 시작
    import asyncio

    current_time = asyncio.get_event_loop().time()
    eligible = []

    for s in other_sessions:
        if s.user_id == session.user_id:
            continue
        if not s.dungeon or s.dungeon.id != session.dungeon.id:
            continue
        if s.exploration_step != session.exploration_step:
            continue
        if not s.in_combat:
            continue
        if not s.combat_context:
            continue
        if s.active_encounter_event:
            continue

        # 전투 시작 시간 체크 (5초 이내)
        combat_start_time = getattr(s.combat_context, "created_at", 0)
        if current_time - combat_start_time > 5.0:
            continue

        eligible.append(s)

    if not eligible:
        logger.debug(f"No simultaneous combat partners found for user {session.user_id}")
        return None

    # 20% 확률로 발생
    if random.random() < SOCIAL_ENCOUNTER.SIMULTANEOUS_ENCOUNTER_PROBABILITY:
        partner = eligible[0]
        logger.info(
            f"Simultaneous encounter triggered: user={session.user_id}, "
            f"partner={partner.user_id}, step={session.exploration_step}"
        )
        return partner

    return None


def check_boss_waiting_room(dungeon_id: int, progress: float) -> bool:
    """
    보스방 대기실 발생 조건 체크 (Phase 4)

    보스 스폰 조건 충족 시 대기실 모드로 전환할지 결정합니다.
    조건: 진행도 ≥90% + 보스 스폰 성공 + 15% 확률

    Args:
        dungeon_id: 던전 ID
        progress: 진행도 (0.0~1.0)

    Returns:
        보스방 대기실 발생 여부
    """
    from config.dungeon import DUNGEON

    # Guard: 진행도 미달
    if progress < DUNGEON.BOSS_SPAWN_PROGRESS_THRESHOLD:
        return False

    # 보스 스폰 롤 (기존 로직과 동일)
    if random.random() >= DUNGEON.BOSS_SPAWN_RATE_AT_END:
        return False

    # 15% 확률로 대기실 모드
    if random.random() < SOCIAL_ENCOUNTER.BOSS_WAITING_ROOM_PROBABILITY:
        logger.info(f"Boss waiting room triggered for dungeon {dungeon_id} at {progress:.1%} progress")
        return True

    return False


def check_crisis_witness(session: "DungeonSession") -> bool:
    """
    위기 목격 발생 조건 체크 (Phase 4)

    전투 중 플레이어 HP가 30% 미만일 때 근처 플레이어에게 알림을 보냅니다.
    조건: 음성 채널 + 전투 중 + HP < 30% + 근처 플레이어 존재 + 전투당 1회

    Args:
        session: 현재 세션 (전투 중)

    Returns:
        위기 목격 이벤트 발생 여부
    """
    # Guard: 음성 채널 없음
    if not session.voice_channel_id:
        return False

    # Guard: 전투 중 아님
    if not session.in_combat:
        return False

    # Guard: 이미 전송됨 (전투당 1회 제한)
    if hasattr(session, "crisis_event_sent") and session.crisis_event_sent:
        return False

    # Guard: HP 체크
    user = session.user
    hp_percent = user.now_hp / user.max_hp if user.max_hp > 0 else 1.0

    if hp_percent >= SOCIAL_ENCOUNTER.CRISIS_HP_THRESHOLD:
        return False

    # 근처 플레이어 찾기 (±2 스텝)
    other_sessions = get_sessions_in_voice_channel(session.voice_channel_id)

    eligible = [
        s
        for s in other_sessions
        if s.user_id != session.user_id
        and s.dungeon
        and s.dungeon.id == session.dungeon.id
        and not s.in_combat
        and not s.ended
    ]

    nearby = get_nearby_sessions(session, eligible, 2)

    if not nearby:
        logger.debug(f"No nearby players for crisis witness: user={session.user_id}")
        return False

    # 10% 확률로 발생
    if random.random() < SOCIAL_ENCOUNTER.CRISIS_WITNESS_PROBABILITY:
        logger.info(
            f"Crisis witness triggered: victim={session.user_id}, "
            f"hp={hp_percent:.1%}, nearby_count={len(nearby)}"
        )
        return True

    return False
