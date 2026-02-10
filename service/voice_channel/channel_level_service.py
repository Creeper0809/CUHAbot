"""채널 레벨 서비스 (Phase 5)"""
import logging
from datetime import date as date_type
from typing import Dict, Optional

from models.voice_channel_level import VoiceChannelLevel
from service.economy.reward_service import calculate_level_from_exp

logger = logging.getLogger(__name__)


class ChannelLevelService:
    """음성 채널 레벨 시스템 서비스"""

    @staticmethod
    async def add_channel_exp(
        voice_channel_id: int,
        exp: int,
        user_id: int,
        damage: int
    ) -> Dict[str, any]:
        """
        채널 경험치 추가 및 레벨업 처리

        Args:
            voice_channel_id: 음성 채널 ID
            exp: 추가할 경험치
            user_id: 유저 ID (MVP 추적용)
            damage: 데미지 (MVP 추적용)

        Returns:
            {
                "leveled_up": bool,
                "new_level": int,
                "is_mvp": bool
            }
        """
        today = date_type.today()

        # 오늘 날짜 채널 레벨 레코드 조회 또는 생성
        channel_level, created = await VoiceChannelLevel.get_or_create(
            voice_channel_id=voice_channel_id,
            date=today,
            defaults={"level": 1, "exp": 0}
        )

        # 레벨업 체크
        old_level = channel_level.level
        channel_level.exp += exp
        new_level = calculate_level_from_exp(channel_level.exp)
        leveled_up = new_level > old_level

        if leveled_up:
            channel_level.level = new_level
            logger.info(
                f"Channel {voice_channel_id} leveled up! "
                f"{old_level} → {new_level} (exp: {channel_level.exp})"
            )

        # 통계 업데이트
        channel_level.total_combats += 1
        channel_level.total_damage += damage

        # MVP 업데이트
        is_mvp = False
        if damage > channel_level.mvp_damage:
            channel_level.mvp_user_id = user_id
            channel_level.mvp_damage = damage
            is_mvp = True
            logger.info(f"New MVP for channel {voice_channel_id}: user {user_id} ({damage} damage)")

        await channel_level.save()

        return {
            "leveled_up": leveled_up,
            "new_level": new_level,
            "is_mvp": is_mvp
        }

    @staticmethod
    async def get_channel_stats(voice_channel_id: int) -> Optional[VoiceChannelLevel]:
        """
        채널 통계 조회 (오늘 날짜)

        Args:
            voice_channel_id: 음성 채널 ID

        Returns:
            VoiceChannelLevel 또는 None
        """
        today = date_type.today()

        return await VoiceChannelLevel.get_or_none(
            voice_channel_id=voice_channel_id,
            date=today
        )

    @staticmethod
    async def get_channel_bonus(voice_channel_id: int) -> float:
        """
        채널 레벨 보너스 계산 (레벨당 +5%)

        Args:
            voice_channel_id: 음성 채널 ID

        Returns:
            보상 배율 (1.0 = 보너스 없음, 1.05 = +5%)
        """
        stats = await ChannelLevelService.get_channel_stats(voice_channel_id)

        if not stats:
            return 1.0

        # 레벨당 +5% (레벨 1 = 0%, 레벨 2 = 5%, ...)
        bonus = 1.0 + (stats.level - 1) * 0.05

        return bonus

    @staticmethod
    async def reset_daily_stats(voice_channel_id: int) -> None:
        """
        일일 통계 리셋

        Note: unique_together(voice_channel_id, date)로 인해
        새로운 날짜에 자동으로 새 레코드가 생성되므로,
        수동 리셋은 필요하지 않습니다.
        이 함수는 테스트용으로만 사용됩니다.

        Args:
            voice_channel_id: 음성 채널 ID
        """
        today = date_type.today()

        # 오늘 날짜 레코드 삭제 (다음 add_channel_exp에서 재생성됨)
        await VoiceChannelLevel.filter(
            voice_channel_id=voice_channel_id,
            date=today
        ).delete()

        logger.info(f"Reset daily stats for channel {voice_channel_id}")
