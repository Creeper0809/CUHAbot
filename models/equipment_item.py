from tortoise import models, fields
from typing import Dict, Optional
from models.grade import Grade
from models.equip_pos import EquipPos
from enum import Enum
from models.base_item import BaseItem

class ItemInfoKey(Enum):
    GRADE = "등급"
    EQUIP_POSITION = "장착 위치"

class StatKey(Enum):
    ATTACK = ("attack", "공격력")
    HP = ("hp", "체력")
    SPEED = ("speed", "속도")

    def __init__(self, key: str, display: str):
        self._key = key
        self._display = display

    @property
    def key(self) -> str:
        return self._key

    @property
    def display(self) -> str:
        return self._display

# 장비 아이템 및 스탯
class EquipmentItem(BaseItem):
    id = fields.BigIntField(pk=True)
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

    @property
    def raw_stats(self) -> Dict[StatKey, Optional[int]]:
        return {
            StatKey.ATTACK: self.attack,
            StatKey.HP: self.hp,
            StatKey.SPEED: self.speed
        }

    async def apply_to_embed(self, embed) -> None:
        
        # 스탯 정보 추가
        self.add_stats_to_embed(embed, self.raw_stats)

        # 등급 정보 추가
        grade_name = await self.get_grade_name()
        if grade_name:
            embed.add_field(
                name=ItemInfoKey.GRADE.value,
                value=f"```      {grade_name}      ```",
                inline=True
            )

        # 장착 위치 정보 추가
        pos_name = await self.get_position_name()
        if pos_name:
            embed.add_field(
                name=ItemInfoKey.EQUIP_POSITION.value,
                value=f"```      {pos_name}      ```",
                inline=True
            )

    async def get_grade_name(self) -> Optional[str]:
        grade = await Grade.get_or_none(id=self.grade)
        return grade.name if grade else None

    async def get_position_name(self) -> Optional[str]:
        pos = await EquipPos.get_or_none(id=self.equip_pos)
        return pos.pos_name if pos else None

    def __str__(self):
        return f"Equipment {self.id}"
