"""
DungeonUserPos 모델 정의

던전 내 사용자의 장비/스킬 위치를 관리합니다.
"""
from tortoise import fields, models


class DungeonUserPos(models.Model):
    id = fields.IntField(pk=True)
    user = fields.ForeignKeyField(
        'models.User',
        related_name='positions',
        on_delete=fields.CASCADE
    )
    equip = fields.ForeignKeyField(
        'models.Item',
        related_name='equipped_positions',
        null=True,
        on_delete=fields.SET_NULL
    )
    skill = fields.ForeignKeyField(
        'models.Skill_Model',
        related_name='equipped_positions',
        null=True,
        on_delete=fields.SET_NULL
    )

    class Meta:
        table = "dungeon_user_pos"

    def __str__(self):
        return f"{self.user.name}의 장비: {self.equip.name if self.equip else 'None'}, 스킬: {self.skill.name if self.skill else 'None'}"