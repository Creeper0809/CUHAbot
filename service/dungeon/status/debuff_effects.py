"""
디버프 상태이상: 저주, 표식, 침수, 감전, 감염, 콤보
"""
from models import UserStatEnum
from service.dungeon.status.base import StatusEffect, register_status_effect


@register_status_effect("curse")
class CurseEffect(StatusEffect):
    """저주: 회복량 -50%, 방어력 -20%"""

    def __init__(self):
        super().__init__()
        self.effect_type = "curse"
        self.max_stacks = 1

    def apply_stat(self, stats: dict) -> None:
        reduction = int(stats[UserStatEnum.DEFENSE] * 0.2)
        stats[UserStatEnum.DEFENSE] = max(0, stats[UserStatEnum.DEFENSE] - reduction)

    def get_emoji(self) -> str:
        return "👿"


@register_status_effect("mark")
class MarkEffect(StatusEffect):
    """표식: 받는 피해 증가"""

    def __init__(self):
        super().__init__()
        self.effect_type = "mark"
        self.max_stacks = 1

    def get_emoji(self) -> str:
        return "🎯"


@register_status_effect("submerge")
class SubmergeEffect(StatusEffect):
    """침수: 번개 피해 2배"""

    def __init__(self):
        super().__init__()
        self.effect_type = "submerge"
        self.max_stacks = 1

    def get_emoji(self) -> str:
        return "🌊"


@register_status_effect("shock")
class ShockEffect(StatusEffect):
    """감전: 번개 체인용"""

    def __init__(self):
        super().__init__()
        self.effect_type = "shock"
        self.max_stacks = 1

    def get_emoji(self) -> str:
        return "⚡"


@register_status_effect("infection")
class InfectionEffect(StatusEffect):
    """감염: 디버프 전파"""

    def __init__(self):
        super().__init__()
        self.effect_type = "infection"
        self.max_stacks = 1

    def get_emoji(self) -> str:
        return "🦠"


@register_status_effect("combo")
class ComboEffect(StatusEffect):
    """콤보: 콤보 카운터 스택"""

    def __init__(self):
        super().__init__()
        self.effect_type = "combo"
        self.max_stacks = 10

    def get_emoji(self) -> str:
        return "💥"
