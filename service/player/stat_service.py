"""
StatService

스탯 리셋 등 능력치 관리를 담당합니다.
"""
import logging

from models import User
from exceptions import InsufficientGoldError

logger = logging.getLogger(__name__)

# 리셋 비용: 레벨 × 100 골드
RESET_COST_PER_LEVEL = 100


class StatService:
    """스탯 관련 서비스"""

    @staticmethod
    def calculate_reset_cost(user: User) -> int:
        """리셋 비용 계산"""
        return user.level * RESET_COST_PER_LEVEL

    @staticmethod
    async def reset_stats(user: User) -> dict:
        """
        능력치 리셋 (모든 bonus → 0, 포인트 반환)

        Args:
            user: 대상 사용자

        Returns:
            리셋 결과 딕셔너리

        Raises:
            InsufficientGoldError: 골드 부족
        """
        cost = StatService.calculate_reset_cost(user)
        if user.gold < cost:
            raise InsufficientGoldError(cost, user.gold)

        # 반환할 포인트 = 현재 분배된 포인트 합계
        refunded = (
            user.bonus_str + user.bonus_int + user.bonus_dex
            + user.bonus_vit + user.bonus_luk
        )

        if refunded == 0:
            return {
                "refunded": 0,
                "cost": 0,
                "message": "리셋할 능력치가 없습니다.",
            }

        # 골드 차감
        user.gold -= cost

        # 능력치 초기화
        user.bonus_str = 0
        user.bonus_int = 0
        user.bonus_dex = 0
        user.bonus_vit = 0
        user.bonus_luk = 0

        # 포인트 반환
        user.stat_points += refunded

        await user.save()

        logger.info(
            f"User {user.id} reset stats: refunded={refunded}, cost={cost}"
        )

        return {
            "refunded": refunded,
            "cost": cost,
            "message": f"능력치가 초기화되었습니다. {refunded}포인트가 반환되었습니다.",
        }
