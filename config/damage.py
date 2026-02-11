"""데미지 계산 관련 설정"""
from dataclasses import dataclass


@dataclass(frozen=True)
class DamageConfig:
    """데미지 계산 설정"""

    # 방어력 적용
    PHYSICAL_DEFENSE_RATIO: float = 0.5
    """물리 방어력 적용 비율 (데미지 = 공격력 - 방어력 x 0.5)"""

    MAGICAL_DEFENSE_RATIO: float = 0.4
    """마법 방어력 적용 비율 (데미지 = 마공 - 마방 x 0.4)"""

    # 방어력 무시
    MAX_ARMOR_PENETRATION: float = 0.7
    """최대 방어력 무시 비율 (70%)"""

    # 데미지 변동
    DAMAGE_VARIANCE: float = 0.2
    """데미지 랜덤 변동폭 (+-20%, 0.8~1.2배)"""

    MIN_DAMAGE: int = 1
    """최소 데미지 (0 이하로 떨어지지 않음)"""

    # 치명타
    CRITICAL_MULTIPLIER: float = 1.5
    """치명타 데미지 배율"""

    DEFAULT_CRITICAL_RATE: float = 0.05
    """기본 치명타 확률 (5%)"""

    # 명중/회피
    DEFAULT_ACCURACY: int = 90
    """기본 명중률 (%)"""

    DEFAULT_EVASION: int = 5
    """기본 회피율 (%)"""

    MIN_HIT_RATE: int = 5
    """최소 명중률 (%) - 아무리 회피가 높아도 이 확률은 보장"""

    MAX_HIT_RATE: int = 100
    """최대 명중률 (%)"""


DAMAGE = DamageConfig()
