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

    # 시간 정보
    start_time: float = field(default_factory=lambda: asyncio.get_event_loop().time())

    # 음성 채널 상태
    voice_channel_id: Optional[int] = None

    # 전투 컨텍스트 (1:N 전투 지원)
    combat_context: Optional["CombatContext"] = None
    """현재 전투 중인 몬스터 그룹 (전투 중에만 존재)"""

    def is_dungeon_cleared(self) -> bool:
        """던전 클리어 조건 확인"""
        return self.exploration_step >= self.max_steps


# 활성 세션 저장소 (user_id -> DungeonSession)
active_sessions: dict[int, DungeonSession] = {}


async def create_session(user_id: int) -> Optional[DungeonSession]:
    """
    세션 생성 (원자적 연산)

    이미 세션이 존재하면 None을 반환합니다.
    Race condition을 방지하기 위해 락을 사용합니다.

    Args:
        user_id: Discord 사용자 ID

    Returns:
        생성된 DungeonSession 객체 또는 None (이미 존재 시)
    """
    async with _session_lock:
        # 이미 세션이 존재하면 None 반환
        if user_id in active_sessions and not active_sessions[user_id].ended:
            logger.warning(f"Session already exists for user {user_id}")
            return None

        logger.info(f"Creating session for user {user_id}")
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
