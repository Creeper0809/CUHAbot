"""Named V3 mechanics backed by shared CombatRuntimeState."""
from models import UserStatEnum
from service.combat.runtime_damage import deal_runtime_damage
from service.dungeon.components.base import SkillComponent, register_skill_with_tag
from service.dungeon.status import apply_status_effect, get_status_stacks, remove_status_effects
from utils.game_text import status_label


def _entity_state(entity):
    runtime = getattr(entity, "combat_runtime_state", None)
    if runtime is None:
        from service.dungeon.combat_runtime_state import CombatRuntimeState

        runtime = CombatRuntimeState()
        runtime.bind(entity)
    return runtime, runtime.for_entity(entity)


@register_skill_with_tag("combat_resource")
class CombatResourceComponent(SkillComponent):
    """Generate a named, combat-local resource without touching global skill data."""

    def __init__(self):
        super().__init__()
        self.resource = ""
        self.amount = 1
        self.maximum = 5

    def apply_config(self, config, skill_name, priority=0):
        super().apply_config(config, skill_name, priority)
        self.resource = str(config.get("resource", ""))
        self.amount = max(1, int(config.get("amount", 1) or 1))
        self.maximum = max(self.amount, int(config.get("maximum", 5) or 5))

    def on_turn(self, attacker, target):
        if not self.resource:
            return ""
        runtime, state = _entity_state(attacker)
        total = state.add_resource(self.resource, self.amount, self.maximum)
        runtime.record(
            "combat_resource_gained", entity_id=getattr(attacker, "id", None),
            resource=self.resource, amount=self.amount, total=total,
        )
        return f"🔹 **{attacker.get_name()}** {self.resource} +{self.amount} ({total}/{self.maximum})"


@register_skill_with_tag("resource_payoff")
class ResourcePayoffComponent(SkillComponent):
    """Spend a named resource for an optional payoff; failure is a clean no-op."""

    def __init__(self):
        super().__init__()
        self.resource = ""
        self.cost = 1
        self.ad_ratio = 0.0
        self.ap_ratio = 0.0
        self.is_physical = True
        self.heal_percent = 0.0

    def apply_config(self, config, skill_name, priority=0):
        super().apply_config(config, skill_name, priority)
        self.resource = str(config.get("resource", ""))
        self.cost = max(1, int(config.get("cost", 1) or 1))
        self.ad_ratio = max(0.0, float(config.get("ad_ratio", 0.0) or 0.0))
        self.ap_ratio = max(0.0, float(config.get("ap_ratio", 0.0) or 0.0))
        self.is_physical = bool(config.get("is_physical", self.ad_ratio >= self.ap_ratio))
        self.heal_percent = max(0.0, float(config.get("heal_percent", 0.0) or 0.0))

    def on_turn(self, attacker, target):
        if not self.resource:
            return ""
        runtime, state = _entity_state(attacker)
        if not state.spend_resource(self.resource, self.cost):
            runtime.record(
                "combat_resource_payoff_missed", entity_id=getattr(attacker, "id", None),
                resource=self.resource, required=self.cost,
            )
            return ""
        stats = attacker.get_stat()
        if self.heal_percent:
            maximum_hp = max(1, int(stats.get(UserStatEnum.HP, getattr(attacker, "hp", 1)) or 1))
            old_hp = int(getattr(attacker, "now_hp", maximum_hp))
            attacker.now_hp = min(maximum_hp, old_hp + int(maximum_hp * self.heal_percent))
            healed = attacker.now_hp - old_hp
            runtime.record(
                "combat_resource_spent", entity_id=getattr(attacker, "id", None),
                resource=self.resource, amount=self.cost, healing=healed,
            )
            return f"🔷 **{attacker.get_name()}** {self.resource} {self.cost} 소비 → HP {healed} 추가 회복"
        raw = int(
            stats.get(UserStatEnum.ATTACK, 0) * self.ad_ratio
            + stats.get(UserStatEnum.AP_ATTACK, 0) * self.ap_ratio
        )
        event = deal_runtime_damage(
            attacker, target, max(1, raw), is_physical=self.is_physical,
            attribute=self.skill_attribute,
        ).event
        runtime.record(
            "combat_resource_spent", entity_id=getattr(attacker, "id", None),
            resource=self.resource, amount=self.cost, damage=event.actual_damage,
        )
        return (
            f"🔷 **{attacker.get_name()}** {self.resource} {self.cost} 소비 → "
            f"**{target.get_name()}** {event.actual_damage} 추가 피해"
        )


@register_skill_with_tag("status_transform")
class StatusTransformComponent(SkillComponent):
    """Convert one named status into another through config, never skill-ID checks."""

    def __init__(self):
        super().__init__()
        self.from_status = ""
        self.to_status = ""
        self.minimum = 1
        self.duration = 1
        self.consume_all = True

    def apply_config(self, config, skill_name, priority=0):
        super().apply_config(config, skill_name, priority)
        self.from_status = str(config.get("from_status", ""))
        self.to_status = str(config.get("to_status", ""))
        self.minimum = max(1, int(config.get("minimum", 1) or 1))
        self.duration = max(1, int(config.get("duration", 1) or 1))
        self.consume_all = bool(config.get("consume_all", True))

    def on_turn(self, attacker, target):
        stacks = get_status_stacks(target, self.from_status)
        if not self.from_status or not self.to_status or stacks < self.minimum:
            return ""
        if self.consume_all:
            remove_status_effects(target, count=99, filter_type=self.from_status)
        applied = apply_status_effect(target, self.to_status, stacks=1, duration=self.duration)
        runtime = getattr(attacker, "combat_runtime_state", None)
        if runtime is not None:
            runtime.record(
                "status_transformed", skill_id=getattr(self.skill, "id", None),
                from_status=self.from_status, to_status=self.to_status, stacks=stacks,
            )
        return f"🔁 {status_label(self.from_status)} x{stacks} → {status_label(self.to_status)}\n{applied}"
