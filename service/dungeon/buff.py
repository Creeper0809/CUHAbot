from models import UserStatEnum
from service.dungeon.turn_config import TurnConfig

buff_register = {}

def register_buff_with_tag(tag):
    def decorator(cls):
        buff_register[tag] = cls
        return cls
    return decorator

def get_buff_by_tag(tag):
    return buff_register[tag]()

class Buff(TurnConfig):
    def __init__(self):
        self.amount = 0
        self.duration = 0

    def apply_stat(self,stats):
        pass

    def apply_config(self,config):
        self.amount = config["amount"]
        self.duration = config["duration"]


@register_buff_with_tag("attack")
class AttackBuff(Buff):
    def __init__(self):
        super().__init__()

    def apply_stat(self,stats):
        stats[UserStatEnum.ATTACK] += self.amount

    def get_description(self):
        return f"공격력 버프 {self.amount}"

