"""
CC 상태이상 (Crowd Control): 둔화, 동결, 기절, 마비
"""
from config import STATUS_EFFECT
from models import UserStatEnum
from service.dungeon.status.base import StatusEffect, register_status_effect


@register_status_effect("slow")
class SlowEffect(StatusEffect):
    """둔화: 속도 30% 감소"""

    def __init__(self):
        super().__init__()
        self.effect_type = "slow"
        self.max_stacks = 1

    def apply_stat(self, stats: dict) -> None:
        reduction = int(stats[UserStatEnum.SPEED] * STATUS_EFFECT.SLOW_SPEED_REDUCTION)
        stats[UserStatEnum.SPEED] = max(1, stats[UserStatEnum.SPEED] - reduction)

    def get_emoji(self) -> str:
        return "🐌"


@register_status_effect("freeze")
class FreezeEffect(StatusEffect):
    """동결: 행동 불가 + 받는 피해 20% 증가"""

    def __init__(self):
        super().__init__()
        self.effect_type = "freeze"
        self.max_stacks = 1

    def can_act(self) -> bool:
        return False

    def get_emoji(self) -> str:
        return "❄️"


@register_status_effect("stun")
class StunEffect(StatusEffect):
    """기절: 행동 불가"""

    def __init__(self):
        super().__init__()
        self.effect_type = "stun"
        self.max_stacks = 1

    def can_act(self) -> bool:
        return False

    def get_emoji(self) -> str:
        return "💫"


@register_status_effect("paralyze")
class ParalyzeEffect(StatusEffect):
    """마비: 행동 불가"""

    def __init__(self):
        super().__init__()
        self.effect_type = "paralyze"
        self.max_stacks = 1

    def can_act(self) -> bool:
        return False

    def get_emoji(self) -> str:
        return "⚡"
