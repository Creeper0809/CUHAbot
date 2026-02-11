"""
잘못 추가된 상점 장비 아이템 삭제 (8963-9080)
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from tortoise import Tortoise
from models import Item, EquipmentItem

load_dotenv()


async def cleanup():
    await Tortoise.init(
        db_url=f"postgres://{os.getenv('DATABASE_USER')}:{os.getenv('DATABASE_PASSWORD')}@"
               f"{os.getenv('DATABASE_URL')}:{os.getenv('DATABASE_PORT')}/{os.getenv('DATABASE_TABLE')}",
        modules={"models": ["models"]}
    )

    # 8963~9080 아이템 삭제
    deleted_equip = await EquipmentItem.filter(item_id__gte=8963, item_id__lte=9080).delete()
    deleted_items = await Item.filter(id__gte=8963, id__lte=9080).delete()

    print(f"EquipmentItem 삭제: {deleted_equip}개")
    print(f"Item 삭제: {deleted_items}개")

    await Tortoise.close_connections()


if __name__ == "__main__":
    asyncio.run(cleanup())
