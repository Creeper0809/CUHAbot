"""유저 스탯 관련 설정"""
from dataclasses import dataclass


@dataclass(frozen=True)
class UserStatsConfig:
    """유저 스탯 설정"""

    # 초기 스탯
    INITIAL_HP: int = 300
    """초기 HP"""

    INITIAL_ATTACK: int = 10
    """초기 공격력"""

    INITIAL_SPEED: int = 10
    """초기 속도"""

    INITIAL_LEVEL: int = 1
    """초기 레벨"""

    # 레벨업 스탯 증가
    HP_PER_LEVEL: int = 20
    """레벨당 HP 증가"""

    ATTACK_PER_LEVEL: int = 2
    """레벨당 공격력 증가"""

    # 스탯 포인트
    STAT_POINTS_PER_LEVEL: int = 3
    """레벨당 스탯 포인트"""


USER_STATS = UserStatsConfig()
