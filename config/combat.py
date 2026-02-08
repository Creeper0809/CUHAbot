"""전투 관련 설정"""
from dataclasses import dataclass


@dataclass(frozen=True)
class CombatConfig:
    """전투 설정"""

    # 전투 로그
    COMBAT_LOG_MAX_LENGTH: int = 6
    """전투 로그 최대 줄 수"""

    EVENT_QUEUE_MAX_LENGTH: int = 5
    """이벤트 큐 최대 길이"""

    # 턴 순서 계산 (1:1 전투용, 레거시)
    SPEED_ADVANTAGE_CAP: int = 50
    """속도 우위 최대값 (+-50)"""

    BASE_TURN_PROBABILITY: int = 50
    """기본 선공 확률 (%)"""

    # 행동 게이지 시스템 (1:N 전투용)
    ACTION_GAUGE_MAX: int = 10
    """행동 게이지 최대값 (속도 10 기준)"""

    ACTION_GAUGE_BASE_FILL: int = 10
    """기본 게이지 충전량 (속도 10 기준)"""

    ACTION_GAUGE_SPEED_MULTIPLIER: float = 1.0
    """속도당 게이지 충전 배율 (충전량 = 속도 x 배율)"""

    ACTION_GAUGE_COST: int = 10
    """행동 후 게이지 소모량"""

    MAX_ACTIONS_PER_LOOP: int = 100
    """무한루프 방지용 최대 행동 횟수"""

    # 딜레이 (초)
    MAIN_LOOP_DELAY: float = 5.0
    """던전 메인 루프 딜레이"""

    TURN_PHASE_DELAY: float = 1.0
    """턴 페이즈 간 딜레이"""

    COMBAT_END_DELAY: float = 2.0
    """전투 종료 후 딜레이"""

    # 도주
    FLEE_SUCCESS_RATE: float = 0.5
    """도주 성공 확률 (일반 몬스터)"""

    FLEE_ELITE_SUCCESS_RATE: float = 0.0
    """도주 성공 확률 (엘리트/보스)"""


COMBAT = CombatConfig()
