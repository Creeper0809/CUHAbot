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

from config import DAMAGE
from models import UserStatEnum
from service.combat.damage_calculator import DamageCalculator
from service.dungeon.buff import get_buff_by_tag
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

    def apply_config(self, config, skill_name, priority=0):
        self.priority = priority
        self.skill_name = skill_name


@register_skill_with_tag("attack")
class DamageComponent(SkillComponent):
    """
    공격 데미지 컴포넌트

    DamageCalculator를 사용하여 방어력, 치명타, 데미지 변동을 적용합니다.

    Config options:
        damage (float): 기본 데미지 배율 (기본 1.0, ad_ratio/ap_ratio 미지정 시 사용)
        ad_ratio (float): 물리 공격력 계수 (예: 1.4 = 140% AD)
        ap_ratio (float): 마법 공격력 계수 (예: 1.0 = 100% AP)
        hit_count (int): 타격 횟수 (기본 1)
        crit_bonus (float): 추가 치명타 확률 (기본 0)
        armor_pen (float): 방어력 무시 비율 (기본 0, 최대 0.7)
        is_physical (bool): 물리/마법 데미지 여부 (기본 True=물리)

    스케일링 예시:
        - 순수 AD 스킬: {"ad_ratio": 1.5}  → 150% AD
        - 순수 AP 스킬: {"ap_ratio": 1.2, "is_physical": False}  → 120% AP
        - 하이브리드: {"ad_ratio": 0.8, "ap_ratio": 0.6}  → 80% AD + 60% AP
        - 레거시: {"damage": 1.0}  → 100% AD (하위 호환)
    """

    def __init__(self):
        super().__init__()
        self.damage_multiplier = 1.0  # 레거시 호환용
        self.ad_ratio = 0.0
        self.ap_ratio = 0.0
        self.hit_count = 1
        self.crit_bonus = 0.0
        self.armor_penetration = 0.0
        self.is_physical = True

    def apply_config(self, config, skill_name, priority=0):
        super().apply_config(config, skill_name, priority)
        self.hit_count = config.get("hit_count", 1)
        self.crit_bonus = config.get("crit_bonus", 0.0)
        self.armor_penetration = config.get("armor_pen", 0.0)
        self.is_physical = config.get("is_physical", True)

        # 스탯 계수 설정 (ad_ratio/ap_ratio 우선, 없으면 damage를 ad_ratio로 사용)
        self.ad_ratio = config.get("ad_ratio", 0.0)
        self.ap_ratio = config.get("ap_ratio", 0.0)

        # 레거시 호환: ad_ratio/ap_ratio 둘 다 없으면 damage를 ad_ratio로 사용
        if self.ad_ratio == 0.0 and self.ap_ratio == 0.0:
            self.ad_ratio = config.get("damage", 1.0)

    def _calculate_base_attack_power(self, attacker_stat) -> int:
        """스탯 계수를 적용한 기본 공격력 계산"""
        ad = attacker_stat.get(UserStatEnum.ATTACK, 0)
        ap = attacker_stat.get(UserStatEnum.AP_ATTACK, 0)

        # AD * ad_ratio + AP * ap_ratio
        total = int(ad * self.ad_ratio + ap * self.ap_ratio)
        return max(1, total)

    def on_turn(self, attacker, target):
        attacker_stat = attacker.get_stat()
        attack_power = self._calculate_base_attack_power(attacker_stat)

        # 대상의 방어력
        target_stat = target.get_stat() if hasattr(target, 'get_stat') else {}
        if self.is_physical:
            defense = target_stat.get(UserStatEnum.DEFENSE, 0) if target_stat else getattr(target, 'defense', 0)
        else:
            defense = target_stat.get(UserStatEnum.AP_DEFENSE, 0) if target_stat else getattr(target, 'ap_defense', 0)

        # 치명타 확률 (기본 5% + 보너스)
        crit_rate = DAMAGE.DEFAULT_CRITICAL_RATE + self.crit_bonus

        total_damage = 0
        critical_hits = 0

        for _ in range(self.hit_count):
            if self.is_physical:
                result = DamageCalculator.calculate_physical_damage(
                    attack=attack_power,
                    defense=defense,
                    skill_multiplier=1.0,  # 이미 ad_ratio로 계산됨
                    armor_penetration=self.armor_penetration,
                    critical_rate=crit_rate,
                )
            else:
                result = DamageCalculator.calculate_magical_damage(
                    ap_attack=attack_power,
                    ap_defense=defense,
                    skill_multiplier=1.0,  # 이미 ap_ratio로 계산됨
                    magic_penetration=self.armor_penetration,
                    critical_rate=crit_rate,
                )

            target.take_damage(result.damage)
            total_damage += result.damage
            if result.is_critical:
                critical_hits += 1

        # 결과 메시지 생성
        crit_text = " 💥" if critical_hits > 0 else ""
        hit_text = f" x{self.hit_count}" if self.hit_count > 1 else ""

        return f"⚔️ **{attacker.get_name()}** 「{self.skill_name}」{hit_text} → **{total_damage}**{crit_text}"


@register_skill_with_tag("heal")
class HealComponent(SkillComponent):
    """
    회복 컴포넌트

    다양한 방식의 HP 회복을 지원합니다.

    Config options:
        percent (float): 최대 HP 비율 회복 (기본, 예: 0.15 = 15%)
        ad_ratio (float): AD 기반 회복 (예: 0.5 = AD의 50%)
        ap_ratio (float): AP 기반 회복 (예: 1.0 = AP의 100%)
        flat (int): 고정 회복량

    계산 방식:
        총 회복량 = (최대HP * percent) + (AD * ad_ratio) + (AP * ap_ratio) + flat

    예시:
        - HP 15% 회복: {"percent": 0.15}
        - AD 50% + AP 100%: {"ad_ratio": 0.5, "ap_ratio": 1.0}
        - 고정 50 + HP 10%: {"flat": 50, "percent": 0.1}
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

        # 레거시 호환: amount가 있으면 percent로 사용
        if "amount" in config and self.percent == 0.0:
            self.percent = config.get("amount", 0.15)

        # 아무것도 설정 안 되면 기본값 15%
        if self.percent == 0.0 and self.ad_ratio == 0.0 and self.ap_ratio == 0.0 and self.flat == 0:
            self.percent = 0.15

    def on_turn(self, attacker, target):
        attacker_stat = attacker.get_stat()
        max_hp = attacker_stat.get(UserStatEnum.HP, attacker.hp)
        ad = attacker_stat.get(UserStatEnum.ATTACK, 0)
        ap = attacker_stat.get(UserStatEnum.AP_ATTACK, 0)

        # 회복량 계산
        heal_from_percent = int(max_hp * self.percent)
        heal_from_ad = int(ad * self.ad_ratio)
        heal_from_ap = int(ap * self.ap_ratio)
        total_heal = heal_from_percent + heal_from_ad + heal_from_ap + self.flat

        # HP 회복 적용
        old_hp = attacker.now_hp
        attacker.now_hp = min(attacker.now_hp + total_heal, max_hp)
        actual_heal = attacker.now_hp - old_hp

        return f"💚 **{attacker.get_name()}** 「{self.skill_name}」 → **+{actual_heal}** HP"


@register_skill_with_tag("buff")
class BuffComponent(SkillComponent):
    """
    버프 컴포넌트

    Config options:
        duration (int): 지속 턴 수 (기본 3)
        attack (float): 공격력 증가율 (예: 0.25 = +25%)
        defense (float): 방어력 증가율
        speed (float): 속도 증가율
        crit_rate (float): 치명타 확률 증가 (예: 0.15 = +15%)
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
        if self.attack_mod != 0:
            effects.append(f"공격력 {'+' if self.attack_mod > 0 else ''}{int(self.attack_mod * 100)}%")
        if self.defense_mod != 0:
            effects.append(f"방어력 {'+' if self.defense_mod > 0 else ''}{int(self.defense_mod * 100)}%")
        if self.speed_mod != 0:
            effects.append(f"속도 {'+' if self.speed_mod > 0 else ''}{int(self.speed_mod * 100)}%")
        if self.crit_rate_mod != 0:
            effects.append(f"치명타 {'+' if self.crit_rate_mod > 0 else ''}{int(self.crit_rate_mod * 100)}%")

        if not effects:
            return ""

        return f"✨ **{attacker.get_name()}** 「{self.skill_name}」 → {', '.join(effects)} ({self.duration}턴)"


@register_skill_with_tag("debuff")
class DebuffComponent(SkillComponent):
    """디버프 컴포넌트 (대상에게 약화 효과)"""

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
        if self.attack_mod != 0:
            effects.append(f"공격력 {int(self.attack_mod * 100)}%")
        if self.defense_mod != 0:
            effects.append(f"방어력 {int(self.defense_mod * 100)}%")
        if self.speed_mod != 0:
            effects.append(f"속도 {int(self.speed_mod * 100)}%")
        return f"🔮 **{attacker.get_name()}** 「{self.skill_name}」 → **{target.get_name()}** {', '.join(effects)} ({self.duration}턴)"


@register_skill_with_tag("lifesteal")
class LifestealComponent(SkillComponent):
    """
    생명력 흡수 컴포넌트

    데미지를 입힌 후 피해량의 일정 비율을 회복합니다.

    Config options:
        ad_ratio (float): 물리 공격력 계수 (기본 1.0)
        ap_ratio (float): 마법 공격력 계수 (기본 0.0)
        lifesteal (float): 흡혈 비율 (예: 0.3 = 피해량의 30%)
        hit_count (int): 타격 횟수 (기본 1)
        crit_bonus (float): 추가 치명타 확률 (기본 0)
        armor_pen (float): 방어력 무시 비율 (기본 0)
        is_physical (bool): 물리 데미지 여부 (기본 True)

    예시:
        - 생명력 흡수: {"ad_ratio": 0.8, "lifesteal": 0.3}  → 80% AD 데미지, 30% 흡혈
        - 마법 흡혈: {"ap_ratio": 1.0, "lifesteal": 0.2, "is_physical": False}
    """

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

        # 레거시 호환: damage가 있으면 ad_ratio로 사용
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
        max_hp = attacker_stat.get(UserStatEnum.HP, attacker.hp)

        # 대상의 방어력
        target_stat = target.get_stat() if hasattr(target, 'get_stat') else {}
        if self.is_physical:
            defense = target_stat.get(UserStatEnum.DEFENSE, 0) if target_stat else getattr(target, 'defense', 0)
        else:
            defense = target_stat.get(UserStatEnum.AP_DEFENSE, 0) if target_stat else getattr(target, 'ap_defense', 0)

        crit_rate = DAMAGE.DEFAULT_CRITICAL_RATE + self.crit_bonus

        total_damage = 0
        critical_hits = 0

        for _ in range(self.hit_count):
            if self.is_physical:
                result = DamageCalculator.calculate_physical_damage(
                    attack=attack_power,
                    defense=defense,
                    skill_multiplier=1.0,
                    armor_penetration=self.armor_penetration,
                    critical_rate=crit_rate,
                )
            else:
                result = DamageCalculator.calculate_magical_damage(
                    ap_attack=attack_power,
                    ap_defense=defense,
                    skill_multiplier=1.0,
                    magic_penetration=self.armor_penetration,
                    critical_rate=crit_rate,
                )

            target.take_damage(result.damage)
            total_damage += result.damage
            if result.is_critical:
                critical_hits += 1

        # 흡혈 계산
        heal_amount = int(total_damage * self.lifesteal)
        old_hp = attacker.now_hp
        attacker.now_hp = min(attacker.now_hp + heal_amount, max_hp)
        actual_heal = attacker.now_hp - old_hp

        # 결과 메시지
        crit_text = " 💥" if critical_hits > 0 else ""
        hit_text = f" x{self.hit_count}" if self.hit_count > 1 else ""
        heal_text = f" 💚+{actual_heal}" if actual_heal > 0 else ""

        return f"🩸 **{attacker.get_name()}** 「{self.skill_name}」{hit_text} → **{total_damage}**{crit_text}{heal_text}"
