from tortoise import models, fields
from typing import Dict, Optional
from models.grade import Grade
from models.equip_pos import EquipPos

# 장비 아이템 및 스탯
class EquipmentItem(models.Model):
    id = fields.BigIntField(pk=True)
    equipment_item_id = fields.IntField(null=True)
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

    # 장비 스탯 정보를 딕셔너리 형태로 변환, 스탯 매핑
    def get_stats(self) -> Dict[str, int]:
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

    async def get_display_info(self) -> Dict[str, str]:
        info = {}
        grade_name = await self.get_grade_name()
        if grade_name:
            info['등급'] = grade_name

        pos_name = await self.get_position_name()
        if pos_name:
            info['장착 위치'] = pos_name

        return info

    async def get_grade_name(self) -> Optional[str]:
        grade = await Grade.get_or_none(id=self.grade)
        return grade.name if grade else None

    async def get_position_name(self) -> Optional[str]:
        pos = await EquipPos.get_or_none(id=self.equip_pos)
        return pos.pos_name if pos else None

    def __str__(self):
        return f"Equipment {self.equipment_item_id}"
