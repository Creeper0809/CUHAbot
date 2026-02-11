"""
음성 채널 상태 관리 서비스

사용자의 음성 채널 입장/퇴장 상태를 메모리에서 추적합니다.
"""
import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Dict, Set, Optional

logger = logging.getLogger(__name__)


@dataclass
class VoiceChannelState:
    """음성 채널 상태"""

    channel_id: int
    """Discord 음성 채널 ID"""

    user_ids: Set[int] = field(default_factory=set)
    """현재 이 채널에 있는 Discord 유저 ID 집합"""

    created_at: float = field(default_factory=lambda: time.time())
    """채널 상태 생성 시각"""

    def add_user(self, user_id: int) -> None:
        """유저 추가"""
        self.user_ids.add(user_id)

    def remove_user(self, user_id: int) -> None:
        """유저 제거"""
        self.user_ids.discard(user_id)

    def is_empty(self) -> bool:
        """채널이 비어있는지 확인"""
        return len(self.user_ids) == 0

    def get_user_count(self) -> int:
        """채널 내 유저 수"""
        return len(self.user_ids)


class VoiceChannelService:
    """
    음성 채널 상태 관리 서비스 (싱글톤)

    Responsibilities:
    - 음성 채널 입장/퇴장 이벤트 추적
    - 사용자 → 채널 매핑 관리
    - 채널 내 사용자 목록 조회
    """

    def __init__(self):
        self._user_to_channel: Dict[int, int] = {}
        """user_id → voice_channel_id 매핑"""

        self._channel_states: Dict[int, VoiceChannelState] = {}
        """voice_channel_id → VoiceChannelState 매핑"""

        self._lock = asyncio.Lock()
        """동시성 안전성을 위한 Lock"""

        logger.info("VoiceChannelService initialized")

    async def user_joined_channel(self, user_id: int, channel_id: int) -> None:
        """
        사용자가 음성 채널에 입장

        Args:
            user_id: Discord 유저 ID
            channel_id: Discord 음성 채널 ID
        """
        async with self._lock:
            # 기존 채널에서 제거 (이동의 경우)
            if user_id in self._user_to_channel:
                old_channel_id = self._user_to_channel[user_id]
                if old_channel_id in self._channel_states:
                    self._channel_states[old_channel_id].remove_user(user_id)
                    # 빈 채널 정리
                    if self._channel_states[old_channel_id].is_empty():
                        del self._channel_states[old_channel_id]
                        logger.debug(f"Cleaned up empty channel state: {old_channel_id}")

            # 새 채널에 추가
            self._user_to_channel[user_id] = channel_id

            if channel_id not in self._channel_states:
                self._channel_states[channel_id] = VoiceChannelState(channel_id=channel_id)
                logger.debug(f"Created new channel state: {channel_id}")

            self._channel_states[channel_id].add_user(user_id)
            logger.info(f"User {user_id} joined voice channel {channel_id}")

    async def user_left_channel(self, user_id: int) -> Optional[int]:
        """
        사용자가 현재 음성 채널에서 퇴장

        Args:
            user_id: Discord 유저 ID

        Returns:
            퇴장한 채널 ID (없으면 None)
        """
        async with self._lock:
            if user_id not in self._user_to_channel:
                return None

            channel_id = self._user_to_channel[user_id]
            del self._user_to_channel[user_id]

            if channel_id in self._channel_states:
                self._channel_states[channel_id].remove_user(user_id)

                # 빈 채널 정리
                if self._channel_states[channel_id].is_empty():
                    del self._channel_states[channel_id]
                    logger.debug(f"Cleaned up empty channel state: {channel_id}")

            logger.info(f"User {user_id} left voice channel {channel_id}")
            return channel_id

    def get_user_channel(self, user_id: int) -> Optional[int]:
        """
        사용자가 현재 있는 음성 채널 ID 조회

        Args:
            user_id: Discord 유저 ID

        Returns:
            음성 채널 ID (없으면 None)
        """
        return self._user_to_channel.get(user_id)

    def get_users_in_channel(self, channel_id: int) -> Set[int]:
        """
        특정 음성 채널에 있는 모든 사용자 ID 조회

        Args:
            channel_id: Discord 음성 채널 ID

        Returns:
            사용자 ID 집합
        """
        if channel_id not in self._channel_states:
            return set()

        return self._channel_states[channel_id].user_ids.copy()

    def are_in_same_channel(self, user_id_1: int, user_id_2: int) -> bool:
        """
        두 사용자가 같은 음성 채널에 있는지 확인

        Args:
            user_id_1: 첫 번째 사용자 ID
            user_id_2: 두 번째 사용자 ID

        Returns:
            같은 채널에 있으면 True
        """
        channel_1 = self.get_user_channel(user_id_1)
        channel_2 = self.get_user_channel(user_id_2)

        if channel_1 is None or channel_2 is None:
            return False

        return channel_1 == channel_2

    def get_channel_count(self) -> int:
        """활성 채널 수 (디버깅용)"""
        return len(self._channel_states)

    def get_total_users(self) -> int:
        """추적 중인 총 사용자 수 (디버깅용)"""
        return len(self._user_to_channel)


# 싱글톤 인스턴스
voice_channel_service = VoiceChannelService()
