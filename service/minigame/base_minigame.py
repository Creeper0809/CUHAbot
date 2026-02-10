"""
미니게임 베이스 클래스

모든 미니게임은 이 클래스를 상속받아 구현합니다.
"""
import discord
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class MinigameResult:
    """미니게임 결과"""
    success: bool
    """성공 여부"""

    score: int
    """점수 (0-100)"""

    time_taken: float
    """소요 시간 (초)"""

    bonus_damage: float = 0.0
    """보너스 데미지 배율 (성공 시)"""

    penalty_damage: float = 0.0
    """패널티 데미지 (실패 시, 플레이어가 받는 추가 데미지)"""

    message: str = ""
    """결과 메시지"""


class BaseMinigame(ABC):
    """
    미니게임 베이스 클래스

    모든 미니게임은 이 클래스를 상속받아 구현합니다.
    """

    def __init__(self):
        self.name = "Unknown Game"
        self.description = "설명 없음"
        self.difficulty = 1  # 1~5
        self.timeout = 10.0  # 제한 시간 (초)

    @abstractmethod
    async def start(
        self,
        interaction: discord.Interaction,
        **kwargs
    ) -> MinigameResult:
        """
        미니게임 시작

        Args:
            interaction: Discord 인터랙션
            **kwargs: 추가 파라미터 (보스 정보 등)

        Returns:
            MinigameResult: 게임 결과
        """
        pass

    def calculate_bonus_damage(self, score: int, time_taken: float) -> float:
        """
        점수와 시간을 기반으로 보너스 데미지 배율 계산

        Args:
            score: 점수 (0-100)
            time_taken: 소요 시간

        Returns:
            보너스 데미지 배율 (0.0 ~ 1.0)
        """
        # 점수 기반 보너스
        score_bonus = score / 100.0

        # 시간 기반 보너스 (빠를수록 높음)
        time_bonus = max(0, 1.0 - (time_taken / self.timeout))

        # 최종 보너스 (평균)
        return (score_bonus + time_bonus) / 2.0

    def calculate_penalty_damage(self, boss_attack: int) -> int:
        """
        실패 시 패널티 데미지 계산

        Args:
            boss_attack: 보스 공격력

        Returns:
            패널티 데미지
        """
        return int(boss_attack * 0.5)  # 보스 공격력의 50%
