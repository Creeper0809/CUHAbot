"""
버프/상태이상 기본 클래스 및 등록 시스템
"""
import logging
from typing import Optional

from models import UserStatEnum
from service.dungeon.turn_config import TurnConfig

logger = logging.getLogger(__name__)

# =============================================================================
# 등록 시스템
# =============================================================================

buff_register: dict[str, type] = {}
status_effect_register: dict[str, type] = {}


def register_buff_with_tag(tag: str):
    def decorator(cls):
        buff_register[tag] = cls
        return cls
    return decorator


def register_status_effect(effect_type: str):
    def decorator(cls):
        status_effect_register[effect_type] = cls
        return cls
    return decorator


def get_buff_by_tag(tag: str) -> "Buff":
    return buff_register[tag]()


def get_status_effect_by_type(effect_type: str) -> "StatusEffect":
    return status_effect_register[effect_type]()


# =============================================================================
# Buff 기본 클래스
# =============================================================================


class Buff(TurnConfig):
    """버프/디버프 기본 클래스"""

    def __init__(self):
        self.amount: int = 0
        self.duration: int = 0
        self.buff_type: str = ""
        self.is_debuff: bool = False

    def apply_config(self, config: dict) -> None:
        self.amount = config.get("amount", 0)
        self.duration = config.get("duration", 0)

    def apply_stat(self, stats: dict) -> None:
        """스탯 딕셔너리에 버프 효과 적용"""
        pass

    def tick(self, entity) -> str:
        """매 턴 효과 처리 (DOT 등). 로그 반환."""
        return ""

    def is_expired(self) -> bool:
        return self.duration <= 0

    def decrement_duration(self) -> None:
        self.duration -= 1

    def get_description(self) -> str:
        return "버프"

    def get_emoji(self) -> str:
        return "✨"


# =============================================================================
# StatusEffect 기본 클래스
# =============================================================================


class StatusEffect(Buff):
    """상태이상 기본 클래스"""

    def __init__(self):
        super().__init__()
        self.effect_type: str = ""
        self.stacks: int = 1
        self.max_stacks: int = 99
        self.is_debuff = True

    def can_act(self) -> bool:
        """행동 가능 여부 (CC 체크)"""
        return True

    def add_stacks(self, count: int) -> None:
        """스택 추가 (최대 제한)"""
        self.stacks = min(self.stacks + count, self.max_stacks)

    def get_description(self) -> str:
        stack_text = f" x{self.stacks}" if self.stacks > 1 else ""
        return f"{self.get_emoji()} {self.effect_type}{stack_text} ({self.duration}턴)"
