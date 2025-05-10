from tortoise import models, fields
from enum import Enum

class Grade(str, Enum):
    S = "S"
    A = "A"
    B = "B"
    C = "C"
    D = "D"

class EquipPosition(str, Enum):
    무기 = "Weapon"
    보조무기 = "sub_Weapon"
    모자 = "Hat"
    흉갑 = "armor"
    신발 = "shoes"

class EquipmentItem(models.Model):
    equipment_item_id = fields.IntField(pk=True)
    item = fields.ForeignKeyField(
        'models.Item',
        related_name='equipment_item',
        source_field='equipment_item_id',
        to_field='id'
    )
    attack = fields.IntField(null=True)
    hp = fields.IntField(null=True)
    speed = fields.IntField(null=True)
    grade = fields.CharEnumField(Grade)
    equip_pos = fields.CharEnumField(EquipPosition)

    class Meta:
        table = "equipment_item"

# 장비 아이템 정보 변환
    def get_stats(self):
        stats = {}
        stats_mapping = {
            'attack': ('공격력', self.attack),
            'hp': ('체력', self.hp),
            'speed': ('속도', self.speed)

        }

        for _, (name, value) in stats_mapping.items():
            if value is not None and value != 0:
                stats[name] = value

        return stats

    def __str__(self):
        return f"Equipment {self.equipment_item_id}"