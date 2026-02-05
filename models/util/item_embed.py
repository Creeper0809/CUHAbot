import discord
from typing import Dict, List
from resources.item_emoji import ItemType, EmojiManager

class ItemEmbed:
    @staticmethod
    async def create_description_embed(item) -> discord.Embed:
        # 기본 임베드 생성
        emoji_manager = EmojiManager.get_instance()
        embed = discord.Embed(
            title=f"{item.name} {emoji_manager.get_type_emoji(item.type or ItemType.ETC)}",
            description=item.description or "설명 없음",
            color=0x00ff00
        )

        # 이미지 설정
        item.image_link and embed.set_thumbnail(url=item.image_link)

        # 아이템 타입별 세부 정보 추가
        if item.type and item.type != ItemType.ETC:
            # 타입별 관계 이름 매핑
            type_relation_mapping = {
                ItemType.EQUIP: 'equipment_item',
                ItemType.CONSUME: 'consume_item',
                ItemType.SKILL: 'skill_item'
            }
            
            relation_name = type_relation_mapping.get(item.type)
            if relation_name:
                try:
                    await item.fetch_related(relation_name)
                    type_items = await getattr(item, relation_name).all()
                    if type_items:
                        await type_items[0].apply_to_embed(embed)
                except:
                    # 관계가 없는 경우 ETC 처리
                    item.type = ItemType.ETC

        item.cost is not None and embed.add_field(
            name=f"가격 {emoji_manager.get_gold_emoji()}",
            value=f"```      {item.cost:,} 골드      ```",
            inline=True
        )

        return embed