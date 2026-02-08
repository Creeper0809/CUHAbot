"""
공격 컴포넌트: DamageComponent, LifestealComponent, ConsumeComponent
"""
import random

from config import DAMAGE, get_attribute_multiplier
from models import UserStatEnum
from service.combat.damage_calculator import DamageCalculator
from service.dungeon.components.base import SkillComponent, register_skill_with_tag
from service.dungeon.status import (
    get_status_stacks, get_damage_taken_multiplier, has_curse_effect,
    remove_status_effects,
)


@register_skill_with_tag("attack")
class DamageComponent(SkillComponent):
    """
    공격 데미지 컴포넌트

    DamageCalculator를 사용하여 방어력, 치명타, 데미지 변동을 적용합니다.
    속성 상성 배율도 자동 적용됩니다.

    Config options:
        ad_ratio (float): 물리 공격력 계수 (예: 1.4 = 140% AD)
        ap_ratio (float): 마법 공격력 계수 (예: 1.0 = 100% AP)
        hit_count (int): 타격 횟수 (기본 1)
        crit_bonus (float): 추가 치명타 확률 (기본 0)
        armor_pen (float): 방어력 무시 비율 (기본 0, 최대 0.7)
        is_physical (bool): 물리/마법 데미지 여부 (기본 True=물리)
        aoe (bool): 전체 공격 여부 (기본 False)
    """

    def __init__(self):
        super().__init__()
        self.damage_multiplier = 1.0
        self.ad_ratio = 0.0
        self.ap_ratio = 0.0
        self.hit_count = 1
        self.crit_bonus = 0.0
        self.armor_penetration = 0.0
        self.is_physical = True
        self.is_aoe = False

    def apply_config(self, config, skill_name, priority=0):
        super().apply_config(config, skill_name, priority)
        self.hit_count = config.get("hit_count", 1)
        self.crit_bonus = config.get("crit_bonus", 0.0)
        self.armor_penetration = config.get("armor_pen", 0.0)
        self.is_physical = config.get("is_physical", True)
        self.is_aoe = config.get("aoe", False)

        self.ad_ratio = config.get("ad_ratio", 0.0)
        self.ap_ratio = config.get("ap_ratio", 0.0)

        # 레거시 호환: ad_ratio/ap_ratio 둘 다 없으면 damage를 ad_ratio로 사용
        if self.ad_ratio == 0.0 and self.ap_ratio == 0.0:
            self.ad_ratio = config.get("damage", 1.0)

    def on_turn(self, attacker, target):
        attacker_stat = attacker.get_stat()
        attack_power = self._calculate_base_attack_power(attacker_stat)

        target_stat = target.get_stat() if hasattr(target, 'get_stat') else {}
        defense = self._get_defense(target_stat, target)
        crit_rate = DAMAGE.DEFAULT_CRITICAL_RATE + self.crit_bonus

        # 속성 상성 배율
        target_attr = getattr(target, 'attribute', '무속성')
        attr_mult = get_attribute_multiplier(self.skill_attribute, target_attr)

        # 시너지 배율 (덱 기반)
        synergy_mult = self._get_synergy_multiplier(attacker)

        # 받는 피해 배율 (동결, 표식 등)
        damage_taken_mult = get_damage_taken_multiplier(target)

        combined_mult = attr_mult * synergy_mult * damage_taken_mult

        hit_logs = []
        for _ in range(self.hit_count):
            result = self._calculate_hit(attack_power, defense, crit_rate, combined_mult)
            target.take_damage(result.damage)

            crit_text = " 💥" if result.is_critical else ""
            attr_text = _get_attribute_effectiveness_text(attr_mult)
            hit_logs.append(f"⚔️ **{attacker.get_name()}** 「{self.skill_name}」 → **{result.damage}**{crit_text}{attr_text}")

        return "\n".join(hit_logs)

    def _get_defense(self, target_stat, target) -> int:
        if self.is_physical:
            return target_stat.get(UserStatEnum.DEFENSE, 0) if target_stat else getattr(target, 'defense', 0)
        return target_stat.get(UserStatEnum.AP_DEFENSE, 0) if target_stat else getattr(target, 'ap_defense', 0)

    def _get_synergy_multiplier(self, attacker) -> float:
        if not hasattr(attacker, 'equipped_skill'):
            return 1.0
        from service.skill.synergy_service import SynergyService
        return SynergyService.calculate_damage_multiplier(
            attacker.equipped_skill, self.skill_attribute
        )

    def _calculate_hit(self, attack_power, defense, crit_rate, attribute_multiplier):
        if self.is_physical:
            return DamageCalculator.calculate_physical_damage(
                attack=attack_power, defense=defense,
                skill_multiplier=1.0, armor_penetration=self.armor_penetration,
                critical_rate=crit_rate, attribute_multiplier=attribute_multiplier,
            )
        return DamageCalculator.calculate_magical_damage(
            ap_attack=attack_power, ap_defense=defense,
            skill_multiplier=1.0, magic_penetration=self.armor_penetration,
            critical_rate=crit_rate, attribute_multiplier=attribute_multiplier,
        )


@register_skill_with_tag("lifesteal")
class LifestealComponent(SkillComponent):
    """생명력 흡수 컴포넌트 - 데미지 + 흡혈"""

    def __init__(self):
        super().__init__()
        self.ad_ratio = 1.0
        self.ap_ratio = 0.0
        self.lifesteal = 0.3
        self.hit_count = 1
        self.crit_bonus = 0.0
        self.armor_penetration = 0.0
        self.is_physical = True

    def apply_config(self, config, skill_name, priority=0):
        super().apply_config(config, skill_name, priority)
        self.ad_ratio = config.get("ad_ratio", 0.0)
        self.ap_ratio = config.get("ap_ratio", 0.0)
        self.lifesteal = config.get("lifesteal", 0.3)
        self.hit_count = config.get("hit_count", 1)
        self.crit_bonus = config.get("crit_bonus", 0.0)
        self.armor_penetration = config.get("armor_pen", 0.0)
        self.is_physical = config.get("is_physical", True)

        if self.ad_ratio == 0.0 and self.ap_ratio == 0.0:
            self.ad_ratio = config.get("damage", 1.0)

    def on_turn(self, attacker, target):
        attacker_stat = attacker.get_stat()
        attack_power = self._calculate_base_attack_power(attacker_stat)
        max_hp = attacker_stat.get(UserStatEnum.HP, attacker.hp)

        target_stat = target.get_stat() if hasattr(target, 'get_stat') else {}
        defense = self._get_defense(target_stat, target)
        crit_rate = DAMAGE.DEFAULT_CRITICAL_RATE + self.crit_bonus

        # 속성 배율
        target_attr = getattr(target, 'attribute', '무속성')
        attr_mult = get_attribute_multiplier(self.skill_attribute, target_attr)
        damage_taken_mult = get_damage_taken_multiplier(target)

        hit_logs = []
        total_damage = 0

        for _ in range(self.hit_count):
            result = self._calculate_hit(attack_power, defense, crit_rate, attr_mult * damage_taken_mult)
            target.take_damage(result.damage)
            total_damage += result.damage

            crit_text = " 💥" if result.is_critical else ""
            hit_logs.append(f"🩸 **{attacker.get_name()}** 「{self.skill_name}」 → **{result.damage}**{crit_text}")

        actual_heal = self._apply_lifesteal(attacker, total_damage, max_hp)
        if actual_heal > 0:
            hit_logs.append(f"   💚 흡혈 회복: **+{actual_heal}** HP")

        return "\n".join(hit_logs)

    def _get_defense(self, target_stat, target) -> int:
        if self.is_physical:
            return target_stat.get(UserStatEnum.DEFENSE, 0) if target_stat else getattr(target, 'defense', 0)
        return target_stat.get(UserStatEnum.AP_DEFENSE, 0) if target_stat else getattr(target, 'ap_defense', 0)

    def _calculate_hit(self, attack_power, defense, crit_rate, attribute_multiplier):
        if self.is_physical:
            return DamageCalculator.calculate_physical_damage(
                attack=attack_power, defense=defense,
                skill_multiplier=1.0, armor_penetration=self.armor_penetration,
                critical_rate=crit_rate, attribute_multiplier=attribute_multiplier,
            )
        return DamageCalculator.calculate_magical_damage(
            ap_attack=attack_power, ap_defense=defense,
            skill_multiplier=1.0, magic_penetration=self.armor_penetration,
            critical_rate=crit_rate, attribute_multiplier=attribute_multiplier,
        )

    def _apply_lifesteal(self, attacker, total_damage: int, max_hp: int) -> int:
        heal_amount = int(total_damage * self.lifesteal)
        if has_curse_effect(attacker):
            heal_amount = heal_amount // 2

        old_hp = attacker.now_hp
        attacker.now_hp = min(attacker.now_hp + heal_amount, max_hp)
        return attacker.now_hp - old_hp


@register_skill_with_tag("consume")
class ConsumeComponent(SkillComponent):
    """
    상태이상 소모 컴포넌트 - 스택 소모 후 추가 데미지

    Config options:
        consume_type (str): 소모할 상태이상 타입
        per_stack_ratio (float): 레거시 - 스택당 추가 데미지 비율
        ad_ratio (float): 스택당 물리 공격력 계수
        ap_ratio (float): 스택당 마법 공격력 계수
        base_damage (int): 스택과 관계없는 기본 고정 데미지
        is_physical (bool): 물리/마법 데미지 여부 (방어력 적용)
    """

    def __init__(self):
        super().__init__()
        self.consume_type = ""
        self.per_stack_ratio = 0.0
        self.ad_ratio = 0.0
        self.ap_ratio = 0.0
        self.base_damage = 0
        self.is_physical = True

    def apply_config(self, config, skill_name, priority=0):
        super().apply_config(config, skill_name, priority)
        self.consume_type = config.get("consume_type", "")
        self.per_stack_ratio = config.get("per_stack_ratio", 0.0)
        self.ad_ratio = config.get("ad_ratio", 0.0)
        self.ap_ratio = config.get("ap_ratio", 0.0)
        self.base_damage = config.get("base_damage", 0)
        self.is_physical = config.get("is_physical", True)

    def on_turn(self, attacker, target):
        if not self.consume_type:
            return ""

        stacks = get_status_stacks(target, self.consume_type)
        if stacks == 0:
            return ""

        # 스택 소모
        remove_status_effects(target, count=99, filter_type=self.consume_type)

        bonus_damage = self._calculate_consume_damage(attacker, stacks)
        final_damage = self._apply_defense_reduction(target, bonus_damage)

        target.take_damage(final_damage)
        return f"💥 **{attacker.get_name()}** 「{self.skill_name}」 {self.consume_type} x{stacks} 소모 → **{final_damage}** 추가 데미지!"

    def _calculate_consume_damage(self, attacker, stacks: int) -> int:
        attacker_stat = attacker.get_stat()
        ad = attacker_stat.get(UserStatEnum.ATTACK, 0)
        ap = attacker_stat.get(UserStatEnum.AP_ATTACK, 0)

        # 새 방식: ad_ratio + ap_ratio 별도 계산
        if self.ad_ratio > 0 or self.ap_ratio > 0:
            bonus = self.base_damage
            bonus += int(stacks * self.ad_ratio * ad)
            bonus += int(stacks * self.ap_ratio * ap)
        # 레거시 방식: per_stack_ratio
        else:
            bonus = int(stacks * self.per_stack_ratio * max(ap, ad))

        return max(1, bonus)

    def _apply_defense_reduction(self, target, bonus_damage: int) -> int:
        if self.is_physical:
            defense = target.get_stat().get(UserStatEnum.DEFENSE, 0)
            return max(1, int(bonus_damage * (1 - defense * 0.005)))
        ap_defense = target.get_stat().get(UserStatEnum.AP_DEFENSE, 0)
        return max(1, int(bonus_damage * (1 - ap_defense * 0.005)))


def _get_attribute_effectiveness_text(attr_mult: float) -> str:
    if attr_mult > 1.0:
        return " 🔺효과적!"
    if attr_mult < 1.0:
        return " 🔻비효과적..."
    return ""
