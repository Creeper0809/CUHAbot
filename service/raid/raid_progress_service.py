from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from models import User
from models.repos.raid_progress_repo import get_or_create_progress, mark_clear, mark_enter


MAX_WEEKLY_RAID_ENTRIES = 3
FIRST_CLEAR_BONUS_EXP = 1200
FIRST_CLEAR_BONUS_GOLD = 800
CLEAR_BONUS_EXP = 300
CLEAR_BONUS_GOLD = 200


@dataclass
class RaidEntryCheckResult:
    allowed: bool
    remaining_entries: int
    max_entries: int


def get_week_key(now: datetime | None = None) -> int:
    """주간 키 (UTC, ISO year/week)"""
    now = now or datetime.now(timezone.utc)
    year, week, _ = now.isocalendar()
    return year * 100 + week


async def check_raid_entry(user: User, raid_id: int) -> RaidEntryCheckResult:
    week_key = get_week_key()
    progress = await get_or_create_progress(user, raid_id, week_key)
    remaining = max(0, MAX_WEEKLY_RAID_ENTRIES - int(progress.entries_used))
    return RaidEntryCheckResult(
        allowed=remaining > 0,
        remaining_entries=remaining,
        max_entries=MAX_WEEKLY_RAID_ENTRIES,
    )


async def consume_raid_entry(user: User, raid_id: int) -> tuple[int, int]:
    """입장권 소모 후 (남은, 최대) 반환"""
    week_key = get_week_key()
    progress = await get_or_create_progress(user, raid_id, week_key)
    await mark_enter(progress)
    remaining = max(0, MAX_WEEKLY_RAID_ENTRIES - int(progress.entries_used))
    return remaining, MAX_WEEKLY_RAID_ENTRIES


async def get_raid_clear_bonus(user: User, raid_id: int, clear_turns: int | None) -> tuple[int, int, bool]:
    """
    레이드 클리어 시 추가 보상 계산.
    returns: (exp_bonus, gold_bonus, first_clear_this_week)
    """
    week_key = get_week_key()
    progress = await get_or_create_progress(user, raid_id, week_key)

    is_first_clear = not bool(progress.first_clear_reward_claimed)
    exp_bonus = CLEAR_BONUS_EXP
    gold_bonus = CLEAR_BONUS_GOLD

    if is_first_clear:
        exp_bonus += FIRST_CLEAR_BONUS_EXP
        gold_bonus += FIRST_CLEAR_BONUS_GOLD
        progress.first_clear_reward_claimed = True

    await mark_clear(progress, clear_turns=clear_turns)
    return exp_bonus, gold_bonus, is_first_clear
