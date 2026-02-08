"""멀티플레이 관련 설정 (파티, 주간 타워, 옥션)"""
from dataclasses import dataclass


# =============================================================================
# 주간 타워
# =============================================================================

@dataclass(frozen=True)
class WeeklyTowerConfig:
    """주간 타워 설정"""

    TOTAL_FLOORS: int = 100
    """타워 총 층수"""

    BOSS_FLOOR_INTERVAL: int = 10
    """보스층 간격 (10, 20, 30...)"""

    ITEMS_ALLOWED: bool = False
    """아이템 사용 허용 여부"""

    SKILL_CHANGE_BETWEEN_FLOORS: bool = True
    """층 사이 스킬 변경 허용 여부"""

    FLEE_ALLOWED: bool = False
    """도주 허용 여부"""


WEEKLY_TOWER = WeeklyTowerConfig()


# =============================================================================
# 파티/멀티플레이
# =============================================================================

@dataclass(frozen=True)
class PartyConfig:
    """파티 설정"""

    MAX_PARTY_SIZE: int = 5
    """파티 최대 인원"""

    INTERVENTION_WINDOW_TURNS: int = 3
    """전투 난입 가능 턴 수"""

    INTERVENTION_COOLDOWN_SECONDS: int = 300
    """전투 난입 쿨타임 (5분)"""

    RESCUE_REQUEST_HP_THRESHOLD: float = 0.3
    """구조 요청 HP 임계값 (30%)"""

    URGENT_RESCUE_HP_THRESHOLD: float = 0.1
    """긴급 구조 요청 HP 임계값 (10%)"""


PARTY = PartyConfig()


# =============================================================================
# 옥션
# =============================================================================

@dataclass(frozen=True)
class AuctionConfig:
    """옥션 설정"""

    LISTING_FEE_PERCENT: float = 0.02
    """등록 수수료 (2%)"""

    SALE_FEE_PERCENT: float = 0.05
    """판매 수수료 (5%)"""

    MIN_LISTING_PRICE: int = 100
    """최소 등록 가격"""

    MAX_LISTING_DURATION_HOURS: int = 72
    """최대 등록 기간 (72시간)"""


AUCTION = AuctionConfig()
