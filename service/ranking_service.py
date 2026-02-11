"""
RankingService

랭킹 시스템 비즈니스 로직을 제공합니다.
"""
import logging
from typing import Dict, List

from models.repos.users_repo import (
    get_top_users_by_level,
    get_top_users_by_gold,
    get_user_rank_by_level,
    get_user_rank_by_gold,
)

logger = logging.getLogger(__name__)


class RankingService:
    """랭킹 서비스"""

    @staticmethod
    async def get_level_ranking(limit: int = 100) -> List[Dict]:
        """
        레벨 랭킹 조회

        Args:
            limit: 조회할 최대 유저 수 (기본: 100)

        Returns:
            랭킹 정보 딕셔너리 목록:
            [
                {
                    "rank": 1,
                    "username": "플레이어명",
                    "discord_id": 1234567890,
                    "level": 50,
                    "exp": 123456,
                },
                ...
            ]
        """
        users = await get_top_users_by_level(limit)

        return [
            {
                "rank": idx + 1,
                "username": user.username,
                "discord_id": user.discord_id,
                "level": user.level,
                "exp": user.exp,
            }
            for idx, user in enumerate(users)
        ]

    @staticmethod
    async def get_gold_ranking(limit: int = 100) -> List[Dict]:
        """
        골드 랭킹 조회

        Args:
            limit: 조회할 최대 유저 수 (기본: 100)

        Returns:
            랭킹 정보 딕셔너리 목록:
            [
                {
                    "rank": 1,
                    "username": "플레이어명",
                    "discord_id": 1234567890,
                    "gold": 1000000,
                },
                ...
            ]
        """
        users = await get_top_users_by_gold(limit)

        return [
            {
                "rank": idx + 1,
                "username": user.username,
                "discord_id": user.discord_id,
                "gold": user.gold,
            }
            for idx, user in enumerate(users)
        ]

    @staticmethod
    async def get_user_rankings(user_id: int) -> Dict:
        """
        특정 유저의 모든 순위 조회

        Args:
            user_id: 유저 ID

        Returns:
            순위 딕셔너리:
            {
                "level_rank": 10,
                "gold_rank": 5,
            }
        """
        return {
            "level_rank": await get_user_rank_by_level(user_id),
            "gold_rank": await get_user_rank_by_gold(user_id),
        }
