"""장비 인스턴스 등급 시스템 설정"""
from dataclasses import dataclass
from enum import IntEnum
from typing import Optional


class InstanceGrade(IntEnum):
    """인스턴스 등급 (아이템 드롭 시 랜덤 부여)"""
    NONE = 0    # 소비 아이템 등 (등급 없음)
    D = 1
    C = 2
    B = 3
    A = 4
    S = 5
    SS = 6
    SSS = 7
    MYTHIC = 8  # 신화


@dataclass(frozen=True)
class GradeInfo:
    """등급별 설정"""
    grade: InstanceGrade
    name: str
    stat_multiplier: float
    effect_slots_min: int
    effect_slots_max: int
    color_emoji: str


# 등급별 설정 테이블
GRADE_TABLE: dict[int, GradeInfo] = {
    InstanceGrade.D: GradeInfo(
        InstanceGrade.D, "D", 1.0, 0, 0, "⬜"
    ),
    InstanceGrade.C: GradeInfo(
        InstanceGrade.C, "C", 1.08, 0, 0, "🟩"
    ),
    InstanceGrade.B: GradeInfo(
        InstanceGrade.B, "B", 1.18, 0, 0, "🟦"
    ),
    InstanceGrade.A: GradeInfo(
        InstanceGrade.A, "A", 1.32, 0, 1, "🟪"
    ),
    InstanceGrade.S: GradeInfo(
        InstanceGrade.S, "S", 1.5, 1, 2, "🟨"
    ),
    InstanceGrade.SS: GradeInfo(
        InstanceGrade.SS, "SS", 1.72, 2, 2, "🟧"
    ),
    InstanceGrade.SSS: GradeInfo(
        InstanceGrade.SSS, "SSS", 1.98, 2, 3, "❤️"
    ),
    InstanceGrade.MYTHIC: GradeInfo(
        InstanceGrade.MYTHIC, "신화", 2.30, 3, 3, "💎"
    ),
}


# =============================================================================
# 드롭 확률 (컨텍스트별 가중치)
# =============================================================================

GRADE_DROP_WEIGHTS: dict[str, dict[int, float]] = {
    "normal": {
        InstanceGrade.D: 45,
        InstanceGrade.C: 28,
        InstanceGrade.B: 16,
        InstanceGrade.A: 8,
        InstanceGrade.S: 2.5,
        InstanceGrade.SS: 0.4,
        InstanceGrade.SSS: 0.09,
        InstanceGrade.MYTHIC: 0.01,
    },
    "elite": {
        InstanceGrade.D: 20,
        InstanceGrade.C: 28,
        InstanceGrade.B: 24,
        InstanceGrade.A: 17,
        InstanceGrade.S: 8,
        InstanceGrade.SS: 2.3,
        InstanceGrade.SSS: 0.6,
        InstanceGrade.MYTHIC: 0.1,
    },
    "boss": {
        InstanceGrade.D: 5,
        InstanceGrade.C: 12,
        InstanceGrade.B: 22,
        InstanceGrade.A: 27,
        InstanceGrade.S: 20,
        InstanceGrade.SS: 10,
        InstanceGrade.SSS: 3.5,
        InstanceGrade.MYTHIC: 0.5,
    },
    "box_low": {
        InstanceGrade.D: 50,
        InstanceGrade.C: 30,
        InstanceGrade.B: 13,
        InstanceGrade.A: 5,
        InstanceGrade.S: 1.5,
        InstanceGrade.SS: 0.4,
        InstanceGrade.SSS: 0.08,
        InstanceGrade.MYTHIC: 0.02,
    },
    "box_mid": {
        InstanceGrade.D: 25,
        InstanceGrade.C: 30,
        InstanceGrade.B: 25,
        InstanceGrade.A: 13,
        InstanceGrade.S: 5,
        InstanceGrade.SS: 1.5,
        InstanceGrade.SSS: 0.4,
        InstanceGrade.MYTHIC: 0.1,
    },
    "box_high": {
        InstanceGrade.D: 10,
        InstanceGrade.C: 20,
        InstanceGrade.B: 25,
        InstanceGrade.A: 25,
        InstanceGrade.S: 12,
        InstanceGrade.SS: 5,
        InstanceGrade.SSS: 2.5,
        InstanceGrade.MYTHIC: 0.5,
    },
    "box_best": {
        InstanceGrade.D: 5,
        InstanceGrade.C: 10,
        InstanceGrade.B: 20,
        InstanceGrade.A: 30,
        InstanceGrade.S: 20,
        InstanceGrade.SS: 10,
        InstanceGrade.SSS: 4,
        InstanceGrade.MYTHIC: 1,
    },
}


# =============================================================================
# 특수 효과 (Special Effects)
# =============================================================================

@dataclass(frozen=True)
class SpecialEffectDef:
    """특수 효과 정의"""
    effect_type: str
    name: str
    min_value: float
    max_value: float
    is_percent: bool
    """True면 퍼센트 표시 (예: 흡혈 3%), False면 고정값 (예: HP +50)"""


SPECIAL_EFFECT_POOL: list[SpecialEffectDef] = [
    SpecialEffectDef("lifesteal", "흡혈", 2, 5, True),
    SpecialEffectDef("crit_rate", "치명타 확률", 3, 15, True),
    SpecialEffectDef("crit_damage", "치명타 데미지", 10, 40, True),
    SpecialEffectDef("armor_pen", "방어력 관통", 3, 12, True),
    SpecialEffectDef("bonus_hp_pct", "추가 HP", 5, 20, True),
    SpecialEffectDef("bonus_speed_pct", "추가 속도", 3, 10, True),
]


def get_grade_info(grade_id: int) -> Optional[GradeInfo]:
    """등급 ID로 GradeInfo 반환"""
    return GRADE_TABLE.get(grade_id)


def get_grade_name_map() -> dict[str, int]:
    """등급 이름 → ID 매핑 (역방향 조회용)"""
    return {info.name: info.grade.value for info in GRADE_TABLE.values()}
