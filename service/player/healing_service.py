"""
HealingService

자연 회복 시스템을 담당합니다.
HP 자연회복은 최대 HP 비례 % 방식 (VIT 기반).
"""
import logging
from datetime import datetime, timezone

from models import User
from models.users import UserStatEnum

logger = logging.getLogger(__name__)


class HealingService:
    """HP 회복 비즈니스 로직"""

    @staticmethod
    async def apply_natural_regen(user: User) -> int:
        """
        자연 회복 적용

        VIT 기반 최대 HP 비례 회복:
        회복량/분 = 최대 HP × (1% + VIT × 0.04%)

        Args:
            user: 대상 사용자

        Returns:
            회복된 HP량
        """
        now = datetime.now(timezone.utc)

        # last_regen_time이 None이면 현재 시간으로 초기화
        if user.last_regen_time is None:
            user.last_regen_time = now
            await user.save()
            return 0

        # 시간대 정보 처리
        last_time = user.last_regen_time
        if last_time.tzinfo is None:
            last_time = last_time.replace(tzinfo=timezone.utc)

        # 경과 시간 (분)
        elapsed_seconds = (now - last_time).total_seconds()
        elapsed_minutes = int(elapsed_seconds // 60)

        if elapsed_minutes <= 0:
            return 0

        # 이미 풀 HP면 시간만 갱신
        max_hp = user.get_stat()[UserStatEnum.HP]
        if user.now_hp >= max_hp:
            user.last_regen_time = now
            await user.save()
            return 0

        # VIT 기반 회복량 계산
        regen_rate = user.get_hp_regen_rate()
        regen_amount = int(max_hp * regen_rate * elapsed_minutes)
        regen_amount = max(regen_amount, 1)  # 최소 1 HP 회복
        actual_heal = user.heal(regen_amount)

        # 시간 갱신
        user.last_regen_time = now
        await user.save()

        logger.info(
            f"Natural regen applied: user={user.discord_id}, "
            f"minutes={elapsed_minutes}, rate={regen_rate:.2%}, healed={actual_heal}"
        )

        return actual_heal

    @staticmethod
    async def get_regen_status(user: User) -> dict:
        """
        회복 상태 조회

        Args:
            user: 대상 사용자

        Returns:
            회복 상태 정보 딕셔너리
        """
        now = datetime.now(timezone.utc)

        # last_regen_time이 None이면 현재 시간으로 초기화
        if user.last_regen_time is None:
            user.last_regen_time = now
            await user.save()

        # 시간대 정보 처리
        last_time = user.last_regen_time
        if last_time.tzinfo is None:
            last_time = last_time.replace(tzinfo=timezone.utc)

        max_hp = user.get_stat()[UserStatEnum.HP]
        regen_rate = user.get_hp_regen_rate()
        regen_per_min = int(max_hp * regen_rate)

        elapsed_seconds = (now - last_time).total_seconds()
        elapsed_minutes = int(elapsed_seconds // 60)
        pending_heal = regen_per_min * elapsed_minutes

        # 최대 회복 가능량
        max_heal = max(0, max_hp - user.now_hp)
        pending_heal = min(pending_heal, max_heal)

        # 풀 HP까지 필요한 시간
        hp_needed = max(0, max_hp - user.now_hp)
        if regen_per_min > 0 and hp_needed > 0:
            minutes_to_full = (hp_needed + regen_per_min - 1) // regen_per_min
        else:
            minutes_to_full = 0

        return {
            "current_hp": user.now_hp,
            "max_hp": max_hp,
            "regen_rate": regen_rate,
            "regen_per_min": regen_per_min,
            "elapsed_minutes": elapsed_minutes,
            "pending_heal": pending_heal,
            "minutes_to_full": minutes_to_full,
        }

    @staticmethod
    async def full_heal(user: User) -> int:
        """
        완전 회복 (관리자/특수 아이템용)

        Args:
            user: 대상 사용자

        Returns:
            회복된 HP량
        """
        max_hp = user.get_stat()[UserStatEnum.HP]
        heal_amount = max_hp - user.now_hp
        user.now_hp = max_hp
        user.last_regen_time = datetime.now(timezone.utc)
        await user.save()

        logger.info(f"Full heal: user={user.discord_id}, healed={heal_amount}")
        return heal_amount
