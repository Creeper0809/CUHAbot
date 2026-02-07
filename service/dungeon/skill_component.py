"""
스킬 컴포넌트 시스템

스킬의 다양한 효과를 컴포넌트 단위로 분리하여 조합합니다.
각 컴포넌트는 턴 기반 콜백을 구현합니다.

스탯 계수 시스템:
- ad_ratio: 물리 공격력(AD) 계수 (예: 1.4 = 140% AD)
- ap_ratio: 마법 공격력(AP) 계수 (예: 1.0 = 100% AP)
- 하이브리드 스킬은 두 계수 모두 사용 가능
"""
import random

from config import DAMAGE, get_attribute_multiplier
from models import UserStatEnum
from service.combat.damage_calculator import DamageCalculator
from service.dungeon.buff import (
    AttackBuff, DefenseBuff, SpeedBuff, ApAttackBuff, ApDefenseBuff, ShieldBuff,
    apply_status_effect, remove_status_effects, get_status_stacks,
    get_damage_taken_multiplier, has_curse_effect,
)
from service.dungeon.turn_config import TurnConfig

skill_component_register = {}


def register_skill_with_tag(tag):
    def decorator(cls):
        skill_component_register[tag] = cls
        return cls
    return decorator


def get_component_by_tag(tag):
    return skill_component_register[tag]()


class SkillComponent(TurnConfig):
    def __init__(self):
        self.priority = 0
        self.skill_name = ""
        self.skill_attribute = "무속성"

    def apply_config(self, config, skill_name, priority=0):
        self.priority = priority
        self.skill_name = skill_name


# =============================================================================
# 공격 컴포넌트
# =============================================================================


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

    def _calculate_base_attack_power(self, attacker_stat) -> int:
        """스탯 계수를 적용한 기본 공격력 계산"""
        ad = attacker_stat.get(UserStatEnum.ATTACK, 0)
        ap = attacker_stat.get(UserStatEnum.AP_ATTACK, 0)
        total = int(ad * self.ad_ratio + ap * self.ap_ratio)
        return max(1, total)

    def on_turn(self, attacker, target):
        attacker_stat = attacker.get_stat()
        attack_power = self._calculate_base_attack_power(attacker_stat)

        target_stat = target.get_stat() if hasattr(target, 'get_stat') else {}
        if self.is_physical:
            defense = target_stat.get(UserStatEnum.DEFENSE, 0) if target_stat else getattr(target, 'defense', 0)
        else:
            defense = target_stat.get(UserStatEnum.AP_DEFENSE, 0) if target_stat else getattr(target, 'ap_defense', 0)

        crit_rate = DAMAGE.DEFAULT_CRITICAL_RATE + self.crit_bonus

        # 속성 상성 배율
        target_attr = getattr(target, 'attribute', '무속성')
        attr_mult = get_attribute_multiplier(self.skill_attribute, target_attr)

        # 시너지 배율 (덱 기반)
        synergy_mult = 1.0
        if hasattr(attacker, 'equipped_skill'):
            from service.synergy_service import SynergyService
            synergy_mult = SynergyService.calculate_damage_multiplier(
                attacker.equipped_skill,
                self.skill_attribute
            )

        # 받는 피해 배율 (동결, 표식 등)
        damage_taken_mult = get_damage_taken_multiplier(target)

        hit_logs = []
        for _ in range(self.hit_count):
            if self.is_physical:
                result = DamageCalculator.calculate_physical_damage(
                    attack=attack_power,
                    defense=defense,
                    skill_multiplier=1.0,
                    armor_penetration=self.armor_penetration,
                    critical_rate=crit_rate,
                    attribute_multiplier=attr_mult * synergy_mult * damage_taken_mult,
                )
            else:
                result = DamageCalculator.calculate_magical_damage(
                    ap_attack=attack_power,
                    ap_defense=defense,
                    skill_multiplier=1.0,
                    magic_penetration=self.armor_penetration,
                    critical_rate=crit_rate,
                    attribute_multiplier=attr_mult * synergy_mult * damage_taken_mult,
                )

            target.take_damage(result.damage)

            crit_text = " 💥" if result.is_critical else ""
            attr_text = ""
            if attr_mult > 1.0:
                attr_text = " 🔺효과적!"
            elif attr_mult < 1.0:
                attr_text = " 🔻비효과적..."
            hit_logs.append(f"⚔️ **{attacker.get_name()}** 「{self.skill_name}」 → **{result.damage}**{crit_text}{attr_text}")

        return "\n".join(hit_logs)


# =============================================================================
# 회복 컴포넌트
# =============================================================================


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
            from service.synergy_service import SynergyService
            synergy_mult = SynergyService.calculate_heal_multiplier(attacker.equipped_skill)
            total_heal = int(total_heal * synergy_mult)

        # 저주 효과 시 회복량 50% 감소
        if has_curse_effect(attacker):
            total_heal = total_heal // 2

        old_hp = attacker.now_hp
        attacker.now_hp = min(attacker.now_hp + total_heal, max_hp)
        actual_heal = attacker.now_hp - old_hp

        return f"💚 **{attacker.get_name()}** 「{self.skill_name}」 → **+{actual_heal}** HP"


# =============================================================================
# 버프 컴포넌트 (버그 수정: 실제 Buff 적용)
# =============================================================================


@register_skill_with_tag("buff")
class BuffComponent(SkillComponent):
    """
    버프 컴포넌트 - 실제 Buff 객체를 entity.status에 추가

    Config options:
        duration (int): 지속 턴 수 (기본 3)
        attack (float): 공격력 증가율 (예: 0.25 = +25%)
        defense (float): 방어력 증가율
        speed (float): 속도 증가율
        crit_rate (float): 치명타 확률 증가
    """

    def __init__(self):
        super().__init__()
        self.duration = 3
        self.attack_mod = 0
        self.defense_mod = 0
        self.speed_mod = 0
        self.crit_rate_mod = 0

    def apply_config(self, config, skill_name, priority=0):
        super().apply_config(config, skill_name, priority)
        self.duration = config.get("duration", 3)
        self.attack_mod = config.get("attack", 0)
        self.defense_mod = config.get("defense", 0)
        self.speed_mod = config.get("speed", 0)
        self.crit_rate_mod = config.get("crit_rate", 0)

    def on_turn_start(self, attacker, target):
        effects = []
        stat = attacker.get_stat()

        if self.attack_mod != 0:
            amount = int(stat[UserStatEnum.ATTACK] * self.attack_mod)
            buff = AttackBuff()
            buff.amount = amount
            buff.duration = self.duration
            attacker.status.append(buff)
            effects.append(f"공격력 +{amount}")

        if self.defense_mod != 0:
            amount = int(stat[UserStatEnum.DEFENSE] * self.defense_mod)
            buff = DefenseBuff()
            buff.amount = amount
            buff.duration = self.duration
            attacker.status.append(buff)
            effects.append(f"방어력 +{amount}")

        if self.speed_mod != 0:
            amount = int(stat[UserStatEnum.SPEED] * self.speed_mod)
            buff = SpeedBuff()
            buff.amount = amount
            buff.duration = self.duration
            attacker.status.append(buff)
            effects.append(f"속도 +{amount}")

        if not effects:
            return ""

        return f"✨ **{attacker.get_name()}** 「{self.skill_name}」 → {', '.join(effects)} ({self.duration}턴)"


# =============================================================================
# 디버프 컴포넌트 (버그 수정: 실제 Buff 적용)
# =============================================================================


@register_skill_with_tag("debuff")
class DebuffComponent(SkillComponent):
    """디버프 컴포넌트 - 실제 디버프 Buff를 target.status에 추가"""

    def __init__(self):
        super().__init__()
        self.duration = 3
        self.attack_mod = 0
        self.defense_mod = 0
        self.speed_mod = 0

    def apply_config(self, config, skill_name, priority=0):
        super().apply_config(config, skill_name, priority)
        self.duration = config.get("duration", 3)
        self.attack_mod = config.get("attack", 0)
        self.defense_mod = config.get("defense", 0)
        self.speed_mod = config.get("speed", 0)

    def on_turn(self, attacker, target):
        effects = []
        target_stat = target.get_stat()

        if self.attack_mod != 0:
            amount = int(target_stat[UserStatEnum.ATTACK] * self.attack_mod)
            buff = AttackBuff()
            buff.amount = amount  # 음수값
            buff.duration = self.duration
            buff.is_debuff = True
            target.status.append(buff)
            effects.append(f"공격력 {amount}")

        if self.defense_mod != 0:
            amount = int(target_stat[UserStatEnum.DEFENSE] * self.defense_mod)
            buff = DefenseBuff()
            buff.amount = amount
            buff.duration = self.duration
            buff.is_debuff = True
            target.status.append(buff)
            effects.append(f"방어력 {amount}")

        if self.speed_mod != 0:
            amount = int(target_stat[UserStatEnum.SPEED] * self.speed_mod)
            buff = SpeedBuff()
            buff.amount = amount
            buff.duration = self.duration
            buff.is_debuff = True
            target.status.append(buff)
            effects.append(f"속도 {amount}")

        if not effects:
            return ""

        return f"🔮 **{attacker.get_name()}** 「{self.skill_name}」 → **{target.get_name()}** {', '.join(effects)} ({self.duration}턴)"


# =============================================================================
# 생명력 흡수 컴포넌트
# =============================================================================


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

    def _calculate_base_attack_power(self, attacker_stat) -> int:
        ad = attacker_stat.get(UserStatEnum.ATTACK, 0)
        ap = attacker_stat.get(UserStatEnum.AP_ATTACK, 0)
        total = int(ad * self.ad_ratio + ap * self.ap_ratio)
        return max(1, total)

    def on_turn(self, attacker, target):
        attacker_stat = attacker.get_stat()
        attack_power = self._calculate_base_attack_power(attacker_stat)
        max_hp = attacker_stat.get(UserStatEnum.HP, attacker.hp)

        target_stat = target.get_stat() if hasattr(target, 'get_stat') else {}
        if self.is_physical:
            defense = target_stat.get(UserStatEnum.DEFENSE, 0) if target_stat else getattr(target, 'defense', 0)
        else:
            defense = target_stat.get(UserStatEnum.AP_DEFENSE, 0) if target_stat else getattr(target, 'ap_defense', 0)

        crit_rate = DAMAGE.DEFAULT_CRITICAL_RATE + self.crit_bonus

        # 속성 배율
        target_attr = getattr(target, 'attribute', '무속성')
        attr_mult = get_attribute_multiplier(self.skill_attribute, target_attr)
        damage_taken_mult = get_damage_taken_multiplier(target)

        hit_logs = []
        total_damage = 0

        for _ in range(self.hit_count):
            if self.is_physical:
                result = DamageCalculator.calculate_physical_damage(
                    attack=attack_power, defense=defense,
                    skill_multiplier=1.0, armor_penetration=self.armor_penetration,
                    critical_rate=crit_rate, attribute_multiplier=attr_mult * damage_taken_mult,
                )
            else:
                result = DamageCalculator.calculate_magical_damage(
                    ap_attack=attack_power, ap_defense=defense,
                    skill_multiplier=1.0, magic_penetration=self.armor_penetration,
                    critical_rate=crit_rate, attribute_multiplier=attr_mult * damage_taken_mult,
                )

            target.take_damage(result.damage)
            total_damage += result.damage

            crit_text = " 💥" if result.is_critical else ""
            hit_logs.append(f"🩸 **{attacker.get_name()}** 「{self.skill_name}」 → **{result.damage}**{crit_text}")

        heal_amount = int(total_damage * self.lifesteal)
        if has_curse_effect(attacker):
            heal_amount = heal_amount // 2

        old_hp = attacker.now_hp
        attacker.now_hp = min(attacker.now_hp + heal_amount, max_hp)
        actual_heal = attacker.now_hp - old_hp

        if actual_heal > 0:
            hit_logs.append(f"   💚 흡혈 회복: **+{actual_heal}** HP")

        return "\n".join(hit_logs)


# =============================================================================
# 상태이상 컴포넌트
# =============================================================================


@register_skill_with_tag("status")
class StatusComponent(SkillComponent):
    """
    상태이상 적용 컴포넌트

    Config options:
        type (str): 상태이상 타입 (burn, poison, bleed, slow, freeze, stun 등)
        chance (float): 적용 확률 (0.0~1.0)
        duration (int): 지속 턴 수
        stacks (int): 적용 스택 수
    """

    def __init__(self):
        super().__init__()
        self.status_type = ""
        self.chance = 1.0
        self.status_duration = 0
        self.stacks = 1

    def apply_config(self, config, skill_name, priority=0):
        super().apply_config(config, skill_name, priority)
        self.status_type = config.get("type", "")
        self.chance = config.get("chance", 1.0)
        self.status_duration = config.get("duration", 0)
        self.stacks = config.get("stacks", 1)

    def on_turn(self, attacker, target):
        if not self.status_type:
            return ""
        if random.random() >= self.chance:
            return ""
        return apply_status_effect(target, self.status_type, self.stacks, self.status_duration)


# =============================================================================
# 소모 (Consume) 컴포넌트
# =============================================================================


@register_skill_with_tag("consume")
class ConsumeComponent(SkillComponent):
    """
    상태이상 소모 컴포넌트 - 스택 소모 후 추가 데미지

    Config options:
        consume_type (str): 소모할 상태이상 타입
        per_stack_ratio (float): 레거시 - 스택당 추가 데미지 비율
        ad_ratio (float): 스택당 물리 공격력 계수 (예: 1.0 = 스택당 100% AD)
        ap_ratio (float): 스택당 마법 공격력 계수 (예: 0.5 = 스택당 50% AP)
        base_damage (int): 스택과 관계없는 기본 고정 데미지
        is_physical (bool): 물리/마법 데미지 여부 (방어력 적용)
    """

    def __init__(self):
        super().__init__()
        self.consume_type = ""
        self.per_stack_ratio = 0.0  # 레거시 호환
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

        # 추가 데미지 계산
        attacker_stat = attacker.get_stat()
        ad = attacker_stat.get(UserStatEnum.ATTACK, 0)
        ap = attacker_stat.get(UserStatEnum.AP_ATTACK, 0)

        # 새 방식: ad_ratio + ap_ratio 별도 계산
        if self.ad_ratio > 0 or self.ap_ratio > 0:
            bonus_damage = self.base_damage
            bonus_damage += int(stacks * self.ad_ratio * ad)
            bonus_damage += int(stacks * self.ap_ratio * ap)
        # 레거시 방식: per_stack_ratio
        else:
            bonus_damage = int(stacks * self.per_stack_ratio * max(ap, ad))

        bonus_damage = max(1, bonus_damage)

        # 데미지 적용 (물리/마법 구분)
        if self.is_physical:
            # 물리 데미지 - 방어력 적용
            defense = target.get_stat().get(UserStatEnum.DEFENSE, 0)
            final_damage = max(1, int(bonus_damage * (1 - defense * 0.005)))
        else:
            # 마법 데미지 - 마방 적용
            ap_defense = target.get_stat().get(UserStatEnum.AP_DEFENSE, 0)
            final_damage = max(1, int(bonus_damage * (1 - ap_defense * 0.005)))

        target.take_damage(final_damage)
        return f"💥 **{attacker.get_name()}** 「{self.skill_name}」 {self.consume_type} x{stacks} 소모 → **{final_damage}** 추가 데미지!"


# =============================================================================
# 보호막 컴포넌트
# =============================================================================


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
        shield_amount = int(max_hp * self.percent) + self.flat
        shield_amount = max(1, shield_amount)

        shield = ShieldBuff()
        shield.shield_hp = shield_amount
        shield.duration = self.shield_duration
        attacker.status.append(shield)

        return f"🛡️ **{attacker.get_name()}** 「{self.skill_name}」 → 보호막 **{shield_amount}**!"


# =============================================================================
# 정화 컴포넌트
# =============================================================================


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


# =============================================================================
# 패시브 버프 컴포넌트
# =============================================================================


@register_skill_with_tag("passive_buff")
class PassiveBuffComponent(SkillComponent):
    """
    패시브 버프 컴포넌트 - 전투 시작 시 1회 영구 버프

    Config options:
        attack_percent (float): 공격력 증가 비율
        hp_percent (float): HP 증가 비율
        defense_percent (float): 방어력 증가 비율
        crit_rate (float): 치명타 확률 증가
        condition (str): 발동 조건 (vs_boss, always 등)
    """

    def __init__(self):
        super().__init__()
        self.attack_percent = 0.0
        self.hp_percent = 0.0
        self.defense_percent = 0.0
        self.crit_rate = 0.0
        self.condition = "always"
        self._applied = False

    def apply_config(self, config, skill_name, priority=0):
        super().apply_config(config, skill_name, priority)
        self.attack_percent = config.get("attack_percent", 0.0)
        self.hp_percent = config.get("hp_percent", 0.0)
        self.defense_percent = config.get("defense_percent", 0.0)
        self.crit_rate = config.get("crit_rate", 0.0)
        self.condition = config.get("condition", "always")

    def on_turn_start(self, attacker, target):
        if self._applied:
            return ""
        self._applied = True

        # 조건 체크 (향후 확장)
        # vs_boss 등의 조건은 target 기반으로 체크 가능

        stat = attacker.get_stat()
        effects = []
        duration = 999  # 영구

        if self.attack_percent != 0:
            amount = int(stat[UserStatEnum.ATTACK] * self.attack_percent)
            buff = AttackBuff()
            buff.amount = amount
            buff.duration = duration
            attacker.status.append(buff)
            effects.append(f"공격력 +{amount}")

        if self.defense_percent != 0:
            amount = int(stat[UserStatEnum.DEFENSE] * self.defense_percent)
            buff = DefenseBuff()
            buff.amount = amount
            buff.duration = duration
            attacker.status.append(buff)
            effects.append(f"방어력 +{amount}")

        if not effects:
            return ""

        return f"🌟 **{attacker.get_name()}** 패시브 「{self.skill_name}」 → {', '.join(effects)}"


# =============================================================================
# 콤보 체인 컴포넌트
# =============================================================================


@register_skill_with_tag("combo")
class ComboComponent(SkillComponent):
    """
    콤보 체인 컴포넌트

    대상의 상태이상을 체크하여 추가 데미지/효과 적용
    DamageComponent와 함께 사용하여 콤보 효과 구현

    Config options:
        combo_type (str): 콤보 타입 (ignite, shatter, overload 등) - 메시지용
        prerequisite (str): 선행 조건 상태이상 (burn, freeze, paralyze 등)
        min_stacks (int): 최소 스택 수 (기본 1)
        damage_multiplier (float): 추가 데미지 배율 (기본 1.0)
        consume_stacks (bool): 스택 소모 여부 (기본 False)
        force_critical (bool): 강제 치명타 여부 (기본 False)
        ad_ratio (float): 물리 공격력 계수
        ap_ratio (float): 마법 공격력 계수
        apply_status (str): 추가 적용할 상태이상 (선택)
        apply_duration (int): 추가 상태이상 지속 시간

    예시:
        # 소각: 화상 3스택 이상 시 1.3배 추가 데미지
        {
            "tag": "combo",
            "combo_type": "ignite",
            "prerequisite": "burn",
            "min_stacks": 3,
            "damage_multiplier": 1.3,
            "ad_ratio": 0.5
        }

        # 파쇄: 동결 시 2배 추가 데미지 + 강제 치명타 + 스택 소모
        {
            "tag": "combo",
            "combo_type": "shatter",
            "prerequisite": "freeze",
            "damage_multiplier": 2.0,
            "force_critical": True,
            "consume_stacks": True,
            "ap_ratio": 1.0
        }
    """

    def __init__(self):
        super().__init__()
        self.combo_type = ""
        self.prerequisite = ""
        self.min_stacks = 1
        self.damage_multiplier = 1.0
        self.consume_stacks = False
        self.force_critical = False
        self.ad_ratio = 0.0
        self.ap_ratio = 0.0
        self.apply_status = ""
        self.apply_duration = 0

    def apply_config(self, config, skill_name, priority=0):
        super().apply_config(config, skill_name, priority)
        self.combo_type = config.get("combo_type", "")
        self.prerequisite = config.get("prerequisite", "")
        self.min_stacks = config.get("min_stacks", 1)
        self.damage_multiplier = config.get("damage_multiplier", 1.0)
        self.consume_stacks = config.get("consume_stacks", False)
        self.force_critical = config.get("force_critical", False)
        self.ad_ratio = config.get("ad_ratio", 0.0)
        self.ap_ratio = config.get("ap_ratio", 0.0)
        self.apply_status = config.get("apply_status", "")
        self.apply_duration = config.get("apply_duration", 0)

    def on_turn(self, attacker, target):
        # 선행 조건 체크
        if not self.prerequisite:
            return ""

        if not has_status_effect(target, self.prerequisite):
            return ""

        stacks = get_status_stacks(target, self.prerequisite)
        if stacks < self.min_stacks:
            return ""

        # 콤보 발동!
        logs = []

        # 콤보 데미지 계산
        attacker_stat = attacker.get_stat()
        ad = attacker_stat.get(UserStatEnum.ATTACK, 0)
        ap = attacker_stat.get(UserStatEnum.AP_ATTACK, 0)

        base_damage = int(ad * self.ad_ratio + ap * self.ap_ratio)
        bonus_damage = int(base_damage * self.damage_multiplier)

        if bonus_damage > 0:
            # 강제 치명타 적용
            if self.force_critical:
                bonus_damage = int(bonus_damage * DAMAGE.CRITICAL_MULTIPLIER)

            target.take_damage(bonus_damage)

        # 스택 소모
        if self.consume_stacks:
            remove_status_effects(target, count=99, filter_type=self.prerequisite)

        # 추가 상태이상 적용
        if self.apply_status:
            status_log = apply_status_effect(
                target,
                self.apply_status,
                stacks=1,
                duration=self.apply_duration
            )
            if status_log:
                logs.append(status_log)

        # 콤보 메시지
        combo_name = self._get_combo_name()
        crit_mark = " 💥" if self.force_critical else ""

        if bonus_damage > 0:
            main_log = f"{combo_name} **{attacker.get_name()}** 「{self.skill_name}」 → **+{bonus_damage}**{crit_mark}"
            logs.insert(0, main_log)
        else:
            logs.insert(0, f"{combo_name} **{attacker.get_name()}** 「{self.skill_name}」 발동!")

        return "\n".join(logs)

    def _get_combo_name(self) -> str:
        """콤보 타입별 이름/이모지 반환"""
        combo_names = {
            # 화염
            "ignite": "🔥소각",
            "incinerate": "💥연소",

            # 냉기
            "shatter": "❄️💥파쇄",

            # 번개
            "paralyze_combo": "⚡마비",
            "overload": "⚡💥과부하",

            # 암흑
            "curse_combo": "👿저주",
            "vampiric": "🩸흡혈",
            "infect": "🦠감염",

            # 수속성
            "submerge": "🌊침수",

            # 물리
            "stun_combo": "💫기절",
            "bleed_combo": "🩸출혈",
        }
        return combo_names.get(self.combo_type, "💥콤보")


# =============================================================================
# 소환 컴포넌트
# =============================================================================


@register_skill_with_tag("summon")
class SummonComponent(SkillComponent):
    """
    몬스터 소환 컴포넌트
    
    전투 중 추가 몬스터를 소환합니다.
    CombatContext의 monsters 리스트에 추가됩니다.
    
    Config options:
        monster_ids (list[int]): 소환 가능한 몬스터 ID 리스트
        count (int): 소환할 개수 (기본 1)
        use_limit (int): 전투당 사용 제한 (기본 None=무제한)
    
    예시:
        {
            "tag": "summon",
            "monster_ids": [2, 4],  # 고블린 또는 고블린 궁수
            "count": 2,
            "use_limit": 1  # 전투당 1회만
        }
    """
    
    def __init__(self):
        super().__init__()
        self.monster_ids = []
        self.count = 1
        self.use_limit = None
        self.used_count = 0
    
    def apply_config(self, config, skill_name, priority=0):
        super().apply_config(config, skill_name, priority)
        self.monster_ids = config.get("monster_ids", [])
        self.count = config.get("count", 1)
        self.use_limit = config.get("use_limit", None)
    
    def on_turn(self, attacker, defender) -> str:
        """
        소환 실행

        Args:
            attacker: 소환하는 엔티티 (몬스터)
            defender: 대상 (플레이어)

        Returns:
            소환 로그 메시지
        """
        from models.repos.static_cache import monster_cache_by_id
        from service.session import get_session, get_all_sessions

        # 사용 제한 체크
        if self.use_limit is not None and self.used_count >= self.use_limit:
            return f"💫 **{attacker.get_name()}** {self.skill_name} 사용 불가 (제한 초과)"

        # 소환할 몬스터 ID 선택
        if not self.monster_ids:
            return f"⚠️ **{attacker.get_name()}** {self.skill_name} 소환 실패 (설정 오류)"

        # 플레이어 세션 찾기
        session = None

        # 1. defender가 User 객체인 경우
        if hasattr(defender, 'discord_id'):
            session = get_session(defender.discord_id)

        # 2. 그 외의 경우 모든 세션 검색 (안전장치)
        if not session:
            all_sessions = get_all_sessions()
            for s in all_sessions.values():
                if s.combat_context and attacker in s.combat_context.monsters:
                    session = s
                    break

        if not session or not session.combat_context:
            return f"⚠️ **{attacker.get_name()}** {self.skill_name} 소환 실패 (전투 컨텍스트 없음)"

        summoned_names = []
        summoned_count = 0

        # 소환 실행
        for _ in range(self.count):
            # 랜덤하게 몬스터 ID 선택
            selected_id = random.choice(self.monster_ids)

            if selected_id in monster_cache_by_id:
                # 몬스터 복사하여 소환
                summoned = monster_cache_by_id[selected_id].copy()
                session.combat_context.monsters.append(summoned)
                summoned_names.append(summoned.get_name())
                summoned_count += 1

        # 사용 횟수 증가
        self.used_count += 1

        if summoned_count > 0:
            names_str = ", ".join(summoned_names)
            return f"✨ **{attacker.get_name()}** {self.skill_name}! → {names_str} 소환!"
        else:
            return f"⚠️ **{attacker.get_name()}** {self.skill_name} 소환 실패"
