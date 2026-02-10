"""
상점용 레벨 1 장비 추가 스크립트

실행: python scripts/add_shop_equipment.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from tortoise import Tortoise
from models import Item, EquipmentItem
from resources.item_emoji import ItemType

load_dotenv()


async def init_db():
    await Tortoise.init(
        db_url=f"postgres://{os.getenv('DATABASE_USER')}:{os.getenv('DATABASE_PASSWORD')}@"
               f"{os.getenv('DATABASE_URL')}:{os.getenv('DATABASE_PORT')}/{os.getenv('DATABASE_TABLE')}",
        modules={"models": ["models"]}
    )


async def add_items():
    await init_db()

    items_to_add = [
        {
            "id": 8960,
            "name": "초보자 단검",
            "description": "초보 모험가를 위한 간단한 단검. 작지만 날카롭다.",
            "cost": 80,
            "type": ItemType.EQUIP,
            "equip_pos": 4,  # 무기
            "require_level": 1,
            "attack": 3,
            "acquisition_source": "상점",
        },
        {
            "id": 8961,
            "name": "천 모자",
            "description": "천으로 만든 간단한 모자. 기본적인 보호만 제공한다.",
            "cost": 50,
            "type": ItemType.EQUIP,
            "equip_pos": 1,  # 투구
            "require_level": 1,
            "hp": 15,
            "ad_defense": 2,
            "ap_defense": 2,
            "acquisition_source": "상점",
        },
        {
            "id": 8962,
            "name": "나무 목걸이",
            "description": "나무로 만든 소박한 목걸이. 약간의 행운을 가져다준다.",
            "cost": 70,
            "type": ItemType.EQUIP,
            "equip_pos": 7,  # 목걸이
            "require_level": 1,
            "config": '{"components": [{"tag": "passive_buff", "gold_bonus": 3}]}',
            "acquisition_source": "상점",
        },
    ]

    added = 0
    for item_data in items_to_add:
        # Check if item already exists
        existing_item = await Item.get_or_none(id=item_data["id"])
        if existing_item:
            print(f"Item {item_data['id']} already exists, skipping...")
            continue

        # Create Item
        item = await Item.create(
            id=item_data["id"],
            name=item_data["name"],
            description=item_data["description"],
            cost=item_data["cost"],
            type=item_data["type"],
        )
        print(f"Created Item: {item.name} (ID: {item.id})")

        # Create EquipmentItem
        equip_data = {
            "item_id": item.id,
            "equip_pos": item_data.get("equip_pos"),
            "require_level": item_data.get("require_level", 1),
            "attack": item_data.get("attack", 0),
            "hp": item_data.get("hp", 0),
            "ad_defense": item_data.get("ad_defense", 0),
            "ap_defense": item_data.get("ap_defense", 0),
            "speed": item_data.get("speed", 0),
            "acquisition_source": item_data.get("acquisition_source", ""),
        }

        # Only add config if it exists
        if item_data.get("config"):
            equip_data["config"] = item_data["config"]

        equip = await EquipmentItem.create(**equip_data)
        print(f"Created EquipmentItem: {item.name}")
        added += 1

    print(f"\nTotal items added: {added}")
    await Tortoise.close_connections()
    print("Complete.")


if __name__ == "__main__":
    asyncio.run(add_items())
