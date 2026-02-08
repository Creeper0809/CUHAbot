"""
RewardService

던전 보상 적용 및 레벨업 처리를 담당합니다.
"""
import logging
from dataclasses import dataclass
from typing import Optional

from models import User
from config import USER_STATS, LEVELING_EXP_TABLE, LEVELING_EXP_DEFAULT

logger = logging.getLogger(__name__)

# 레벨당 스탯 포인트 (config에서 가져옴)
STAT_POINTS_PER_LEVEL = USER_STATS.STAT_POINTS_PER_LEVEL


@dataclass
class LevelUpResult:
    """레벨업 결과"""
    leveled_up: bool
    old_level: int
    new_level: int
    levels_gained: int
    stat_points_gained: int


@dataclass
class RewardResult:
    """보상 적용 결과"""
    exp_gained: int
    gold_gained: int
    level_up: Optional[LevelUpResult]


def get_exp_multiplier(level: int) -> int:
    """
    레벨에 따른 경험치 배율 반환

    Args:
        level: 현재 레벨

    Returns:
        필요 경험치 배율
    """
    for max_level, exp_required in LEVELING_EXP_TABLE:
        if level <= max_level:
            return exp_required
    return LEVELING_EXP_DEFAULT


def get_exp_for_level(level: int) -> int:
    """
    특정 레벨까지 필요한 누적 경험치 계산

    Args:
        level: 목표 레벨

    Returns:
        필요 누적 경험치
    """
    total_exp = 0
    for lv in range(1, level):
        total_exp += get_exp_multiplier(lv) * lv
    return total_exp


def get_exp_to_next_level(level: int) -> int:
    """
    다음 레벨까지 필요한 경험치

    Args:
        level: 현재 레벨

    Returns:
        다음 레벨까지 필요한 경험치
    """
    return get_exp_multiplier(level) * level


def calculate_level_from_exp(total_exp: int) -> int:
    """
    총 경험치로부터 레벨 계산

    Args:
        total_exp: 총 누적 경험치

    Returns:
        계산된 레벨
    """
    level = 1
    cumulative = 0

    while level < 100:
        exp_needed = get_exp_multiplier(level) * level
        if cumulative + exp_needed > total_exp:
            break
        cumulative += exp_needed
        level += 1

    return level


class RewardService:
    """보상 및 레벨업 비즈니스 로직"""

    @staticmethod
    async def apply_rewards(
        user: User,
        exp_gained: int,
        gold_gained: int
    ) -> RewardResult:
        """
        보상 적용 및 레벨업 처리

        Args:
            user: 대상 사용자
            exp_gained: 획득 경험치
            gold_gained: 획득 골드

        Returns:
            보상 적용 결과
        """
        old_level = user.level

        # 경험치 및 골드 추가
        user.exp += exp_gained
        user.gold += gold_gained

        # 레벨업 체크
        new_level = calculate_level_from_exp(user.exp)
        level_up_result = None

        if new_level > old_level:
            # 레벨업!
            levels_gained = new_level - old_level
            stat_points_gained = levels_gained * STAT_POINTS_PER_LEVEL

            user.level = new_level
            user.stat_points += stat_points_gained

            level_up_result = LevelUpResult(
                leveled_up=True,
                old_level=old_level,
                new_level=new_level,
                levels_gained=levels_gained,
                stat_points_gained=stat_points_gained
            )

            logger.info(
                f"Level up: user={user.discord_id}, "
                f"{old_level} -> {new_level}, "
                f"stat_points=+{stat_points_gained} (total: {user.stat_points})"
            )

        # DB 저장
        await user.save()

        logger.info(
            f"Rewards applied: user={user.discord_id}, "
            f"exp=+{exp_gained} (total: {user.exp}), "
            f"gold=+{gold_gained} (total: {user.gold})"
        )

        return RewardResult(
            exp_gained=exp_gained,
            gold_gained=gold_gained,
            level_up=level_up_result
        )

    @staticmethod
    def get_level_progress(user: User) -> dict:
        """
        레벨 진행 상황 조회

        Args:
            user: 대상 사용자

        Returns:
            레벨 진행 정보 딕셔너리
        """
        current_level_exp = get_exp_for_level(user.level)
        next_level_exp = get_exp_for_level(user.level + 1)
        exp_in_current_level = user.exp - current_level_exp
        exp_needed_for_next = next_level_exp - current_level_exp

        progress = exp_in_current_level / exp_needed_for_next if exp_needed_for_next > 0 else 1.0

        return {
            "level": user.level,
            "current_exp": user.exp,
            "exp_in_level": exp_in_current_level,
            "exp_needed": exp_needed_for_next,
            "progress": min(progress, 1.0),
            "exp_to_next": max(0, exp_needed_for_next - exp_in_current_level)
        }
