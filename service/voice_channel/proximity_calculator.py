"""
근접도 계산기

exploration_step 차이를 기반으로 사용자 간 거리를 계산합니다.
"""
from enum import IntEnum
from typing import Optional

from config.voice_channel import VOICE_CHANNEL


class ProximityLevel(IntEnum):
    """근접도 레벨 분류"""

    IMMEDIATE = 1
    """즉시 거리 (±3 스텝)"""

    NEARBY = 2
    """근처 거리 (±10 스텝)"""

    FAR = 3
    """먼 거리 (>10 스텝)"""


class ProximityCalculator:
    """
    근접도 계산기

    사용자 간 exploration_step 차이를 기반으로 거리를 계산합니다.
    Phase 1: 기본 계산만 제공
    Phase 2: 비용/보상 배율 계산 추가 예정
    """

    @staticmethod
    def calculate_distance(step_a: int, step_b: int) -> int:
        """
        두 위치 간 거리 계산

        Args:
            step_a: 첫 번째 위치 (exploration_step)
            step_b: 두 번째 위치 (exploration_step)

        Returns:
            스텝 차이 (절댓값)
        """
        return abs(step_a - step_b)

    @staticmethod
    def get_proximity_level(distance: int) -> ProximityLevel:
        """
        거리에 따른 근접도 레벨 분류

        Args:
            distance: 스텝 거리

        Returns:
            ProximityLevel 열거형
        """
        if distance <= VOICE_CHANNEL.PROXIMITY_IMMEDIATE_STEPS:
            return ProximityLevel.IMMEDIATE
        elif distance <= VOICE_CHANNEL.PROXIMITY_NEARBY_STEPS:
            return ProximityLevel.NEARBY
        else:
            return ProximityLevel.FAR

    @staticmethod
    def is_immediate_proximity(distance: int) -> bool:
        """
        즉시 근접 거리인지 확인 (±3 스텝)

        Args:
            distance: 스텝 거리

        Returns:
            즉시 근접이면 True
        """
        return distance <= VOICE_CHANNEL.PROXIMITY_IMMEDIATE_STEPS

    @staticmethod
    def is_nearby_proximity(distance: int) -> bool:
        """
        근처 거리인지 확인 (±10 스텝)

        Args:
            distance: 스텝 거리

        Returns:
            근처 거리면 True
        """
        return distance <= VOICE_CHANNEL.PROXIMITY_NEARBY_STEPS

    @staticmethod
    def is_far_proximity(distance: int) -> bool:
        """
        먼 거리인지 확인 (>10 스텝)

        Args:
            distance: 스텝 거리

        Returns:
            먼 거리면 True
        """
        return distance > VOICE_CHANNEL.PROXIMITY_NEARBY_STEPS
