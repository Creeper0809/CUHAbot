"""
스킬 컴포넌트 시스템

스킬의 다양한 효과를 컴포넌트 단위로 분리하여 조합합니다.
각 컴포넌트는 턴 기반 콜백을 구현합니다.
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
        damage (float): 데미지 배율 (필수, 예: 1.0 = 100%)
        hit_count (int): 타격 횟수 (기본 1)
        crit_bonus (float): 추가 치명타 확률 (기본 0)
        armor_pen (float): 방어력 무시 비율 (기본 0, 최대 0.7)
        is_physical (bool): 물리 데미지 여부 (기본 True)
    """

    def __init__(self):
        super().__init__()
        self.damage_multiplier = 1.0
        self.hit_count = 1
        self.crit_bonus = 0.0
        self.armor_penetration = 0.0
        self.is_physical = True

    def apply_config(self, config, skill_name, priority=0):
        super().apply_config(config, skill_name, priority)
        self.damage_multiplier = config.get("damage", 1.0)
        self.hit_count = config.get("hit_count", 1)
        self.crit_bonus = config.get("crit_bonus", 0.0)
        self.armor_penetration = config.get("armor_pen", 0.0)
        self.is_physical = config.get("is_physical", True)

    def on_turn(self, attacker, target):
        attacker_stat = attacker.get_stat()
        attack_power = attacker_stat[UserStatEnum.ATTACK]

        # 대상의 방어력 (현재 모델에 없으므로 기본값 0)
        defense = 0

        # 치명타 확률 (기본 5% + 보너스)
        crit_rate = DAMAGE.DEFAULT_CRITICAL_RATE + self.crit_bonus

        total_damage = 0
        critical_hits = 0
        logs = []

        for hit_num in range(self.hit_count):
            if self.is_physical:
                result = DamageCalculator.calculate_physical_damage(
                    attack=attack_power,
                    defense=defense,
                    skill_multiplier=self.damage_multiplier,
                    armor_penetration=self.armor_penetration,
                    critical_rate=crit_rate,
                )
            else:
                result = DamageCalculator.calculate_magical_damage(
                    ap_attack=attack_power,
                    ap_defense=defense,
                    skill_multiplier=self.damage_multiplier,
                    magic_penetration=self.armor_penetration,
                    critical_rate=crit_rate,
                )

            target.take_damage(result.damage)
            total_damage += result.damage
            if result.is_critical:
                critical_hits += 1

        # 결과 메시지 생성
        crit_text = f" [치명타 {critical_hits}회!]" if critical_hits > 0 else ""
        hit_text = f" ({self.hit_count}타)" if self.hit_count > 1 else ""

        return f"{attacker.get_name()}의 {self.skill_name}!{hit_text}{crit_text} {target.get_name()}에게 {total_damage} 피해!"


@register_skill_with_tag("heal")
class HealComponent(SkillComponent):
    def __init__(self):
        super().__init__()
        self.amount = 1

    def apply_config(self, config, skill_name, priority=0):
        super().apply_config(config, skill_name, priority)
        # "amount" 또는 "percent" 키 지원
        self.amount = config.get("amount") or config.get("percent", 0.15)

    def on_turn(self, attacker, target):
        attacker_stat = attacker.get_stat()

        total_heal = int(attacker_stat[UserStatEnum.ATTACK] * self.amount)

        attacker.now_hp += total_heal
        attacker.now_hp = min(attacker.now_hp, attacker_stat[UserStatEnum.HP])
        return f"{attacker.get_name()}이 {self.skill_name}을 사용하여 {total_heal}의 힐을 했다!"


@register_skill_with_tag("buff")
class BuffComponent(SkillComponent):
    def __init__(self):
        super().__init__()
        self.buff = None
        self.duration = 3
        self.attack_mod = 0
        self.defense_mod = 0

    def apply_config(self, config, skill_name, priority=0):
        super().apply_config(config, skill_name, priority)
        self.duration = config.get("duration", 3)
        self.attack_mod = config.get("attack", 0)
        self.defense_mod = config.get("defense", 0)

        # 기존 "type" 키 지원 (하위 호환성)
        if "type" in config:
            buff = get_buff_by_tag(config["type"])
            buff.apply_config(config)
            self.buff = buff

    def on_turn_start(self, attacker, target):
        if self.buff:
            attacker.status.append(self.buff)
            return f"{self.skill_name}을 사용하여 {self.buff.get_description()}을 {self.buff.duration}동안 얻었다!"
        # 새 포맷: 직접 스탯 적용 (간단 처리)
        effects = []
        if self.attack_mod != 0:
            effects.append(f"공격력 {'+' if self.attack_mod > 0 else ''}{int(self.attack_mod * 100)}%")
        if self.defense_mod != 0:
            effects.append(f"방어력 {'+' if self.defense_mod > 0 else ''}{int(self.defense_mod * 100)}%")
        return f"{self.skill_name}을 사용하여 {', '.join(effects)} 효과를 {self.duration}턴간 얻었다!"


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
        return f"{attacker.get_name()}이 {self.skill_name}을 사용하여 {target.get_name()}에게 {', '.join(effects)} 효과를 {self.duration}턴간 부여했다!"

