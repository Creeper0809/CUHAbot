from tortoise import Model, fields
from tortoise.fields import ReverseRelation
import discord
from resources.item_emoji import ItemType
from models.util.item_embed import ItemEmbed

    # 아이템 기본 속성
class Item(Model):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=50, null=True)
    description = fields.CharField(max_length=50, null=True)
    image_link = fields.TextField(null=True)
    cost = fields.IntField(null=True)
    emoji_id = fields.TextField(null=True)
    type = fields.CharEnumField(ItemType, null=True)

    # 다른 아이템 타입과 관계
    equipment_item = ReverseRelation["EquipmentItem"]
    consume_item = ReverseRelation["ConsumeItem"]

    class Meta:
        table = "item"

    async def get_description_embed(self) -> discord.Embed:
        return await ItemEmbed.create_description_embed(self)

    def __str__(self):
        return self.name or str(self.id)
