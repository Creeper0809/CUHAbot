import discord
from models.item import Item

class ItemNotFoundException(Exception):
    pass

async def get_item_info(item_name: str) -> discord.Embed:
    item = await Item.filter(name=item_name).first()
    if not item:
        raise ItemNotFoundException(f"'{item_name}' 아이템을 찾을 수 없습니다.")
    return await item.get_description_embed()
