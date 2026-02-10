"""
미니게임 매니저

모든 미니게임을 관리하고 랜덤 선택 기능 제공
"""
import random
from typing import Optional

from .base_minigame import BaseMinigame
from .timing_game import TimingGame
from .sequence_game import SequenceGame
from .reaction_game import ReactionGame
from .rps_game import RPSGame
from .typing_game import TypingGame
from .math_game import MathGame
from .memory_card_game import MemoryCardGame


class MinigameManager:
    """미니게임 매니저"""

    # 사용 가능한 모든 미니게임
    MINIGAMES = {
        "timing": TimingGame,
        "sequence": SequenceGame,
        "reaction": ReactionGame,
        "rps": RPSGame,
        "typing": TypingGame,
        "math": MathGame,
        "memory": MemoryCardGame,
    }

    @classmethod
    def get_minigame(cls, name: str, difficulty: int = 1) -> Optional[BaseMinigame]:
        """
        미니게임 가져오기

        Args:
            name: 미니게임 이름
            difficulty: 난이도 (1~5)

        Returns:
            미니게임 인스턴스 또는 None
        """
        game_class = cls.MINIGAMES.get(name)
        if not game_class:
            return None
        return game_class(difficulty=difficulty)

    @classmethod
    def get_random_minigame(cls, difficulty: int = 1) -> BaseMinigame:
        """
        랜덤 미니게임 가져오기

        Args:
            difficulty: 난이도 (1~5)

        Returns:
            랜덤 미니게임 인스턴스
        """
        game_class = random.choice(list(cls.MINIGAMES.values()))
        return game_class(difficulty=difficulty)

    @classmethod
    def list_minigames(cls) -> list[str]:
        """사용 가능한 미니게임 목록 반환"""
        return list(cls.MINIGAMES.keys())

    @classmethod
    def get_minigame_info(cls, name: str) -> Optional[dict]:
        """
        미니게임 정보 가져오기

        Args:
            name: 미니게임 이름

        Returns:
            미니게임 정보 딕셔너리
        """
        game_class = cls.MINIGAMES.get(name)
        if not game_class:
            return None

        instance = game_class()
        return {
            "name": instance.name,
            "description": instance.description,
            "timeout": instance.timeout,
        }
