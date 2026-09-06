"""Named status effects used by authored V3 skills.

These used to be accepted by the CSV loader but silently discarded because no
runtime status class was registered.  Keeping them as named effects also avoids
hard-coding individual skill IDs in the combat engine.
"""

from models import UserStatEnum
from service.dungeon.status.base import StatusEffect, register_status_effect


def _maximum_hp(entity) -> int:
    stats = entity.get_stat() if hasattr(entity, "get_stat") else {}
    return max(1, int(stats.get(UserStatEnum.HP, getattr(entity, "hp", 1))))


@register_status_effect("fear")
class FearEffect(StatusEffect):
    """공포: 지속시간 동안 행동할 수 없다."""

    def __init__(self):
        super().__init__()
        self.effect_type = "fear"
        self.max_stacks = 1

    def can_act(self) -> bool:
        return False

    def get_emoji(self) -> str:
        return "😱"


@register_status_effect("root")
class RootEffect(StatusEffect):
    """속박: 지속시간 동안 행동할 수 없다."""

    def __init__(self):
        super().__init__()
        self.effect_type = "root"
        self.max_stacks = 1

    def can_act(self) -> bool:
        return False

    def get_emoji(self) -> str:
        return "🌿"


@register_status_effect("charm")
class CharmEffect(StatusEffect):
    """매혹: 지속시간 동안 행동할 수 없다."""

    def __init__(self):
        super().__init__()
        self.effect_type = "charm"
        self.max_stacks = 1

    def can_act(self) -> bool:
        return False

    def get_emoji(self) -> str:
        return "💞"


@register_status_effect("blind")
class BlindEffect(StatusEffect):
    """실명: 기본 명중률을 30%p 낮춘다."""

    def __init__(self):
        super().__init__()
        self.effect_type = "blind"
        self.max_stacks = 1

    def apply_stat(self, stats: dict) -> None:
        stats[UserStatEnum.ACCURACY] = max(0, stats.get(UserStatEnum.ACCURACY, 0) - 30)

    def get_emoji(self) -> str:
        return "🌑"


@register_status_effect("taunt")
class TauntEffect(StatusEffect):
    """도발: 공격 대상을 이 효과를 건 생존 엔티티로 고정한다."""

    def __init__(self):
        super().__init__()
        self.effect_type = "taunt"
        self.max_stacks = 1

    def get_emoji(self) -> str:
        return "💢"


@register_status_effect("blessing")
class BlessingEffect(StatusEffect):
    """축복 표식: 연계 소비기가 확인하는 이로운 상태."""

    def __init__(self):
        super().__init__()
        self.effect_type = "blessing"
        self.max_stacks = 5
        self.is_debuff = False

    def get_emoji(self) -> str:
        return "✨"


@register_status_effect("dot")
class TimedDamageEffect(StatusEffect):
    """설정값 기반 지속 피해."""

    def __init__(self):
        super().__init__()
        self.effect_type = "dot"
        self.max_stacks = 1
        self.damage_type = "max_hp_percent"
        self.value = 0.0

    def tick(self, entity) -> str:
        if self.damage_type == "current_hp_percent":
            damage = int(max(1, getattr(entity, "now_hp", 1)) * self.value)
        elif self.damage_type == "fixed":
            damage = int(self.value)
        else:
            damage = int(_maximum_hp(entity) * self.value)
        damage = max(1, damage) * max(1, self.stacks)
        actual = entity.take_damage(damage)
        return f"🌫️ **{entity.get_name()}** 지속 피해! **-{actual}** HP"

    def get_emoji(self) -> str:
        return "🌫️"


@register_status_effect("death_mark")
class DeathMarkEffect(StatusEffect):
    """죽음의 낙인: 마지막 틱에 대상을 쓰러뜨린다. 정화 가능."""

    def __init__(self):
        super().__init__()
        self.effect_type = "death_mark"
        self.max_stacks = 1

    def tick(self, entity) -> str:
        if self.duration > 1:
            return f"💀 **{entity.get_name()}** 죽음의 낙인 발동까지 {self.duration - 1}턴"
        actual = entity.take_damage(max(1, getattr(entity, "now_hp", 1)))
        return f"💀 **{entity.get_name()}** 죽음의 낙인 발동! **-{actual}** HP"

    def get_emoji(self) -> str:
        return "💀"


@register_status_effect("skill_seal")
class SkillSealEffect(StatusEffect):
    """스킬 봉인: 덱 스킬 대신 기본 공격만 사용할 수 있다."""

    def __init__(self):
        super().__init__()
        self.effect_type = "skill_seal"
        self.max_stacks = 1

    def get_emoji(self) -> str:
        return "🔒"


@register_status_effect("self_destruct")
class SelfDestructMarkEffect(StatusEffect):
    """자폭 표식: 마지막 틱에 설정된 최대 HP 비율 피해를 준다."""

    def __init__(self):
        super().__init__()
        self.effect_type = "self_destruct"
        self.max_stacks = 1
        self.value = 1.0

    def tick(self, entity) -> str:
        if self.duration > 1:
            return f"💣 **{entity.get_name()}** 자폭까지 {self.duration - 1}턴"
        damage = max(1, int(_maximum_hp(entity) * self.value))
        actual = entity.take_damage(damage)
        return f"💥 **{entity.get_name()}** 자폭! **-{actual}** HP"

    def get_emoji(self) -> str:
        return "💣"
