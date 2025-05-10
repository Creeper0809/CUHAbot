import discord
from models.item import Item, ItemType
from models.equipment_item import Grade, EquipPosition
from typing import Optional

# 타입별 이모지
TYPE_EMOJI = {
    ItemType.CONSUME: "🧪",
    ItemType.EQUIP: "⚔️",
    ItemType.SKILL: "📖",
    ItemType.ETC: "📦"
}

# 스탯별 이모지
STAT_EMOJI = {
    "공격력": "⚔️",
    "체력": "❤️",
    "주문력": "🔮",
    "방어력": "🛡️",
    "마법 저항력": "✨"
}

# 아이템 정보
async def get_item_info(item_name: str) -> Optional[discord.Embed]:
    item = await Item.filter(name=item_name).first()
    if not item:
        return None
    return await create_item_embed(item)

# 아이템 스탯이 추가 될 경우 📌로 표시
async def add_equipment_stats(embed: discord.Embed, equipment) -> None:
    stats = equipment.get_stats()
    for stat_name, stat_value in stats.items():
        emoji = STAT_EMOJI.get(stat_name, "📌")
        embed.add_field(name=f"{emoji} {stat_name}",
                        value=f"```      {stat_value}      ```",
                        inline=True)

# 장비 등급 정보 추가
async def add_equipment_grade(embed: discord.Embed, equipment) -> None:
    if not hasattr(equipment, 'grade') or equipment.grade is None:
        return
    try:
        grade = Grade(equipment.grade)
        embed.add_field(name="등급",
                       value=f"```      {grade.name}      ```",
                       inline=True)
    except ValueError:
        pass

# 장비 장착 위치 정보 추가
async def add_equipment_position(embed: discord.Embed, equipment) -> None:
    try:
        pos = EquipPosition(equipment.equip_pos).name
        formatted_pos = pos.replace('_', ' ').title()
        embed.add_field(name="장착 위치",
                        value=f"```      {formatted_pos}      ```",
                        inline=True)
    except (ValueError, AttributeError):
        pass

# 아이템 정보 임베드 생성
async def create_item_embed(item: Item) -> discord.Embed:
    type_icon = TYPE_EMOJI.get(item.type, "📦")
    embed = discord.Embed(
        title=f"{item.name} {type_icon}",
        description=item.description or "설명 없음",
        color=0x00ff00
    )

# 아이템 이미지 추가
    if item.image_link:
        embed.set_thumbnail(url=item.image_link)

# 장비 아이템 추가 정보
    if item.type == ItemType.EQUIP:
        equipment_items = await item.equipment_item.all()
        if equipment_items:
            equipment = equipment_items[0]
            await add_equipment_stats(embed, equipment)
            await add_equipment_grade(embed, equipment)
            await add_equipment_position(embed, equipment)

# 모든 아이템 타입에 공통으로 가격 표시
    embed.add_field(name="💰 가격",
                    value=f"```      {item.cost:,} 골드      ```",
                    inline=True)

    return embed