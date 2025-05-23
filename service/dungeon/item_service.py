import discord
from models.item import Item
from models.util.item_embed import ItemEmbed

class ItemNotFoundException(Exception):
    pass

class ItemService:
    @staticmethod
    async def get_item_info(item_name: str) -> discord.Embed:
        item = await Item.filter(name=item_name).first()
        if not item:
            raise ItemNotFoundException(f"'{item_name}' 아이템을 찾을 수 없습니다.")
        item_embed = ItemEmbed(item)
        return await item_embed.build()
