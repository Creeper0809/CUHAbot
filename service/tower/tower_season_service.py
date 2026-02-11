"""
주간 타워 시즌 관리
"""
import asyncio
from datetime import datetime, timedelta, timezone, time

from models import UserTowerProgress

SEASON_BASE_DATE = datetime(2024, 1, 1, tzinfo=timezone.utc)


def get_current_season(now: datetime | None = None) -> int:
    now = now or datetime.now(timezone.utc)
    delta_days = (now - SEASON_BASE_DATE).days
    if delta_days < 0:
        return 1
    return delta_days // 7 + 1


def get_next_reset_time(now: datetime | None = None) -> datetime:
    now = now or datetime.now(timezone.utc)
    # 다음 월요일 00:00
    if now.weekday() == 0 and now.time() == time(0, 0):
        return now
    days_ahead = (7 - now.weekday()) % 7
    if days_ahead == 0 and now.time() > time(0, 0):
        days_ahead = 7
    next_monday = (now + timedelta(days=days_ahead)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return next_monday


async def reset_season() -> None:
    new_season = get_current_season()
    now = datetime.now(timezone.utc)

    await UserTowerProgress.all().update(
        season_id=new_season,
        highest_floor_reached=0,
        current_floor=0,
        rewards_claimed=[],
        tower_coins=0,
        last_attempt_time=None,
        season_start_time=now,
    )


async def start_season_reset_task() -> None:
    async def _runner():
        while True:
            now = datetime.now(timezone.utc)
            next_reset = get_next_reset_time(now)
            sleep_seconds = max(0, (next_reset - now).total_seconds())
            await asyncio.sleep(sleep_seconds)
            await reset_season()

    asyncio.create_task(_runner())
