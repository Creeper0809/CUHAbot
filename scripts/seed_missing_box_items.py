#!/usr/bin/env python3
"""
누락된 상자 아이템을 DB에 추가합니다.

실행: python scripts/seed_missing_box_items.py
"""
import asyncio
import csv
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv
from tortoise import Tortoise

from resources.item_emoji import ItemType
from models.item import Item
from models.consume_item import ConsumeItem

load_dotenv()

DATA_DIR = os.path.join(PROJECT_ROOT, "data")
BOX_ITEM_IDS = {
    5920, 5921, 5922, 5923, 5924,
    5930, 5931, 5932, 5933, 5934,
    5940, 5941, 5942, 5943,
    5945, 5946, 5947,
}


def read_csv(filename: str) -> list[dict]:
    filepath = os.path.join(DATA_DIR, filename)
    with open(filepath, "r", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def safe_int(value: str, default: int = 0) -> int:
    if not value or not value.strip():
        return default
    try:
        return int(value.strip())
    except ValueError:
        return default


async def init_db():
    db_url = (
        f"postgres://{os.getenv('DATABASE_USER')}:{os.getenv('DATABASE_PASSWORD')}@"
        f"{os.getenv('DATABASE_URL')}:{os.getenv('DATABASE_PORT')}/{os.getenv('DATABASE_TABLE')}"
    )
    await Tortoise.init(
        db_url=db_url,
        modules={"models": ["models"]}
    )


async def seed_missing_boxes():
    rows = read_csv("items_consumable.csv")
    target_rows = [row for row in rows if int(row["ID"]) in BOX_ITEM_IDS]

    inserted = 0
    for row in target_rows:
        item_id = int(row["ID"])
        name = row.get("이름", "")
        effect = row.get("효과", "")
        cost = safe_int(row.get("가격", "0"))

        item = await Item.get_or_none(id=item_id)
        if not item:
            item = await Item.create(
                id=item_id,
                name=name,
                description=effect,
                cost=cost,
                type=ItemType.CONSUME,
            )

        consume = await ConsumeItem.get_or_none(item_id=item_id)
        if not consume:
            await ConsumeItem.create(item_id=item_id, amount=0)

        inserted += 1

    print(f"✅ 상자 아이템 {inserted}개 확인/추가 완료")


async def main():
    try:
        await init_db()
        await seed_missing_boxes()
    finally:
        await Tortoise.close_connections()


if __name__ == "__main__":
    asyncio.run(main())
