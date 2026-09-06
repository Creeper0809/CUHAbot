"""Settlement rules shared by death and timeout exits."""

from config import ROGUELIKE


def apply_failure_penalty(session) -> tuple[int, int]:
    """Keep items untouched and retain exactly 70% of run EXP and gold."""
    original_exp = max(0, int(session.total_exp))
    original_gold = max(0, int(session.total_gold))
    session.total_exp = int(original_exp * ROGUELIKE.FAILURE_REWARD_RATE)
    session.total_gold = int(original_gold * ROGUELIKE.FAILURE_REWARD_RATE)
    return original_exp - session.total_exp, original_gold - session.total_gold
