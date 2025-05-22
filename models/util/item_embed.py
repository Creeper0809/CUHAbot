import discord
from typing import Dict, List
from resources.item_emoji import ItemType, ItemEmoji

class ItemEmbed:
    def __init__(self, item):
        self.item = item
        self.embed = self._create_base_embed()

    # 기본 임베드 생성
    def _create_base_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title=f"{self.item.name} {self._get_type_emoji()}",
            description=self.item.description or "설명 없음",
            color=0x00ff00
        )
        if self.item.image_link:
            embed.set_thumbnail(url=self.item.image_link)
        return embed

    def _get_type_emoji(self) -> str:
        return ItemEmoji.TYPE.get(self.item.type.value, "📦")

    async def build(self) -> discord.Embed:
        await self._add_item_details()
        self._add_cost_info()
        return self.embed

    def _add_cost_info(self) -> None:
        if self.item.cost is not None:
            self._add_field("💰 가격", f"{self.item.cost:,} 골드")

    # 아이템 타입 세부 정보 처리
    async def _get_type_specific_items(self) -> List:
        # 타입 추가 1
        type_mapping = {
            ItemType.EQUIP: ('equipment_item', self.item.equipment_item),
            ItemType.CONSUME: ('consume_item', self.item.consume_item)
        }

        if self.item.type not in type_mapping:
            return []

        field_name, item_query = type_mapping[self.item.type]
        await self.item.fetch_related(field_name)
        return await item_query.all()

    async def _add_item_details(self) -> None:
        items = await self._get_type_specific_items()
        if not items:
            return

        item = items[0]
        self._process_item_stats(item)

        # 타입 추가 2
        type_handlers = {
            ItemType.EQUIP: self._process_equipment_details,
            ItemType.CONSUME: self._process_consume_details
        }

        handler = type_handlers.get(self.item.type)
        if handler:
            await handler(item)

    def _process_item_stats(self, item) -> None:
        stats = item.get_stats()
        self._add_stats(stats)

    def _add_stats(self, stats: Dict[str, any]) -> None:
        for stat_name, stat_value in stats.items():
            emoji = ItemEmoji.STAT.get(stat_name, "📌")
            self._add_field(f"{emoji} {stat_name}", str(stat_value))

    async def _process_equipment_details(self, item) -> None:
        info = await item.get_display_info()
        for name, value in info.items():
            self._add_field(name, value)

    async def _process_consume_details(self, item) -> None:
        pass

    def _add_field(self, name: str, value: str) -> None:
        self.embed.add_field(
            name=name,
            value=f"```      {value}      ```",
            inline=True
        )
