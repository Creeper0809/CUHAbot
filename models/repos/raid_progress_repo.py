"""
Raid progress repository

주간 레이드 진행도 CRUD를 담당합니다.
"""
from datetime import datetime, timezone

from tortoise.exceptions import OperationalError

from models import User, UserRaidProgress


async def get_or_create_progress(user: User, raid_id: int, week_key: int) -> UserRaidProgress:
    """유저의 주간 레이드 진행도 조회 또는 생성"""
    try:
        progress, _ = await UserRaidProgress.get_or_create(
            user=user,
            raid_id=raid_id,
            week_key=week_key,
            defaults={
                "entries_used": 0,
                "clears": 0,
                "first_clear_reward_claimed": False,
                "best_clear_turns": None,
                "last_entered_at": None,
                "last_cleared_at": None,
            }
        )
        return progress
    except OperationalError as exc:
        raise RuntimeError("레이드 진행도 테이블이 아직 생성되지 않았습니다.") from exc


async def save_progress(progress: UserRaidProgress) -> None:
    """진행도 저장"""
    try:
        await progress.save()
    except OperationalError:
        return


async def mark_enter(progress: UserRaidProgress) -> None:
    """레이드 입장 기록"""
    progress.entries_used += 1
    progress.last_entered_at = datetime.now(timezone.utc)
    await save_progress(progress)


async def mark_clear(progress: UserRaidProgress, clear_turns: int | None = None) -> None:
    """레이드 클리어 기록"""
    progress.clears += 1
    progress.last_cleared_at = datetime.now(timezone.utc)
    if clear_turns and clear_turns > 0:
        if progress.best_clear_turns is None or clear_turns < progress.best_clear_turns:
            progress.best_clear_turns = clear_turns
    await save_progress(progress)
