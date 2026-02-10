"""
공유 던전 인스턴스 관리자

(음성_채널_ID, 던전_ID) 키를 기반으로 공유 인스턴스를 관리합니다.
"""
import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Dict, Set, Tuple, Optional, List

logger = logging.getLogger(__name__)


@dataclass
class SharedDungeonInstance:
    """
    공유 던전 인스턴스

    같은 음성 채널 + 같은 던전 조합으로 생성되는 논리적 인스턴스.
    각 사용자는 독립적으로 탐험하지만 같은 공간을 공유합니다.
    """

    voice_channel_id: int
    """Discord 음성 채널 ID"""

    dungeon_id: int
    """던전 ID"""

    session_ids: Set[int] = field(default_factory=set)
    """이 인스턴스에 참여 중인 DungeonSession의 user_id 목록"""

    created_at: float = field(default_factory=lambda: time.time())
    """인스턴스 생성 시각"""

    def add_session(self, user_id: int) -> None:
        """세션 추가"""
        self.session_ids.add(user_id)
        logger.debug(f"Added session {user_id} to instance ({self.voice_channel_id}, {self.dungeon_id})")

    def remove_session(self, user_id: int) -> None:
        """세션 제거"""
        self.session_ids.discard(user_id)
        logger.debug(f"Removed session {user_id} from instance ({self.voice_channel_id}, {self.dungeon_id})")

    def is_empty(self) -> bool:
        """인스턴스가 비어있는지 확인"""
        return len(self.session_ids) == 0

    def get_session_count(self) -> int:
        """참여 중인 세션 수"""
        return len(self.session_ids)

    def get_key(self) -> Tuple[int, int]:
        """인스턴스 키"""
        return (self.voice_channel_id, self.dungeon_id)


class SharedInstanceManager:
    """
    공유 던전 인스턴스 관리자 (싱글톤)

    Responsibilities:
    - 인스턴스 생성/삭제
    - 세션 참여/탈퇴 관리
    - 인스턴스 조회
    """

    def __init__(self):
        self._instances: Dict[Tuple[int, int], SharedDungeonInstance] = {}
        """(voice_channel_id, dungeon_id) → SharedDungeonInstance 매핑"""

        self._user_to_instance: Dict[int, Tuple[int, int]] = {}
        """user_id → (voice_channel_id, dungeon_id) 매핑"""

        self._lock = asyncio.Lock()
        """동시성 안전성을 위한 Lock"""

        logger.info("SharedInstanceManager initialized")

    async def _remove_user_from_all_instances(self, user_id: int) -> None:
        """
        사용자를 모든 인스턴스에서 제거 (멱등성 보장)

        Args:
            user_id: 사용자 ID
        """
        old_key = self._user_to_instance.pop(user_id, None)
        if old_key and old_key in self._instances:
            try:
                self._instances[old_key].remove_session(user_id)
                logger.debug(f"Removed user {user_id} from instance {old_key}")

                # 빈 인스턴스 정리
                if self._instances[old_key].is_empty():
                    del self._instances[old_key]
                    logger.info(f"Cleaned up empty instance: {old_key}")
            except KeyError:
                # 이미 제거된 경우 무시
                logger.debug(f"User {user_id} was already removed from instance {old_key}")

    async def join_instance(
        self,
        user_id: int,
        voice_channel_id: int,
        dungeon_id: int
    ) -> SharedDungeonInstance:
        """
        공유 인스턴스에 참여 (없으면 생성)

        Args:
            user_id: 사용자 ID
            voice_channel_id: 음성 채널 ID
            dungeon_id: 던전 ID

        Returns:
            참여한 SharedDungeonInstance
        """
        async with self._lock:
            key = (voice_channel_id, dungeon_id)

            # 명확한 클린업: 모든 기존 인스턴스에서 제거
            await self._remove_user_from_all_instances(user_id)

            # 인스턴스 생성 또는 조회
            if key not in self._instances:
                self._instances[key] = SharedDungeonInstance(
                    voice_channel_id=voice_channel_id,
                    dungeon_id=dungeon_id
                )
                logger.info(f"Created new shared instance: vc={voice_channel_id}, dungeon={dungeon_id}")

            instance = self._instances[key]
            instance.add_session(user_id)
            self._user_to_instance[user_id] = key

            logger.info(
                f"User {user_id} joined instance (vc={voice_channel_id}, dungeon={dungeon_id}). "
                f"Total participants: {instance.get_session_count()}"
            )

            return instance

    async def leave_instance(self, user_id: int) -> Optional[SharedDungeonInstance]:
        """
        현재 인스턴스에서 탈퇴

        Args:
            user_id: 사용자 ID

        Returns:
            탈퇴한 인스턴스 (없으면 None)
        """
        async with self._lock:
            if user_id not in self._user_to_instance:
                return None

            key = self._user_to_instance[user_id]
            del self._user_to_instance[user_id]

            if key not in self._instances:
                return None

            instance = self._instances[key]
            instance.remove_session(user_id)

            logger.info(
                f"User {user_id} left instance {key}. "
                f"Remaining participants: {instance.get_session_count()}"
            )

            # 빈 인스턴스 정리
            if instance.is_empty():
                del self._instances[key]
                logger.info(f"Cleaned up empty instance: {key}")

            return instance

    def get_instance(
        self,
        voice_channel_id: int,
        dungeon_id: int
    ) -> Optional[SharedDungeonInstance]:
        """
        특정 인스턴스 조회

        Args:
            voice_channel_id: 음성 채널 ID
            dungeon_id: 던전 ID

        Returns:
            SharedDungeonInstance (없으면 None)
        """
        key = (voice_channel_id, dungeon_id)
        return self._instances.get(key)

    def get_user_instance(self, user_id: int) -> Optional[SharedDungeonInstance]:
        """
        사용자가 참여 중인 인스턴스 조회

        Args:
            user_id: 사용자 ID

        Returns:
            SharedDungeonInstance (없으면 None)
        """
        if user_id not in self._user_to_instance:
            return None

        key = self._user_to_instance[user_id]
        return self._instances.get(key)

    def get_instances_in_channel(
        self,
        voice_channel_id: int
    ) -> List[SharedDungeonInstance]:
        """
        특정 음성 채널의 모든 인스턴스 조회 (다른 던전들)

        Args:
            voice_channel_id: 음성 채널 ID

        Returns:
            SharedDungeonInstance 리스트
        """
        return [
            instance for key, instance in self._instances.items()
            if key[0] == voice_channel_id
        ]

    def get_instance_count(self) -> int:
        """활성 인스턴스 수 (디버깅용)"""
        return len(self._instances)

    def get_all_instances(self) -> List[SharedDungeonInstance]:
        """모든 활성 인스턴스 (디버깅용)"""
        return list(self._instances.values())


# 싱글톤 인스턴스
shared_instance_manager = SharedInstanceManager()
