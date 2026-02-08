"""
지원 컴포넌트: HealComponent, ShieldComponent, CleanseComponent
"""
from models import UserStatEnum
from service.dungeon.components.base import SkillComponent, register_skill_with_tag
from service.dungeon.status import (
    ShieldBuff, has_curse_effect, remove_status_effects,
)


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

    def apply_config(self, config, skill_name, priority=0):
        super().apply_config(config, skill_name, priority)
        self.percent = config.get("percent", 0.0)
        self.ad_ratio = config.get("ad_ratio", 0.0)
        self.ap_ratio = config.get("ap_ratio", 0.0)
        self.flat = config.get("flat", 0)

        if "amount" in config and self.percent == 0.0:
            self.percent = config.get("amount", 0.15)

        if self.percent == 0.0 and self.ad_ratio == 0.0 and self.ap_ratio == 0.0 and self.flat == 0:
            self.percent = 0.15

    def on_turn(self, attacker, target):
        attacker_stat = attacker.get_stat()
        max_hp = attacker_stat.get(UserStatEnum.HP, attacker.hp)
        ad = attacker_stat.get(UserStatEnum.ATTACK, 0)
        ap = attacker_stat.get(UserStatEnum.AP_ATTACK, 0)

        total_heal = int(max_hp * self.percent) + int(ad * self.ad_ratio) + int(ap * self.ap_ratio) + self.flat

        # 시너지 배율 (덱 기반)
        if hasattr(attacker, 'equipped_skill'):
            from service.skill.synergy_service import SynergyService
            synergy_mult = SynergyService.calculate_heal_multiplier(attacker.equipped_skill)
            total_heal = int(total_heal * synergy_mult)

        # 저주 효과 시 회복량 50% 감소
        if has_curse_effect(attacker):
            total_heal = total_heal // 2

        old_hp = attacker.now_hp
        attacker.now_hp = min(attacker.now_hp + total_heal, max_hp)
        actual_heal = attacker.now_hp - old_hp

        return f"💚 **{attacker.get_name()}** 「{self.skill_name}」 → **+{actual_heal}** HP"


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

    def apply_config(self, config, skill_name, priority=0):
        super().apply_config(config, skill_name, priority)
        self.percent = config.get("percent", 0.2)
        self.shield_duration = config.get("duration", 3)
        self.flat = config.get("flat", 0)

    def on_turn(self, attacker, target):
        max_hp = attacker.hp
        shield_amount = max(1, int(max_hp * self.percent) + self.flat)

        shield = ShieldBuff()
        shield.shield_hp = shield_amount
        shield.duration = self.shield_duration
        attacker.status.append(shield)

        return f"🛡️ **{attacker.get_name()}** 「{self.skill_name}」 → 보호막 **{shield_amount}**!"


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

    def apply_config(self, config, skill_name, priority=0):
        super().apply_config(config, skill_name, priority)
        self.count = config.get("count", 99)

    def on_turn(self, attacker, target):
        result = remove_status_effects(attacker, count=self.count, filter_debuff=True)
        if not result:
            return f"✨ **{attacker.get_name()}** 「{self.skill_name}」 → 제거할 상태이상 없음"
        return f"✨ **{attacker.get_name()}** 「{self.skill_name}」 → {result}"
