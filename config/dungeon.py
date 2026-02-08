"""던전 관련 설정"""
from dataclasses import dataclass


@dataclass(frozen=True)
class DungeonConfig:
    """던전 설정"""

    # 레벨 제한
    MIN_LEVEL_DIFFERENCE: int = -10
    """던전 입장 최소 레벨 차이 (권장 레벨보다 최대 10 낮아도 입장 가능)"""

    # 보상 배율
    ELITE_EXP_MULTIPLIER: float = 2.0
    """엘리트 몬스터 경험치 배율"""

    BOSS_EXP_MULTIPLIER: float = 5.0
    """보스 몬스터 경험치 배율"""

    ELITE_GOLD_MULTIPLIER: float = 2.5
    """엘리트 몬스터 골드 배율"""

    BOSS_GOLD_MULTIPLIER: float = 10.0
    """보스 몬스터 골드 배율"""

    BOSS_SPAWN_RATE: float = 0.05
    """보스 몬스터 기본 등장 확률 (스폰 테이블 내 존재 시)"""

    BOSS_SPAWN_PROGRESS_THRESHOLD: float = 0.9
    """보스 등장 가능 진행도 (90% 이상)"""

    BOSS_SPAWN_RATE_AT_END: float = 0.1
    """던전 마지막(90% 이상) 진행도에서 보스 등장 확률 (10%)"""

    # 그룹 전투 설정
    GROUP_SPAWN_RATE: float = 0.1
    """몬스터 그룹 등장 확률 (10%)"""

    MAX_GROUP_SIZE: int = 3
    """최대 그룹 크기 (1~3마리)"""

    # 그룹 전투 보너스
    GROUP_EXP_BONUS: float = 1.2
    """그룹 처치 시 경험치 보너스 (+20%)"""

    GROUP_GOLD_BONUS: float = 1.1
    """그룹 처치 시 골드 보너스 (+10%)"""

    MIN_GROUP_SIZE: int = 1
    """최소 그룹 크기"""

    # 던전 탐험
    BASE_STEPS: int = 15
    """기본 던전 스텝 수"""

    STEPS_PER_LEVEL_TIER: int = 10
    """레벨 10단위당 추가 스텝"""

    # 보상/패널티
    BASE_EXP_PER_MONSTER: int = 20
    """몬스터당 기본 경험치"""

    BASE_GOLD_PER_MONSTER: int = 10
    """몬스터당 기본 골드"""

    CLEAR_BONUS_MULTIPLIER: float = 0.2
    """던전 클리어 보너스 배율 (20%)"""

    DEATH_GOLD_LOSS: float = 0.1
    """사망 시 골드 손실 비율 (10%)"""

    # 드롭
    LUCK_DROP_BONUS_PER_POINT: float = 0.01
    """행운 1포인트당 드롭률 증가 (1%)"""

    # 던전 입장 조건
    MIN_HP_PERCENT_TO_ENTER: float = 0.3
    """던전 입장 최소 HP 비율 (30%)"""


DUNGEON = DungeonConfig()
