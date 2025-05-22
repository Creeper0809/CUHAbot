from typing import Optional
import discord
from models.item import Item

class ItemService:
    @staticmethod
    async def get_item_info(item_name: str) -> Optional[discord.Embed]:
        item = await Item.filter(name=item_name).first()
        return await item.get_description_embed() if item else None
