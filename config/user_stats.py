"""유저 스탯 관련 설정"""
from dataclasses import dataclass


@dataclass(frozen=True)
class UserStatsConfig:
    """유저 스탯 설정"""

    # 초기 스탯
    INITIAL_HP: int = 300
    """초기 HP"""

    INITIAL_ATTACK: int = 15
    """초기 물리 공격력"""

    INITIAL_AP_ATTACK: int = 15
    """초기 마법 공격력"""

    INITIAL_DEFENSE: int = 8
    """초기 물리 방어력"""

    INITIAL_AP_DEFENSE: int = 8
    """초기 마법 방어력"""

    INITIAL_SPEED: int = 100
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

    # 초기 보조 스탯 (백분율)
    INITIAL_ACCURACY: int = 95
    """초기 명중률 (%)"""

    INITIAL_EVASION: int = 5
    """초기 회피율 (%)"""

    INITIAL_CRITICAL_RATE: int = 5
    """초기 치명타율 (%)"""

    INITIAL_CRITICAL_DAMAGE: int = 150
    """초기 치명타 데미지 (%)"""

    # 출석 보상
    ATTENDANCE_BASE_GOLD: int = 100
    """출석 기본 골드"""

    ATTENDANCE_STREAK_BONUS: int = 50
    """연속 출석 1일당 추가 골드"""

    ATTENDANCE_MAX_STREAK: int = 7
    """연속 출석 보너스 최대 일수"""


@dataclass(frozen=True)
class StatConversionConfig:
    """능력치 → 전투 스탯 변환 계수"""

    # HP 변환 계수
    HP_STR: float = 6.0
    HP_INT: float = 6.0
    HP_VIT: float = 15.0

    # 물리 공격력 변환 계수
    ATTACK_STR: float = 2.0
    ATTACK_DEX: float = 0.6
    ATTACK_LUK: float = 0.3

    # 마법 공격력 변환 계수
    AP_ATTACK_INT: float = 2.0
    AP_ATTACK_LUK: float = 0.3

    # 물리 방어력 변환 계수
    AD_DEFENSE_STR: float = 0.2
    AD_DEFENSE_VIT: float = 0.55

    # 마법 방어력 변환 계수
    AP_DEFENSE_INT: float = 0.2
    AP_DEFENSE_VIT: float = 0.45

    # 속도 변환 계수
    SPEED_DEX: float = 0.25

    # 명중률 변환 계수 (%)
    ACCURACY_DEX: float = 0.08

    # 회피율 변환 계수 (%)
    EVASION_DEX: float = 0.04
    EVASION_LUK: float = 0.0

    # 치명타율 변환 계수 (%)
    CRIT_RATE_DEX: float = 0.0
    CRIT_RATE_LUK: float = 0.12

    # 치명타 데미지 변환 계수 (%)
    CRIT_DAMAGE_LUK: float = 0.35

    # 드롭률 변환 계수 (%)
    DROP_RATE_LUK: float = 0.08

    # HP 자연회복률
    HP_REGEN_BASE: float = 0.015
    HP_REGEN_VIT: float = 0.0008


USER_STATS = UserStatsConfig()
STAT_CONVERSION = StatConversionConfig()
