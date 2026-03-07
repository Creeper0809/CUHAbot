"""
지원 컴포넌트: HealComponent, ShieldComponent, CleanseComponent
"""
from models import UserStatEnum
from service.dungeon.components.base import SkillComponent, register_skill_with_tag
from service.dungeon.components.targeting_utils import resolve_targets
from service.dungeon.status import (
    ShieldBuff, has_curse_effect, remove_status_effects, StatusEffect,
)
from service.player.stat_synergy_combat import get_heal_bonus_pct, get_buff_duration_bonus


def _normalize_ratio(value: float | int | None, default: float = 0.0) -> float:
    if value is None:
        return default
    ratio = float(value)
    if abs(ratio) > 1:
        ratio /= 100.0
    return ratio


def _heal_received_multiplier(entity) -> float:
    """Apply heal_received buffs/debuffs if present."""
    multiplier = 1.0
    for status in getattr(entity, "status", []):
        if getattr(status, "buff_type", "") != "heal_received":
            continue
        amount = float(getattr(status, "amount", 0.0))
        multiplier *= max(0.0, 1.0 + amount)
    return max(0.0, multiplier)


@register_skill_with_tag("heal")
class HealComponent(SkillComponent):
    """
    회복 컴포넌트

    Config options:
        percent (float): 최대 HP 비율 회복 (예: 0.15 = 15%)
        ad_ratio (float): AD 기반 회복
        ap_ratio (float): AP 기반 회복
        flat (int): 고정 회복량
    """

    def __init__(self):
        super().__init__()
        self.percent = 0.0
        self.ad_ratio = 0.0
        self.ap_ratio = 0.0
        self.flat = 0
        self.target_type = "self"

    def apply_config(self, config, skill_name, priority=0):
        super().apply_config(config, skill_name, priority)
        self.percent = _normalize_ratio(
            config.get("percent", config.get("heal_percent", 0.0))
        )
        self.ad_ratio = config.get("ad_ratio", 0.0)
        self.ap_ratio = config.get("ap_ratio", 0.0)
        self.flat = int(config.get("flat", config.get("base_amount", 0)))
        self.target_type = config.get("target", "self")

        if "amount" in config and self.percent == 0.0:
            self.percent = _normalize_ratio(config.get("amount"), 0.15)

        if self.percent == 0.0 and self.ad_ratio == 0.0 and self.ap_ratio == 0.0 and self.flat == 0:
            self.percent = 0.15

    def on_turn(self, attacker, target):
        attacker_stat = attacker.get_stat()
        ad = attacker_stat.get(UserStatEnum.ATTACK, 0)
        ap = attacker_stat.get(UserStatEnum.AP_ATTACK, 0)
        targets = resolve_targets(attacker, target, self.target_type)

        if not targets:
            return f"💚 **{attacker.get_name()}** 「{self.skill_name}」 → 회복 대상 없음"

        # 시전자 기준 배율은 한번만 계산
        synergy_mult = 1.0
        if hasattr(attacker, "equipped_skill"):
            from service.skill.synergy_service import SynergyService
            synergy_mult = SynergyService.calculate_heal_multiplier(
                attacker.equipped_skill, actor=attacker, current_skill=self.skill
            )

        heal_bonus_mult = 1.0 + (get_heal_bonus_pct(attacker) / 100.0)
        results = []

        for each in targets:
            max_hp = each.get_stat().get(UserStatEnum.HP, each.hp)
            total_heal = int(max_hp * self.percent) + int(ad * self.ad_ratio) + int(ap * self.ap_ratio) + self.flat
            total_heal = int(total_heal * synergy_mult * heal_bonus_mult)

            # 저주 효과 시 회복량 감소
            if has_curse_effect(each):
                total_heal //= 2

            # heal_received 버프/디버프 반영
            total_heal = int(total_heal * _heal_received_multiplier(each))
            if total_heal <= 0:
                results.append(f"**{each.get_name()}** +0")
                continue

            old_hp = each.now_hp
            each.now_hp = min(each.now_hp + total_heal, max_hp)
            actual_heal = each.now_hp - old_hp
            results.append(f"**{each.get_name()}** +{actual_heal}")

        return f"💚 **{attacker.get_name()}** 「{self.skill_name}」 → " + ", ".join(results) + " HP"


@register_skill_with_tag("shield")
class ShieldComponent(SkillComponent):
    """
    보호막 컴포넌트

    Config options:
        percent (float): 최대 HP 비율 보호막 (예: 0.2 = 20%)
        duration (int): 보호막 지속 턴
        flat (int): 고정 보호막량
    """

    def __init__(self):
        super().__init__()
        self.percent = 0.0
        self.shield_duration = 3
        self.flat = 0
        self.target_type = "self"

    def apply_config(self, config, skill_name, priority=0):
        super().apply_config(config, skill_name, priority)
        self.percent = _normalize_ratio(config.get("percent", 0.2), 0.2)
        self.shield_duration = config.get("duration", 3)
        self.flat = config.get("flat", 0)
        self.target_type = config.get("target", "self")

    def on_turn(self, attacker, target):
        targets = resolve_targets(attacker, target, self.target_type)
        if not targets:
            return f"🛡️ **{attacker.get_name()}** 「{self.skill_name}」 → 보호막 대상 없음"

        duration = self.shield_duration + get_buff_duration_bonus(attacker)
        applied = []

        for each in targets:
            max_hp = each.get_stat().get(UserStatEnum.HP, each.hp)
            shield_amount = max(1, int(max_hp * self.percent) + self.flat)
            shield = ShieldBuff()
            shield.shield_hp = shield_amount
            shield.duration = duration
            each.status.append(shield)
            applied.append(f"**{each.get_name()}** {shield_amount}")

        return f"🛡️ **{attacker.get_name()}** 「{self.skill_name}」 → " + ", ".join(applied)


@register_skill_with_tag("cleanse")
class CleanseComponent(SkillComponent):
    """
    정화 컴포넌트 - 디버프/상태이상 제거

    Config options:
        count (int): 제거할 개수 (99 = 모두)
    """

    def __init__(self):
        super().__init__()
        self.count = 99
        self.target_type = "self"

    def apply_config(self, config, skill_name, priority=0):
        super().apply_config(config, skill_name, priority)
        self.count = config.get("count", 99)
        self.target_type = config.get("target", "self")

    @staticmethod
    def _remove_positive_buffs(entity, count: int) -> str:
        removed = []
        remaining = []
        for status in entity.status:
            is_status_effect = isinstance(status, StatusEffect)
            is_debuff = getattr(status, "is_debuff", False)
            is_positive_buff = (not is_status_effect) and (not is_debuff)
            if is_positive_buff and len(removed) < count:
                removed.append(status)
            else:
                remaining.append(status)

        entity.status = remaining
        if not removed:
            return ""

        names = ", ".join(getattr(buff, "buff_type", "버프") for buff in removed)
        return f"✨ **{entity.get_name()}** {names} 해제!"

    def on_turn(self, attacker, target):
        targets = resolve_targets(attacker, target, self.target_type)
        if not targets:
            return f"✨ **{attacker.get_name()}** 「{self.skill_name}」 → 대상 없음"

        enemy_dispel = self.target_type in {"enemy", "all_enemies", "all_enemy", "enemies", "all"}
        results = []
        for each in targets:
            if enemy_dispel:
                result = self._remove_positive_buffs(each, self.count)
            else:
                result = remove_status_effects(each, count=self.count, filter_debuff=True)

            if result:
                results.append(result)

        if not results:
            return f"✨ **{attacker.get_name()}** 「{self.skill_name}」 → 제거할 효과 없음"
        return f"✨ **{attacker.get_name()}** 「{self.skill_name}」\n" + "\n".join(results)
