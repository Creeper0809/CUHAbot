"""전투 기록 서비스 (Phase 5 - 환영 시스템)"""
import logging
from datetime import datetime
from typing import List

from models.combat_history import CombatHistory
from service.voice_channel.proximity_calculator import ProximityCalculator

logger = logging.getLogger(__name__)


class HistoryService:
    """전투 기록 및 환영 시스템 서비스"""

    @staticmethod
    async def record_combat(
        user_id: int,
        dungeon_id: int,
        step: int,
        monster_name: str,
        result: str,
        damage: int,
        turns: int,
        voice_channel_id: int = None
    ) -> CombatHistory:
        """
        전투 기록 저장

        Args:
            user_id: 유저 ID
            dungeon_id: 던전 ID
            step: 전투 발생 스텝
            monster_name: 몬스터 이름
            result: 전투 결과 (victory, defeat, fled)
            damage: 총 데미지
            turns: 턴 수
            voice_channel_id: 음성 채널 ID (선택)

        Returns:
            생성된 CombatHistory
        """
        history = await CombatHistory.create(
            user_id=user_id,
            dungeon_id=dungeon_id,
            exploration_step=step,
            monster_name=monster_name,
            result=result,
            total_damage=damage,
            turns_lasted=turns,
            voice_channel_id=voice_channel_id,
            expires_at=CombatHistory.calculate_expires_at()
        )

        logger.info(
            f"Combat history recorded: user {user_id}, "
            f"dungeon {dungeon_id}, step {step}, result {result}"
        )

        return history

    @staticmethod
    async def get_nearby_histories(
        dungeon_id: int,
        current_step: int,
        range: int = 3
    ) -> List[CombatHistory]:
        """
        근처 전투 기록 조회 (±range 스텝 이내)

        Args:
            dungeon_id: 던전 ID
            current_step: 현재 스텝
            range: 거리 범위 (기본 ±3 스텝)

        Returns:
            근처 전투 기록 리스트 (최신순)
        """
        # Guard: 만료되지 않은 기록만 조회
        now = datetime.now()

        # 거리 범위 내 기록 조회
        min_step = current_step - range
        max_step = current_step + range

        histories = await CombatHistory.filter(
            dungeon_id=dungeon_id,
            exploration_step__gte=min_step,
            exploration_step__lte=max_step,
            expires_at__gt=now
        ).prefetch_related("user").order_by("-created_at").all()

        # 정확한 거리 필터링 및 정렬
        nearby = []
        for history in histories:
            distance = ProximityCalculator.calculate_distance(
                current_step,
                history.exploration_step
            )
            if distance <= range:
                nearby.append(history)

        logger.debug(
            f"Found {len(nearby)} nearby combat histories "
            f"(dungeon {dungeon_id}, step {current_step}, range ±{range})"
        )

        return nearby

    @staticmethod
    async def cleanup_expired_histories() -> int:
        """
        만료된 전투 기록 삭제

        BackgroundTasksCog에서 6시간마다 호출됩니다.

        Returns:
            삭제된 레코드 수
        """
        now = datetime.now()

        deleted_count = await CombatHistory.filter(expires_at__lt=now).delete()

        if deleted_count > 0:
            logger.info(f"Deleted {deleted_count} expired combat histories")

        return deleted_count

    @staticmethod
    async def get_user_recent_histories(
        user_id: int,
        limit: int = 10
    ) -> List[CombatHistory]:
        """
        유저의 최근 전투 기록 조회

        Args:
            user_id: 유저 ID
            limit: 최대 개수

        Returns:
            최근 전투 기록 리스트 (최신순)
        """
        # 만료되지 않은 기록만 조회
        now = datetime.now()

        histories = await CombatHistory.filter(
            user_id=user_id,
            expires_at__gt=now
        ).prefetch_related("dungeon").order_by("-created_at").limit(limit).all()

        return histories
