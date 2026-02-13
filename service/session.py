"""
세션 관리 모듈

던전 탐험 세션의 생성, 조회, 종료 및 상태 관리를 담당합니다.
"""
import asyncio
import logging
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from models import Dungeon, User
    from discord import Message
    from service.dungeon.combat_context import CombatContext

logger = logging.getLogger(__name__)

# 세션 생성/삭제 동기화를 위한 락
_session_lock = asyncio.Lock()


class SessionType(IntEnum):
    """세션 상태 열거형"""

    IDLE = 1        # 대기 중 (탐험 완료 후 다음 인카운터 대기)
    EXPLORING = 2   # 탐험 중
    FIGHT = 3       # 전투 중
    EVENT = 4       # 이벤트 처리 중 (전투/도주 선택 등)
    REST = 5        # 휴식 중


class ContentType(IntEnum):
    """콘텐츠 타입 열거형 (제한 규칙 적용용)"""

    NORMAL_DUNGEON = 1  # 일반 던전
    WEEKLY_TOWER = 2    # 주간 타워
    RAID = 3            # 레이드


@dataclass
class DungeonSession:
    """
    던전 세션 데이터 클래스

    사용자의 던전 탐험 상태를 추적합니다.
    """

    user_id: int

    # 던전/사용자 참조
    dungeon: Optional["Dungeon"] = None
    user: Optional["User"] = None

    # 상태 플래그
    status: SessionType = SessionType.IDLE
    content_type: ContentType = ContentType.NORMAL_DUNGEON
    in_combat: bool = False
    ended: bool = False
    pending_exit: bool = False  # 이벤트 종료 후 던전 종료 대기

    # 진행 정보
    current_floor: int = 1          # 타워용 현재 층
    exploration_step: int = 0       # 탐험 진행도
    max_steps: int = 20             # 던전 클리어에 필요한 스텝 수

    # 누적 보상 (세션 요약용)
    total_exp: int = 0              # 획득한 총 경험치
    total_gold: int = 0             # 획득한 총 골드
    monsters_defeated: int = 0      # 처치한 몬스터 수
    items_found: list = field(default_factory=list)  # 획득한 아이템 ID 목록

    # Discord 메시지 참조
    ui_message: Optional["Message"] = None   # 공개 채널 메시지
    dm_message: Optional["Message"] = None   # DM 컨트롤 메시지
    message: Optional["Message"] = None      # 레거시 호환용
    discord_client: Optional[object] = None  # Discord client (난입자 UI 전송용)

    # 시간 정보
    start_time: float = field(default_factory=lambda: asyncio.get_event_loop().time())

    # 음성 채널 상태
    voice_channel_id: Optional[int] = None

    # 공유 인스턴스 추적 (Phase 1: Voice Channel Shared Dungeon)
    shared_instance_key: Optional[tuple[int, int]] = None
    """(voice_channel_id, dungeon_id) if in shared instance"""

    # 전투 컨텍스트 (1:N 전투 지원)
    combat_context: Optional["CombatContext"] = None
    """현재 전투 중인 몬스터 그룹 (전투 중에만 존재)"""

    # 탐험 버프 (아이템으로 부여)
    explore_buffs: dict = field(default_factory=dict)
    """활성 탐험 버프: {"drop_bonus": 50, "avoid_combat": 1, "force_treasure": 1, ...}"""

    # 관전자 추적 (관전 시스템)
    spectators: set[int] = field(default_factory=set)
    """이 세션을 관전 중인 Discord 유저 ID 집합"""

    # Phase 2: 난입자 거리 추적 (근접도 기반 비용/보상)
    intervention_distances: dict[int, int] = field(default_factory=dict)
    """user_id → 난입 요청 시 exploration_step 거리 (절댓값)"""

    spectator_messages: dict[int, "Message"] = field(default_factory=dict)
    """관전자 ID → 관전자 DM 메시지 매핑"""

    # Phase 3: 멀티유저 encounter
    active_encounter_event: Optional[object] = None
    """현재 진행 중인 멀티유저 encounter 이벤트 (MultiUserEncounterEvent)"""

    encounter_event_cooldown: float = 0.0
    """마지막 멀티유저 encounter 발생 스텝 (쿨타임)"""

    # Phase 4: 위기 목격 이벤트
    crisis_event_sent: bool = False
    """위기 목격 이벤트 전송 여부 (전투당 1회 제한)"""

    combat_notification_message: Optional["Message"] = None
    """서버 채널에 게시된 전투 알림 메시지 (관전 버튼 포함)"""

    # 난입 시스템 (멀티플레이어 전투)
    participants: dict[int, "User"] = field(default_factory=dict)
    """파티 참가자 (user_id → User 엔티티). 리더는 user 필드에 별도 보관"""

    participant_combat_messages: dict[int, "Message"] = field(default_factory=dict)
    """참가자별 전투 UI 메시지 (user_id → DM 메시지). 리더는 별도 관리"""

    intervention_pending: dict[int, float] = field(default_factory=dict)
    """난입 대기 중인 유저 (user_id → 요청 시간 timestamp)"""

    contribution: dict[int, int] = field(default_factory=dict)
    """기여도 추적 (user_id → 누적 데미지+치유)"""

    allow_intervention: bool = True
    """난입 허용 여부 (유저가 설정)"""

    # 레이드 전용 런타임 상태
    raid_id: Optional[int] = None
    raid_phase: int = 1
    raid_current_target: Optional[str] = None
    raid_target_priority: list[str] = field(default_factory=list)
    raid_pending_target: Optional[str] = None
    raid_target_apply_turn: int = 0
    raid_destroyed_parts: set[str] = field(default_factory=set)
    raid_locked_skills: set[str] = field(default_factory=set)
    raid_part_hp: dict[str, int] = field(default_factory=dict)
    raid_part_max_hp: dict[str, int] = field(default_factory=dict)
    raid_action_used_round: dict[int, int] = field(default_factory=dict)
    raid_action_next_round: dict[str, int] = field(default_factory=dict)
    raid_action_counters: dict[str, int] = field(default_factory=dict)
    raid_provoke_target_discord_id: Optional[int] = None
    raid_provoke_until_round: int = 0
    raid_last_broken_part_key: Optional[str] = None
    raid_gimmick_last_round: dict[str, int] = field(default_factory=dict)
    raid_pending_transition_id: Optional[int] = None
    raid_pending_minigame_id: Optional[int] = None
    raid_minigame_started_round: int = 0
    raid_minigame_inputs: list[str] = field(default_factory=list)
    raid_minigame_expected: list[str] = field(default_factory=list)
    raid_minigame_prompt: Optional[str] = None
    raid_minigame_stage_inputs: dict[str, str] = field(default_factory=dict)
    raid_minigame_stage_index: int = 0

    def is_dungeon_cleared(self) -> bool:
        """던전 클리어 조건 확인"""
        return self.exploration_step >= self.max_steps


# 활성 세션 저장소 (user_id -> DungeonSession)
active_sessions: dict[int, DungeonSession] = {}


async def create_session(user_id: int) -> Optional[DungeonSession]:
    """
    세션 생성 (원자적 연산 with double-check locking)

    이미 세션이 존재하면 None을 반환합니다.
    Race condition을 방지하기 위해 double-check locking을 사용합니다.

    Args:
        user_id: Discord 사용자 ID

    Returns:
        생성된 DungeonSession 객체 또는 None (이미 존재 시)
    """
    # First check (without lock - fast path)
    if user_id in active_sessions:
        existing = active_sessions[user_id]
        if not existing.ended:
            logger.warning(f"Session already exists for user {user_id} (fast path)")
            return None

    async with _session_lock:
        # Double-check inside lock (prevents race condition)
        if user_id in active_sessions:
            existing = active_sessions[user_id]
            if not existing.ended:
                logger.warning(f"Session already exists for user {user_id} (locked path)")
                return None
            else:
                # 종료된 세션은 제거
                del active_sessions[user_id]
                logger.info(f"Cleaned up ended session for user {user_id}")

        logger.info(f"Creating new session for user {user_id}")
        session = DungeonSession(user_id=user_id)
        active_sessions[user_id] = session
        return session


def get_session(user_id: int) -> Optional[DungeonSession]:
    """
    세션 조회

    Args:
        user_id: Discord 사용자 ID

    Returns:
        DungeonSession 객체 또는 None
    """
    return active_sessions.get(user_id)


async def end_session(user_id: int) -> None:
    """
    세션 종료 및 사용자 데이터 저장 (원자적 연산)

    Args:
        user_id: Discord 사용자 ID
    """
    async with _session_lock:
        if user_id not in active_sessions:
            return

        logger.info(f"Ending session for user {user_id}")
        session = active_sessions[user_id]
        session.ended = True

        # 전투 상태 강제 해제 (리소스 정리)
        session.in_combat = False
        session.status = SessionType.IDLE

        # 관전자 정리
        if session.spectators:
            try:
                from service.spectator.spectator_service import SpectatorService
                await SpectatorService.cleanup_spectators(session)
            except Exception as e:
                logger.error(f"Failed to cleanup spectators on session end: {e}")

        # 사용자 데이터 저장
        if session.user:
            try:
                await session.user.save()
            except Exception as e:
                logger.error(f"Failed to save user data on session end: {e}")

        del active_sessions[user_id]


def is_in_session(user_id: int) -> bool:
    """
    세션 존재 여부 확인

    Args:
        user_id: Discord 사용자 ID

    Returns:
        세션이 존재하고 종료되지 않았으면 True
    """
    return user_id in active_sessions and not active_sessions[user_id].ended


def is_in_combat(user_id: int) -> bool:
    """
    전투 중 여부 확인

    Args:
        user_id: Discord 사용자 ID

    Returns:
        전투 중이면 True
    """
    session = get_session(user_id)
    return session is not None and session.in_combat


def set_combat_state(user_id: int, in_combat: bool) -> None:
    """
    전투 상태 설정

    Args:
        user_id: Discord 사용자 ID
        in_combat: 전투 중 여부
    """
    session = get_session(user_id)
    if session:
        session.in_combat = in_combat
        session.status = SessionType.FIGHT if in_combat else SessionType.IDLE


def set_voice_channel(user_id: int, channel_id: Optional[int]) -> None:
    """
    음성 채널 상태 설정

    Args:
        user_id: Discord 사용자 ID
        channel_id: 음성 채널 ID (None이면 음성 채널에서 나감)
    """
    session = get_session(user_id)
    if session:
        session.voice_channel_id = channel_id
        logger.debug(f"User {user_id} voice channel set to {channel_id}")


def get_all_sessions() -> dict[int, DungeonSession]:
    """
    모든 활성 세션 조회

    Returns:
        활성 세션 딕셔너리
    """
    return active_sessions.copy()


def get_sessions_in_voice_channel(channel_id: int) -> list[DungeonSession]:
    """
    특정 음성 채널의 세션 목록 조회

    Args:
        channel_id: 음성 채널 ID

    Returns:
        해당 채널의 DungeonSession 목록
    """
    return [
        session for session in active_sessions.values()
        if session.voice_channel_id == channel_id and not session.ended
    ]
