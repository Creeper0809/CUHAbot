from tortoise import models, fields
from enum import Enum

# 임시 등급
class Grade(Enum):
    D = 1
    C = 2
    B = 3
    A = 4
    S = 5

# 임시 pos
class EquipPosition(Enum):
    오른손 = 1
    왼손 = 2
    머리 = 3
    상의 = 4
    하의 = 5
    신발 = 6
    반지 = 7
    귀걸이 = 8
    #ACCESSORY_추후 추가 = 9
    #ACCESSORY_추후 추가 = 10


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
    ap_attack = fields.IntField(null=True)
    ad_defanse = fields.IntField(null=True)
    ap_defanse = fields.IntField(null=True)
    grade = fields.IntField()
    equip_pos = fields.IntField()

    class Meta:
        table = "equipment_item"

# 장비 아이템 정보 변환
    def get_stats(self):
        stats = {}
        stats_mapping = {
            'attack': ('공격력', self.attack),
            'hp': ('체력', self.hp),
            'ap_attack': ('주문력', self.ap_attack),
            'ad_defanse': ('방어력', self.ad_defanse),
            'ap_defanse': ('마법 저항력', self.ap_defanse)
        }

        for _, (name, value) in stats_mapping.items():
            if value is not None and value != 0:
                stats[name] = value

        return stats

    def __str__(self):
        return f"Equipment {self.equipment_item_id}"
