"""
스탯 버프 클래스들 (공격력, 방어력, 속도 등) 및 보호막
"""
from models import UserStatEnum
from service.dungeon.status.base import Buff, register_buff_with_tag


@register_buff_with_tag("attack")
class AttackBuff(Buff):
    def __init__(self):
        super().__init__()
        self.buff_type = "attack"

    def apply_stat(self, stats: dict) -> None:
        stats[UserStatEnum.ATTACK] += self.amount

    def get_description(self) -> str:
        sign = "+" if self.amount > 0 else ""
        return f"⚔️ 공격력 {sign}{self.amount} ({self.duration}턴)"

    def get_emoji(self) -> str:
        return "⚔️"


@register_buff_with_tag("defense")
class DefenseBuff(Buff):
    def __init__(self):
        super().__init__()
        self.buff_type = "defense"

    def apply_stat(self, stats: dict) -> None:
        stats[UserStatEnum.DEFENSE] += self.amount

    def get_description(self) -> str:
        sign = "+" if self.amount > 0 else ""
        return f"🛡️ 방어력 {sign}{self.amount} ({self.duration}턴)"

    def get_emoji(self) -> str:
        return "🛡️"


@register_buff_with_tag("speed")
class SpeedBuff(Buff):
    def __init__(self):
        super().__init__()
        self.buff_type = "speed"

    def apply_stat(self, stats: dict) -> None:
        stats[UserStatEnum.SPEED] += self.amount

    def get_description(self) -> str:
        sign = "+" if self.amount > 0 else ""
        return f"💨 속도 {sign}{self.amount} ({self.duration}턴)"

    def get_emoji(self) -> str:
        return "💨"


@register_buff_with_tag("ap_attack")
class ApAttackBuff(Buff):
    def __init__(self):
        super().__init__()
        self.buff_type = "ap_attack"

    def apply_stat(self, stats: dict) -> None:
        stats[UserStatEnum.AP_ATTACK] += self.amount

    def get_description(self) -> str:
        sign = "+" if self.amount > 0 else ""
        return f"🔮 마공 {sign}{self.amount} ({self.duration}턴)"

    def get_emoji(self) -> str:
        return "🔮"


@register_buff_with_tag("ap_defense")
class ApDefenseBuff(Buff):
    def __init__(self):
        super().__init__()
        self.buff_type = "ap_defense"

    def apply_stat(self, stats: dict) -> None:
        stats[UserStatEnum.AP_DEFENSE] += self.amount

    def get_description(self) -> str:
        sign = "+" if self.amount > 0 else ""
        return f"🌀 마방 {sign}{self.amount} ({self.duration}턴)"

    def get_emoji(self) -> str:
        return "🌀"


@register_buff_with_tag("shield")
class ShieldBuff(Buff):
    """보호막: 데미지를 흡수"""

    def __init__(self):
        super().__init__()
        self.buff_type = "shield"
        self.shield_hp: int = 0

    def apply_config(self, config: dict) -> None:
        super().apply_config(config)
        self.shield_hp = config.get("shield_hp", 0)

    def absorb_damage(self, damage: int) -> tuple[int, int]:
        """
        보호막으로 데미지 흡수

        Returns:
            (실제 피해, 흡수된 피해)
        """
        absorbed = min(damage, self.shield_hp)
        self.shield_hp -= absorbed
        remaining = damage - absorbed
        if self.shield_hp <= 0:
            self.duration = 0
        return remaining, absorbed

    def get_description(self) -> str:
        return f"🛡️ 보호막 {self.shield_hp} ({self.duration}턴)"

    def get_emoji(self) -> str:
        return "🛡️"
