"""인카운터 관련 설정"""
from dataclasses import dataclass


@dataclass(frozen=True)
class EncounterConfig:
    """인카운터 설정"""

    # 기본 인카운터 확률 가중치
    MONSTER_WEIGHT: int = 60
    """몬스터 인카운터 가중치 (60%)"""

    TREASURE_WEIGHT: int = 10
    """보물상자 인카운터 가중치 (10%)"""

    TRAP_WEIGHT: int = 10
    """함정 인카운터 가중치 (10%)"""

    EVENT_WEIGHT: int = 10
    """랜덤 이벤트 인카운터 가중치 (10%)"""

    NPC_WEIGHT: int = 5
    """NPC 인카운터 가중치 (5%)"""

    HIDDEN_ROOM_WEIGHT: int = 5
    """숨겨진 방 인카운터 가중치 (5%)"""

    # 보물상자 등급 가중치
    CHEST_NORMAL_WEIGHT: int = 85
    """일반 상자 가중치"""

    CHEST_SILVER_WEIGHT: int = 14
    """은 상자 가중치"""

    CHEST_GOLD_WEIGHT: int = 1
    """금 상자 가중치"""

    # 함정 피해
    TRAP_DAMAGE_MIN: float = 0.05
    """함정 최소 피해율 (최대 HP의 5%)"""

    TRAP_DAMAGE_MAX: float = 0.15
    """함정 최대 피해율 (최대 HP의 15%)"""


ENCOUNTER = EncounterConfig()
