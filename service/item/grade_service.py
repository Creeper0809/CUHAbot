"""
GradeService

인스턴스 등급 롤링, 스탯 배율, 특수 효과 생성을 담당합니다.
"""
import logging
import random
from typing import Optional

from config.grade import (
    InstanceGrade,
    GRADE_TABLE,
    GRADE_DROP_WEIGHTS,
    SPECIAL_EFFECT_POOL,
    get_grade_info,
)

logger = logging.getLogger(__name__)


class GradeService:
    """인스턴스 등급 비즈니스 로직"""

    @staticmethod
    def roll_grade(context: str = "normal") -> int:
        """
        컨텍스트 기반 인스턴스 등급 랜덤 결정

        Args:
            context: 드롭 컨텍스트
                - "normal": 일반 몬스터
                - "elite": 엘리트 몬스터
                - "boss": 보스 몬스터
                - "box_low" ~ "box_best": 상자 등급별

        Returns:
            등급 ID (1=D ~ 8=신화)
        """
        weights_map = GRADE_DROP_WEIGHTS.get(context)
        if not weights_map:
            weights_map = GRADE_DROP_WEIGHTS["normal"]

        grades = list(weights_map.keys())
        weights = list(weights_map.values())

        return random.choices(grades, weights=weights, k=1)[0]

    @staticmethod
    def roll_special_effects(grade_id: int) -> Optional[list[dict]]:
        """
        등급 기반 특수 효과 랜덤 결정 (A등급 이상)

        Args:
            grade_id: 인스턴스 등급 ID

        Returns:
            특수 효과 리스트 또는 None
        """
        grade_info = get_grade_info(grade_id)
        if not grade_info:
            return None

        if grade_info.effect_slots_max <= 0:
            return None

        num_effects = random.randint(
            grade_info.effect_slots_min,
            grade_info.effect_slots_max
        )
        if num_effects <= 0:
            return None

        # 풀에서 중복 없이 랜덤 선택
        pool = list(SPECIAL_EFFECT_POOL)
        selected = random.sample(pool, min(num_effects, len(pool)))

        effects = []
        for effect_def in selected:
            # 등급이 높을수록 값 범위의 상위 구간 사용
            grade_factor = _grade_effect_factor(grade_id)
            value_range = effect_def.max_value - effect_def.min_value
            min_roll = effect_def.min_value + value_range * grade_factor * 0.3
            max_roll = effect_def.min_value + value_range * (0.4 + grade_factor * 0.6)

            value = round(random.uniform(min_roll, max_roll), 1)
            # 정수로 깔끔하게
            if value == int(value):
                value = int(value)

            effects.append({
                "type": effect_def.effect_type,
                "value": value,
            })

        return effects

    @staticmethod
    def get_stat_multiplier(grade_id: int) -> float:
        """
        등급별 스탯 배율 반환

        Args:
            grade_id: 인스턴스 등급 ID (0이면 1.0 반환)

        Returns:
            스탯 배율 (1.0 ~ 3.0)
        """
        if grade_id <= 0:
            return 1.0

        grade_info = get_grade_info(grade_id)
        if not grade_info:
            return 1.0

        return grade_info.stat_multiplier

    @staticmethod
    def get_grade_display(grade_id: int) -> str:
        """
        등급 표시 문자열 반환 (색상 이모지 + 이름)

        Args:
            grade_id: 인스턴스 등급 ID

        Returns:
            표시 문자열 (예: "🟨 S등급")
        """
        grade_info = get_grade_info(grade_id)
        if not grade_info:
            return ""

        return f"{grade_info.color_emoji} {grade_info.name}등급"

    @staticmethod
    def format_special_effects(effects: Optional[list[dict]]) -> str:
        """
        특수 효과를 표시 문자열로 변환

        Args:
            effects: 특수 효과 리스트

        Returns:
            줄바꿈 구분 표시 문자열
        """
        if not effects:
            return ""

        # 타입 → 이름 매핑
        name_map = {e.effect_type: e for e in SPECIAL_EFFECT_POOL}

        lines = []
        for effect in effects:
            effect_def = name_map.get(effect["type"])
            if not effect_def:
                continue

            value = effect["value"]
            suffix = "%" if effect_def.is_percent else ""
            lines.append(f"✦ {effect_def.name} +{value}{suffix}")

        return "\n".join(lines)


def _grade_effect_factor(grade_id: int) -> float:
    """등급에 따른 효과값 스케일링 팩터 (0.0 ~ 1.0)"""
    factors = {
        InstanceGrade.A: 0.0,
        InstanceGrade.S: 0.3,
        InstanceGrade.SS: 0.5,
        InstanceGrade.SSS: 0.75,
        InstanceGrade.MYTHIC: 1.0,
    }
    return factors.get(grade_id, 0.0)
