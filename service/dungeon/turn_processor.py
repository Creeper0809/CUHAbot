"""
턴 처리 프로세서 (Turn Processor)

전투 턴의 실행 로직을 담당합니다.
"""
import logging
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from models import User
    from service.dungeon.combat_context import CombatContext
    from service.session import DungeonSession

logger = logging.getLogger(__name__)


class TurnProcessor:
    """턴 실행 로직 처리"""

    def __init__(self):
        """TurnProcessor 초기화"""
        pass

    async def execute_actor_action(
        self,
        session: "DungeonSession",
        user: "User",
        actor,
        context: "CombatContext"
    ) -> list[str]:
        """
        액터의 행동 실행

        Args:
            session: 던전 세션
            user: 유저
            actor: 행동할 엔티티
            context: 전투 컨텍스트

        Returns:
            행동 로그 리스트
        """
        from service.dungeon.combat_executor import _execute_entity_action
        return _execute_entity_action(session, user, actor, context)

    def check_death_triggers(
        self,
        context: "CombatContext",
        alive_before: set,
        user: "User"
    ) -> list[str]:
        """
        사망 트리거 확인 (on_death 컴포넌트)

        Args:
            context: 전투 컨텍스트
            alive_before: 행동 전 생존 몬스터 ID 집합
            user: 유저

        Returns:
            사망 트리거 로그
        """
        from service.dungeon.combat_executor import _check_death_triggers
        return _check_death_triggers(context, alive_before, user)

    async def should_end_combat(
        self,
        user: "User",
        session: "DungeonSession",
        context: "CombatContext"
    ) -> bool:
        """
        전투 종료 조건 확인

        Args:
            user: 유저
            session: 던전 세션
            context: 전투 컨텍스트

        Returns:
            전투 종료 여부
        """
        from service.dungeon.combat_executor import _all_players_dead
        return context.is_all_dead() or _all_players_dead(user, session)

    def get_next_actor(
        self,
        context: "CombatContext",
        user: "User",
        participants: dict
    ):
        """
        다음 행동할 액터 가져오기

        Args:
            context: 전투 컨텍스트
            user: 유저
            participants: 참가자 딕셔너리

        Returns:
            다음 액터 또는 None
        """
        return context.get_next_actor(user, participants)

    def fill_gauges(
        self,
        context: "CombatContext",
        user: "User",
        participants: dict
    ) -> None:
        """
        모든 엔티티의 행동 게이지 채우기

        Args:
            context: 전투 컨텍스트
            user: 유저
            participants: 참가자 딕셔너리
        """
        context.fill_gauges(user, participants)

    def consume_gauge(self, context: "CombatContext", actor) -> None:
        """
        액터의 행동 게이지 소비

        Args:
            context: 전투 컨텍스트
            actor: 행동한 액터
        """
        context.consume_gauge(actor)

    def check_and_advance_round(self, context: "CombatContext") -> bool:
        """
        라운드 진행 확인 및 전환

        Args:
            context: 전투 컨텍스트

        Returns:
            라운드가 전환되었으면 True
        """
        return context.check_and_advance_round()
