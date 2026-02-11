"""
주간 타워 보상 서비스
"""
from dataclasses import dataclass

from service.economy.reward_service import RewardService, RewardResult
from models import User
from models.user_tower_progress import UserTowerProgress

BASE_EXP_PER_FLOOR = 100
BASE_GOLD_PER_FLOOR = 50
BOSS_FLOOR_MULTIPLIER = 2.0

NORMAL_FLOOR_COINS = 1
BOSS_FLOOR_COINS = 5


@dataclass
class TowerReward:
    exp: int
    gold: int
    tower_coins: int


def calculate_floor_reward(floor: int, is_boss: bool) -> TowerReward:
    exp = floor * BASE_EXP_PER_FLOOR
    gold = floor * BASE_GOLD_PER_FLOOR
    if is_boss:
        exp = int(exp * BOSS_FLOOR_MULTIPLIER)
        gold = int(gold * BOSS_FLOOR_MULTIPLIER)
        coins = BOSS_FLOOR_COINS
    else:
        coins = NORMAL_FLOOR_COINS
    return TowerReward(exp=exp, gold=gold, tower_coins=coins)


async def apply_floor_reward(
    user: User,
    progress: UserTowerProgress,
    floor: int,
    is_boss: bool
) -> RewardResult:
    reward = calculate_floor_reward(floor, is_boss)
    progress.tower_coins += reward.tower_coins
    await progress.save()
    return await RewardService.apply_rewards(user, reward.exp, reward.gold)
