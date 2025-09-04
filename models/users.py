import random
from enum import IntEnum, Enum

from tortoise import models, fields

class UserStatEnum(str,Enum):
    HP = "HP"
    ATTACK = "ATTACK"
    SPEED = "SPEED"

class User(models.Model):
    id = fields.IntField(pk=True)
    discord_id = fields.BigIntField()
    username = fields.CharField(max_length=255)
    password = fields.CharField(max_length=255)
    baekjoon_id = fields.CharField(max_length=255)
    gender = fields.CharField(max_length=255)
    cuha_point = fields.BigIntField()
    created_at = fields.DatetimeField(auto_now_add=True)
    user_role = fields.CharField(max_length=255)

    hp = fields.IntField(default=300)
    level = fields.IntField(default=1)
    now_hp = fields.IntField(default=300)
    attack = fields.IntField(default=10)
    speed = 10

    status = []
    equipped_skill = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    skill_queue = []

    def next_skill(self):
        from models.repos.skill_repo import get_skill_by_id
        if not self.skill_queue:
            self.skill_queue = self.equipped_skill[:]
            random.shuffle(self.skill_queue)

        return get_skill_by_id(self.skill_queue.pop())

    def get_name(self):
        return self.username
    def on_turn_start(self):
        pass
    def on_turn_end(self):
        pass
    def get_stat(self):
        stat = {
            UserStatEnum.HP : self.hp,
            UserStatEnum.SPEED : self.speed,
            UserStatEnum.ATTACK : self.attack
        }
        for buff in self.status:
            buff.apply_stat(stat)
        return stat
    class Meta:
        table = "users"

class SkillEquip(models.Model):
    id = fields.BigIntField(pk=True)
    pos = fields.IntField(null=True)
    user = fields.ForeignKeyField('models.User', related_name='equipped_skills', on_delete=fields.CASCADE)
    skill = fields.ForeignKeyField('models.Skill_Model', related_name='equipped_by_users', on_delete=fields.CASCADE)

    class Meta:
        table = "skill_equip"

