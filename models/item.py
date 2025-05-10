from tortoise import Model, fields
from tortoise.fields import ReverseRelation
from enum import Enum

# 아이템 타입 정의
class ItemType(Enum):
    CONSUME = 'consume'
    EQUIP = 'equip'
    SKILL = 'skill'
    ETC = 'etc'

# 전체 아이템 정보
class Item(Model):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=50, null=True)
    description = fields.CharField(max_length=50, null=True)
    image_link = fields.TextField(null=True)
    cost = fields.IntField()
    emoji_id = fields.TextField(null=True)
    type = fields.CharEnumField(enum_type=ItemType, null=True)

    class Meta:
        table = "item"

    equipment_item = ReverseRelation["EquipmentItem"]

# 장비 아이템 정보 추가
    async def create_equipment(self, equipment_data):
        if self.type == ItemType.EQUIP:
            from models.equipment_item import EquipmentItem
            equipment = await EquipmentItem.create(
                item=self,
                attack=equipment_data.get('attack'),
                hp=equipment_data.get('hp'),
                ap_attack=equipment_data.get('ap_attack'),
                ad_defanse=equipment_data.get('ad_defanse'),
                ap_defanse=equipment_data.get('ap_defanse'),
                grade=equipment_data.get('grade'),
                equip_pos=equipment_data.get('equip_pos')
            )
            return equipment
        return None

    def __str__(self):
        return self.name or str(self.id)