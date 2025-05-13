import random
from copy import deepcopy

from tortoise import models, fields

class Monster(models.Model):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=255)
    description = fields.TextField()
    hp = fields.IntField()
    attack = fields.IntField()
    speed = 10

    # 런타임 필드 (DB에 저장 안됨)
    now_hp = 0
    status = []
    use_skill = [0,0,0,0,0,0,0,0,0,0]
    skill_queue = []

    def next_skill(self):
        from models.repos.skill_repo import get_skill_by_id
        if not self.skill_queue:
            self.skill_queue = self.use_skill[:]
            random.shuffle(self.skill_queue)
        return get_skill_by_id(self.skill_queue.pop())

    def get_name(self):
        return self.name

    def copy(self):
        new_monster = Monster(
            name=self.name,
            description=self.description,
            hp=self.hp,
            attack=self.attack,
        )
        new_monster.now_hp = self.hp
        new_monster.status = deepcopy(self.status)
        return new_monster


    class Meta:
        table = "monster"
