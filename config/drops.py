"""아이템 드롭 및 상자 시스템 설정"""
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict


@dataclass(frozen=True)
class DropConfig:
    """드롭 설정"""

    # 등급별 기본 드롭률 (일반 몬스터)
    DROP_RATE_D: float = 0.20
    DROP_RATE_C: float = 0.10
    DROP_RATE_B: float = 0.05
    DROP_RATE_A: float = 0.02
    DROP_RATE_S: float = 0.005
    DROP_RATE_SS: float = 0.001
    DROP_RATE_SSS: float = 0.0001
    DROP_RATE_MYTHIC: float = 0.00005

    # 타입별 드롭률 배율
    ELITE_DROP_MULTIPLIER: float = 3.0
    """엘리트 몬스터 드롭률 배율"""

    BOSS_DROP_MULTIPLIER: float = 10.0
    """보스 몬스터 드롭률 배율"""

    # 상자 드롭 (새 시스템)
    BOX_DROP_RATE: float = 0.2
    """몬스터 처치 시 상자 드롭 확률 (20%)"""

    # 스킬 드롭
    SKILL_DROP_RATE: float = 0.001
    """몬스터 스킬 드롭 확률 (0.1%)"""

    # 장비 드롭
    EQUIPMENT_DROP_RATE: float = 0.005
    """몬스터 장비 드롭 확률 (0.5%)"""

    DUNGEON_EQUIPMENT_DROP_RATE: float = 0.10
    """던전 클리어 장비 드롭 확률 (10%)"""

    # 보물상자 골드
    CHEST_BASE_GOLD: int = 20
    """보물상자 기본 골드"""

    CHEST_GOLD_VARIANCE_MIN: float = 0.8
    """보물상자 골드 변동 최소"""

    CHEST_GOLD_VARIANCE_MAX: float = 1.2
    """보물상자 골드 변동 최대"""

    # 보물상자 아이템 ID (인카운터용)
    CHEST_ITEM_NORMAL_ID: int = 5940
    """일반 보물상자 아이템 ID (혼합 상자 - 하급)"""

    CHEST_ITEM_SILVER_ID: int = 5941
    """은 보물상자 아이템 ID (혼합 상자 - 중급)"""

    CHEST_ITEM_GOLD_ID: int = 5942
    """금 보물상자 아이템 ID (혼합 상자 - 상급)"""


DROP = DropConfig()


# =============================================================================
# 상자 시스템 (Box System)
# =============================================================================

class BoxRewardType(str, Enum):
    """상자 보상 타입"""
    GOLD = "gold"
    EQUIPMENT = "equipment"
    SKILL = "skill"


@dataclass(frozen=True)
class BoxRewardConfig:
    """단일 보상 설정"""
    reward_type: BoxRewardType
    """보상 타입 (골드/장비/스킬)"""

    probability: float
    """보상 확률 (0.0~1.0)"""

    guaranteed_grade: Optional[str] = None
    """확정 등급 ("D", "C", "B", "A", "S" 등)"""

    grade_table_id: Optional[int] = None
    """등급 확률 테이블 ID (ItemGradeProbability.cheat_id)"""


@dataclass(frozen=True)
class BoxConfig:
    """상자 설정"""
    box_id: int
    """상자 아이템 ID"""

    name: str
    """상자 이름"""

    rewards: list[BoxRewardConfig]
    """보상 목록"""

    gold_multiplier: float = 1.0
    """골드 보상 배율"""

    def validate(self) -> bool:
        """확률 합계 검증 (합이 ~1.0이어야 함)"""
        total = sum(r.probability for r in self.rewards)
        return 0.99 <= total <= 1.01


# 상자 설정 레지스트리
BOX_CONFIGS: Dict[int, BoxConfig] = {
    # 등급별 장비 상자 (5920-5924)
    5920: BoxConfig(
        box_id=5920,
        name="장비 상자 (D등급)",
        rewards=[BoxRewardConfig(BoxRewardType.EQUIPMENT, 1.0, guaranteed_grade="D")]
    ),
    5921: BoxConfig(
        box_id=5921,
        name="장비 상자 (C등급)",
        rewards=[BoxRewardConfig(BoxRewardType.EQUIPMENT, 1.0, guaranteed_grade="C")]
    ),
    5922: BoxConfig(
        box_id=5922,
        name="장비 상자 (B등급)",
        rewards=[BoxRewardConfig(BoxRewardType.EQUIPMENT, 1.0, guaranteed_grade="B")]
    ),
    5923: BoxConfig(
        box_id=5923,
        name="장비 상자 (A등급)",
        rewards=[BoxRewardConfig(BoxRewardType.EQUIPMENT, 1.0, guaranteed_grade="A")]
    ),
    5924: BoxConfig(
        box_id=5924,
        name="장비 상자 (S등급)",
        rewards=[BoxRewardConfig(BoxRewardType.EQUIPMENT, 1.0, guaranteed_grade="S")]
    ),

    # 등급별 스킬 상자 (5930-5934)
    5930: BoxConfig(
        box_id=5930,
        name="스킬 상자 (D등급)",
        rewards=[BoxRewardConfig(BoxRewardType.SKILL, 1.0, guaranteed_grade="D")]
    ),
    5931: BoxConfig(
        box_id=5931,
        name="스킬 상자 (C등급)",
        rewards=[BoxRewardConfig(BoxRewardType.SKILL, 1.0, guaranteed_grade="C")]
    ),
    5932: BoxConfig(
        box_id=5932,
        name="스킬 상자 (B등급)",
        rewards=[BoxRewardConfig(BoxRewardType.SKILL, 1.0, guaranteed_grade="B")]
    ),
    5933: BoxConfig(
        box_id=5933,
        name="스킬 상자 (A등급)",
        rewards=[BoxRewardConfig(BoxRewardType.SKILL, 1.0, guaranteed_grade="A")]
    ),
    5934: BoxConfig(
        box_id=5934,
        name="스킬 상자 (S등급)",
        rewards=[BoxRewardConfig(BoxRewardType.SKILL, 1.0, guaranteed_grade="S")]
    ),

    # 혼합 상자 (5940-5943)
    5940: BoxConfig(
        box_id=5940,
        name="혼합 상자 (하급)",
        rewards=[
            BoxRewardConfig(BoxRewardType.GOLD, 0.5),
            BoxRewardConfig(BoxRewardType.EQUIPMENT, 0.3, grade_table_id=4),
            BoxRewardConfig(BoxRewardType.SKILL, 0.2, grade_table_id=4),
        ],
        gold_multiplier=1.0
    ),
    5941: BoxConfig(
        box_id=5941,
        name="혼합 상자 (중급)",
        rewards=[
            BoxRewardConfig(BoxRewardType.GOLD, 0.4),
            BoxRewardConfig(BoxRewardType.EQUIPMENT, 0.35, grade_table_id=5),
            BoxRewardConfig(BoxRewardType.SKILL, 0.25, grade_table_id=5),
        ],
        gold_multiplier=2.0
    ),
    5942: BoxConfig(
        box_id=5942,
        name="혼합 상자 (상급)",
        rewards=[
            BoxRewardConfig(BoxRewardType.GOLD, 0.3),
            BoxRewardConfig(BoxRewardType.EQUIPMENT, 0.4, grade_table_id=6),
            BoxRewardConfig(BoxRewardType.SKILL, 0.3, grade_table_id=6),
        ],
        gold_multiplier=3.0
    ),
    5943: BoxConfig(
        box_id=5943,
        name="혼합 상자 (최상급)",
        rewards=[
            BoxRewardConfig(BoxRewardType.GOLD, 0.2),
            BoxRewardConfig(BoxRewardType.EQUIPMENT, 0.45, grade_table_id=7),
            BoxRewardConfig(BoxRewardType.SKILL, 0.35, grade_table_id=7),
        ],
        gold_multiplier=5.0
    ),

    # 특수 상자 (5945-5947)
    5945: BoxConfig(
        box_id=5945,
        name="럭키 박스",
        rewards=[
            BoxRewardConfig(BoxRewardType.EQUIPMENT, 0.5, grade_table_id=8),
            BoxRewardConfig(BoxRewardType.SKILL, 0.5, grade_table_id=8),
        ]
    ),
    5946: BoxConfig(
        box_id=5946,
        name="신비한 상자",
        rewards=[
            BoxRewardConfig(BoxRewardType.EQUIPMENT, 0.5, grade_table_id=9),
            BoxRewardConfig(BoxRewardType.SKILL, 0.5, grade_table_id=9),
        ]
    ),
    5947: BoxConfig(
        box_id=5947,
        name="마스터 상자",
        rewards=[
            BoxRewardConfig(BoxRewardType.EQUIPMENT, 0.6, guaranteed_grade="A"),
            BoxRewardConfig(BoxRewardType.SKILL, 0.4, guaranteed_grade="A"),
        ]
    ),
}
