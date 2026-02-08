"""강화 시스템 설정"""
from dataclasses import dataclass


@dataclass(frozen=True)
class EnhancementConfig:
    """강화 설정"""

    MAX_LEVEL: int = 15
    """최대 강화 레벨"""

    DESTRUCTION_RATE: float = 0.2
    """파괴 확률 (+13~15 실패 시, 20%)"""

    BASE_COST: int = 100
    """기본 강화 비용"""

    COST_PER_LEVEL_MULTIPLIER: float = 0.3
    """레벨당 비용 증가율 (+30%)"""


ENHANCEMENT = EnhancementConfig()
