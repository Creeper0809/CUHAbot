"""상태이상 관련 설정"""
from dataclasses import dataclass


@dataclass(frozen=True)
class StatusEffectConfig:
    """상태이상 설정"""

    # 화상
    BURN_DAMAGE_PERCENT: float = 0.03
    """화상 턴당 피해 (최대 HP의 3%)"""

    BURN_MAX_STACKS: int = 5
    """화상 최대 스택"""

    BURN_DEFAULT_DURATION: int = 3
    """화상 기본 지속 턴"""

    # 독
    POISON_DAMAGE_PERCENT: float = 0.02
    """독 턴당 피해 (최대 HP의 2%)"""

    POISON_MAX_STACKS: int = 3
    """독 최대 스택"""

    POISON_DEFAULT_DURATION: int = 5
    """독 기본 지속 턴"""

    # 출혈
    BLEED_DAMAGE_PERCENT: float = 0.04
    """출혈 턴당 피해 (최대 HP의 4%)"""

    BLEED_DEFAULT_DURATION: int = 2
    """출혈 기본 지속 턴"""

    # 둔화
    SLOW_SPEED_REDUCTION: float = 0.3
    """둔화 속도 감소율 (30%)"""

    SLOW_DEFAULT_DURATION: int = 2
    """둔화 기본 지속 턴"""

    # 동결
    FREEZE_DAMAGE_INCREASE: float = 0.2
    """동결 시 받는 피해 증가 (20%)"""

    FREEZE_DEFAULT_DURATION: int = 1
    """동결 기본 지속 턴"""

    # 상태이상 저항
    MAX_STATUS_RESISTANCE: float = 0.8
    """최대 상태이상 저항 (80%)"""


STATUS_EFFECT = StatusEffectConfig()
