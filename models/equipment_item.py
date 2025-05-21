from tortoise import models, fields
from models.grade import Grade
from models.equip_pos import EquipPos

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
    grade = fields.IntField(null=True)
    equip_pos = fields.IntField(null=True)

    class Meta:
        table = "equipment_item"

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

    async def get_grade_info(self):
        if self.grade:
            return await Grade.get(id=self.grade)
        return None

    async def get_equip_pos_info(self):
        if self.equip_pos:
            return await EquipPos.get(id=self.equip_pos)
        return None

    def __str__(self):
        return f"Equipment {self.equipment_item_id}"