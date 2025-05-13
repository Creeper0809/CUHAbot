import random
CLASS_REGISTRY = {}

def register_with_tag(tag):
    def decorator(cls):
        CLASS_REGISTRY[tag] = cls
        return cls
    return decorator

def get_component_by_tag(tag):
    return CLASS_REGISTRY[tag]()

class SkillComponent:
    def __init__(self):
        self.priority = 0

    def apply_config(self, config, priority=0):
        self.priority = priority
    def on_turn_start(self,attacker,target,skill_name):
        return ""
    def on_turn(self,attacker,target,skill_name):
        return ""
    def on_turn_end(self,attacker,target,skill_name):
        return ""

@register_with_tag("attack")
class DamageComponent(SkillComponent):
    def __init__(self):
        super().__init__()
        self.damage_times = 1

    def apply_config(self, config, priority=0):
        super().apply_config(config, priority)
        self.damage_times = config["damage"]

    def on_turn(self,attacker,target,skill_name):
        total_damage = attacker.attack * self.damage_times

        target.now_hp -= total_damage
        target.now_hp = max(target.now_hp,0)
        return f"{attacker.get_name()}이 {skill_name}을 사용하여 {target.get_name()}에게 {total_damage}의 피해를 입혔다!"



