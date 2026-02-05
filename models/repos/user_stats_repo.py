"""
UserStats Repository

사용자 스탯 데이터 접근 레이어입니다.
"""
from typing import Optional

from models import User
from models.user_stats import UserStats


async def get_user_stats(user: User) -> Optional[UserStats]:
    """
    사용자 스탯 조회

    Args:
        user: 대상 사용자

    Returns:
        UserStats 객체 또는 None
    """
    return await UserStats.get_or_none(user=user)


async def get_or_create_stats(user: User) -> UserStats:
    """
    사용자 스탯 조회 또는 생성

    Args:
        user: 대상 사용자

    Returns:
        UserStats 객체
    """
    stats, _ = await UserStats.get_or_create(user=user)
    return stats


async def get_stats_by_discord_id(discord_id: int) -> Optional[UserStats]:
    """
    Discord ID로 사용자 스탯 조회

    Args:
        discord_id: Discord 사용자 ID

    Returns:
        UserStats 객체 또는 None
    """
    user = await User.get_or_none(discord_id=discord_id)
    if not user:
        return None
    return await UserStats.get_or_none(user=user)
