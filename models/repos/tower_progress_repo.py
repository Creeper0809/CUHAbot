"""
Tower progress repository

주간 타워 진행도 CRUD를 담당합니다.
"""
from datetime import datetime, timezone

from models import User, UserTowerProgress


async def get_or_create_progress(user: User, season_id: int) -> UserTowerProgress:
    """유저의 시즌 진행도 조회 또는 생성"""
    progress, _ = await UserTowerProgress.get_or_create(
        user=user,
        season_id=season_id,
        defaults={
            "highest_floor_reached": 0,
            "current_floor": 0,
            "rewards_claimed": [],
            "tower_coins": 0,
            "last_attempt_time": None,
            "season_start_time": datetime.now(timezone.utc),
        }
    )
    return progress


async def update_highest_floor(user: User, season_id: int, floor: int) -> None:
    """최고 층수 업데이트"""
    progress = await UserTowerProgress.get_or_none(user=user, season_id=season_id)
    if not progress:
        progress = await get_or_create_progress(user, season_id)

    if floor > progress.highest_floor_reached:
        progress.highest_floor_reached = floor
        await progress.save()


async def save_progress(progress: UserTowerProgress) -> None:
    """진행도 저장"""
    progress.last_attempt_time = datetime.now(timezone.utc)
    await progress.save()
