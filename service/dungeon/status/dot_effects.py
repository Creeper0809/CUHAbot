"""
DOT 상태이상 (Damage over Time): 화상, 독, 출혈, 잠식
"""
from config import STATUS_EFFECT
from models import UserStatEnum
from service.dungeon.status.base import StatusEffect, register_status_effect


@register_status_effect("burn")
class BurnEffect(StatusEffect):
    """화상: 매 턴 최대 HP의 3% × 스택 데미지"""

    def __init__(self):
        super().__init__()
        self.effect_type = "burn"
        self.max_stacks = STATUS_EFFECT.BURN_MAX_STACKS

    def tick(self, entity) -> str:
        # User는 get_stat()으로 최대 HP 조회, Monster는 hp 필드가 최대 HP
        from models.users import User
        if isinstance(entity, User):
            max_hp = entity.get_stat().get(UserStatEnum.HP, entity.hp)
        else:
            max_hp = entity.hp

        damage = int(max_hp * STATUS_EFFECT.BURN_DAMAGE_PERCENT * self.stacks)
        damage = max(1, damage)
        entity.take_damage(damage)
        return f"🔥 **{entity.get_name()}** 화상! **-{damage}** HP"

    def get_emoji(self) -> str:
        return "🔥"


@register_status_effect("poison")
class PoisonEffect(StatusEffect):
    """독: 매 턴 최대 HP의 2% × 스택 데미지"""

    def __init__(self):
        super().__init__()
        self.effect_type = "poison"
        self.max_stacks = STATUS_EFFECT.POISON_MAX_STACKS
        self.damage_bonus = 0.0

    def tick(self, entity) -> str:
        # User는 get_stat()으로 최대 HP 조회, Monster는 hp 필드가 최대 HP
        from models.users import User
        if isinstance(entity, User):
            max_hp = entity.get_stat().get(UserStatEnum.HP, entity.hp)
        else:
            max_hp = entity.hp

        damage = int(max_hp * STATUS_EFFECT.POISON_DAMAGE_PERCENT * self.stacks * (1.0 + self.damage_bonus))
        damage = max(1, damage)
        entity.take_damage(damage)
        return f"☠️ **{entity.get_name()}** 중독! **-{damage}** HP"

    def get_emoji(self) -> str:
        return "☠️"


@register_status_effect("bleed")
class BleedEffect(StatusEffect):
    """출혈: 매 턴 최대 HP의 4% 데미지"""

    def __init__(self):
        super().__init__()
        self.effect_type = "bleed"
        self.max_stacks = 1

    def tick(self, entity) -> str:
        # User는 get_stat()으로 최대 HP 조회, Monster는 hp 필드가 최대 HP
        from models.users import User
        if isinstance(entity, User):
            max_hp = entity.get_stat().get(UserStatEnum.HP, entity.hp)
        else:
            max_hp = entity.hp

        damage = int(max_hp * STATUS_EFFECT.BLEED_DAMAGE_PERCENT)
        damage = max(1, damage)
        entity.take_damage(damage)
        return f"🩸 **{entity.get_name()}** 출혈! **-{damage}** HP"

    def get_emoji(self) -> str:
        return "🩸"


@register_status_effect("erode")
class ErodeEffect(StatusEffect):
    """잠식: 스택당 방어력 감소"""

    DEFENSE_REDUCTION_PER_STACK: int = 5

    def __init__(self):
        super().__init__()
        self.effect_type = "erode"
        self.max_stacks = 10

    def apply_stat(self, stats: dict) -> None:
        reduction = self.DEFENSE_REDUCTION_PER_STACK * self.stacks
        stats[UserStatEnum.DEFENSE] = max(0, stats[UserStatEnum.DEFENSE] - reduction)
        stats[UserStatEnum.AP_DEFENSE] = max(0, stats[UserStatEnum.AP_DEFENSE] - reduction)

    def tick(self, entity) -> str:
        return f"💀 **{entity.get_name()}** 잠식! 방어력 -{self.DEFENSE_REDUCTION_PER_STACK * self.stacks}"

    def get_emoji(self) -> str:
        return "💀"
