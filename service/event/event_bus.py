"""
이벤트 버스 (Event Bus)

옵저버 패턴을 사용하여 게임 내 이벤트를 발행하고 구독합니다.
각 시스템은 이벤트를 발행하기만 하면 되고, 구독자(업적, 퀘스트 등)가 자동으로 처리합니다.
"""

import logging
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Any

logger = logging.getLogger(__name__)


class GameEventType(Enum):
    """게임 이벤트 타입"""

    # 전투 이벤트
    MONSTER_KILLED = "monster_killed"           # 몬스터 처치
    COMBAT_WON = "combat_won"                   # 전투 승리
    COMBAT_LOST = "combat_lost"                 # 전투 패배

    # 아이템 이벤트
    ITEM_OBTAINED = "item_obtained"             # 아이템 획득
    ITEM_USED = "item_used"                     # 아이템 사용

    # 탐험 이벤트
    DUNGEON_EXPLORED = "dungeon_explored"       # 던전 탐험
    DUNGEON_CLEARED = "dungeon_cleared"         # 던전 클리어
    FLOOR_CLEARED = "floor_cleared"             # 층 클리어

    # 재화 이벤트
    GOLD_OBTAINED = "gold_obtained"             # 골드 획득
    GOLD_CHANGED = "gold_changed"               # 보유 골드 변경

    # 성장 이벤트
    LEVEL_UP = "level_up"                       # 레벨업
    EXP_OBTAINED = "exp_obtained"               # 경험치 획득

    # 연승 이벤트
    WIN_STREAK_UPDATED = "win_streak"           # 연승 갱신


@dataclass
class GameEvent:
    """게임 이벤트"""

    type: GameEventType
    user_id: int
    data: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)

    def __repr__(self) -> str:
        return f"GameEvent(type={self.type.value}, user_id={self.user_id}, data={self.data})"


class EventBus:
    """
    이벤트 버스 (싱글톤)

    게임 내 모든 이벤트를 중앙에서 관리합니다.
    발행자(Publisher)는 이벤트를 발행하고, 구독자(Subscriber)는 이벤트를 수신합니다.

    Example:
        >>> event_bus = EventBus()
        >>>
        >>> # 구독
        >>> async def on_monster_killed(event: GameEvent):
        ...     print(f"Monster killed: {event.data['monster_name']}")
        >>>
        >>> event_bus.subscribe(GameEventType.MONSTER_KILLED, on_monster_killed)
        >>>
        >>> # 발행
        >>> await event_bus.publish(GameEvent(
        ...     type=GameEventType.MONSTER_KILLED,
        ...     user_id=123,
        ...     data={"monster_id": 1001, "monster_name": "슬라임"}
        ... ))
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._subscribers = {}
            cls._instance._initialized = True
            logger.info("EventBus instance created")
        return cls._instance

    def subscribe(self, event_type: GameEventType, callback: Callable) -> None:
        """
        이벤트 구독

        Args:
            event_type: 구독할 이벤트 타입
            callback: 이벤트 발생 시 호출할 콜백 함수 (async function)
        """
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []

        if callback not in self._subscribers[event_type]:
            self._subscribers[event_type].append(callback)
            logger.debug(f"Subscribed to {event_type.value}: {callback.__name__}")

    def unsubscribe(self, event_type: GameEventType, callback: Callable) -> None:
        """
        구독 취소

        Args:
            event_type: 구독 취소할 이벤트 타입
            callback: 구독 취소할 콜백 함수
        """
        if event_type in self._subscribers:
            try:
                self._subscribers[event_type].remove(callback)
                logger.debug(f"Unsubscribed from {event_type.value}: {callback.__name__}")
            except ValueError:
                pass

    async def publish(self, event: GameEvent) -> None:
        """
        이벤트 발행

        구독자들에게 이벤트를 전파합니다.
        각 구독자의 콜백이 순차적으로 호출되며, 에러가 발생해도 다른 구독자에게 영향을 주지 않습니다.

        Args:
            event: 발행할 이벤트
        """
        if event.type not in self._subscribers:
            logger.debug(f"No subscribers for event: {event.type.value}")
            return

        logger.debug(f"Publishing event: {event}")

        for callback in self._subscribers[event.type]:
            try:
                await callback(event)
            except Exception as e:
                logger.error(
                    f"Error in event callback {callback.__name__} for {event.type.value}: {e}",
                    exc_info=True
                )

    def get_subscriber_count(self, event_type: GameEventType) -> int:
        """
        특정 이벤트 타입의 구독자 수 반환

        Args:
            event_type: 이벤트 타입

        Returns:
            구독자 수
        """
        return len(self._subscribers.get(event_type, []))

    def clear_all_subscribers(self) -> None:
        """모든 구독자 제거 (테스트용)"""
        self._subscribers.clear()
        logger.info("All subscribers cleared")
