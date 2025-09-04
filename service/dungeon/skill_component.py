import random

from models import UserStatEnum
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
    def __init__(self):
        super().__init__()
        self.damage_times = 1

    def apply_config(self, config, skill_name, priority=0):
        super().apply_config(config, skill_name, priority)
        self.damage_times = config["damage"]

    def on_turn(self, attacker, target):
        attacker_stat = attacker.get_stat()
        total_damage = int(attacker_stat[UserStatEnum.ATTACK] * self.damage_times)

        target.now_hp -= total_damage
        target.now_hp = max(target.now_hp, 0)
        return f"{attacker.get_name()}이 {self.skill_name}을 사용하여 {target.get_name()}에게 {total_damage}의 피해를 입혔다!"


@register_skill_with_tag("heal")
class HealComponent(SkillComponent):
    def __init__(self):
        super().__init__()
        self.amount = 1

    def apply_config(self, config, skill_name, priority=0):
        super().apply_config(config, skill_name, priority)
        self.amount = config["amount"]

    def on_turn(self, attacker, target):
        attacker_stat = attacker.get_stat()
        target_stat = target.get_stat()

        total_heal = int(attacker_stat[UserStatEnum.ATTACK] * self.amount)

        attacker.now_hp += total_heal
        target.now_hp = min(target.now_hp, target_stat[UserStatEnum.HP])
        return f"{attacker.get_name()}이 {self.skill_name}을 사용하여 {total_heal}의 힐을 했다!"


@register_skill_with_tag("buff")
class BuffComponent(SkillComponent):
    def __init__(self):
        super().__init__()
        self.buff = None

    def apply_config(self, config, skill_name, priority=0):
        super().apply_config(config, skill_name, priority)
        buff = get_buff_by_tag(config["type"])
        buff.apply_config(config)
        self.buff = buff

    def on_turn_start(self,attacker,target):
        attacker.status.append(self.buff)
        return f"{self.skill_name}을 사용하여 {self.buff.get_description()}을 {self.buff.duration}동안 얻었다!"

