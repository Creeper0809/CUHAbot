"""유저 스탯 관련 설정"""
from dataclasses import dataclass


@dataclass(frozen=True)
class UserStatsConfig:
    """유저 스탯 설정"""

    # 초기 스탯
    INITIAL_HP: int = 300
    """초기 HP"""

    INITIAL_ATTACK: int = 10
    """초기 물리 공격력"""

    INITIAL_AP_ATTACK: int = 5
    """초기 마법 공격력"""

    INITIAL_DEFENSE: int = 5
    """초기 물리 방어력"""

    INITIAL_AP_DEFENSE: int = 5
    """초기 마법 방어력"""

    INITIAL_SPEED: int = 10
    """초기 속도"""

    INITIAL_LEVEL: int = 1
    """초기 레벨"""

    # Lv.1~50 레벨당 성장
    HP_PER_LEVEL: int = 10
    """레벨당 HP 증가"""

    ATTACK_PER_LEVEL: float = 1
    """레벨당 물리 공격력 증가"""

    AP_ATTACK_PER_LEVEL: float = 1
    """레벨당 마법 공격력 증가"""

    DEFENSE_PER_LEVEL: float = 1.0
    """레벨당 물리 방어력 증가"""

    AP_DEFENSE_PER_LEVEL: float = 1.0
    """레벨당 마법 방어력 증가"""

    # Lv.51+ 고레벨 성장 (레벨당 추가)
    HIGH_HP_PER_LEVEL: int = 30
    """고레벨 HP 증가"""

    HIGH_HP_QUADRATIC: float = 0.1
    """고레벨 HP 2차 계수 (over_level² × 0.1)"""

    HIGH_ATTACK_PER_LEVEL: int = 3
    """고레벨 물리 공격력 증가"""

    HIGH_ATTACK_BONUS_INTERVAL: int = 5
    """고레벨 물리 공격력 보너스 간격 (5레벨마다 +1)"""

    HIGH_AP_ATTACK_PER_LEVEL: float = 2.5
    """고레벨 마법 공격력 증가"""

    HIGH_AP_ATTACK_BONUS_INTERVAL: int = 5
    """고레벨 마법 공격력 보너스 간격"""

    HIGH_DEFENSE_PER_LEVEL: float = 1.5
    """고레벨 방어력 증가"""

    HIGH_DEFENSE_BONUS_INTERVAL: int = 8
    """고레벨 방어력 보너스 간격"""

    HIGH_LEVEL_THRESHOLD: int = 50
    """고레벨 구간 시작 레벨"""

    # 스탯 포인트
    STAT_POINTS_PER_LEVEL: int = 3
    """레벨당 스탯 포인트"""

    STAT_RESET_SCROLL_ID: int = 5817
    """스탯 초기화 스크롤 아이템 ID"""


@dataclass(frozen=True)
class StatConversionConfig:
    """능력치 → 전투 스탯 변환 계수"""

    # HP 변환 계수
    HP_STR: float = 10.0
    HP_INT: float = 5.0
    HP_VIT: float = 25.0

    # 물리 공격력 변환 계수
    ATTACK_STR: float = 3
    ATTACK_DEX: float = 1.5
    ATTACK_LUK: float = 1

    # 마법 공격력 변환 계수
    AP_ATTACK_INT: float = 3

    # 물리 방어력 변환 계수
    AD_DEFENSE_STR: float = 0.5
    AD_DEFENSE_VIT: float = 1.2

    # 마법 방어력 변환 계수
    AP_DEFENSE_INT: float = 1.2
    AP_DEFENSE_VIT: float = 0.8

    # 속도 변환 계수
    SPEED_DEX: float = 1.0

    # 명중률 변환 계수 (%)
    ACCURACY_DEX: float = 0.4

    # 회피율 변환 계수 (%)
    EVASION_DEX: float = 0.3
    EVASION_LUK: float = 0.1

    # 치명타율 변환 계수 (%)
    CRIT_RATE_DEX: float = 0.3
    CRIT_RATE_LUK: float = 0.5

    # 치명타 데미지 변환 계수 (%)
    CRIT_DAMAGE_LUK: float = 1.0

    # 드롭률 변환 계수 (%)
    DROP_RATE_LUK: float = 0.5

    # HP 자연회복률
    HP_REGEN_BASE: float = 0.015
    HP_REGEN_VIT: float = 0.0008


USER_STATS = UserStatsConfig()
STAT_CONVERSION = StatConversionConfig()
