"""
장비 아이템에 acquisition_source 컬럼 추가 마이그레이션

equipment_item 테이블에 acquisition_source 컬럼을 추가하고
CSV의 획득처 데이터로 업데이트합니다.

실행: python scripts/migrate_equipment_acquisition_source.py
"""
import asyncio
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from tortoise import Tortoise

load_dotenv()


async def init_db():
    await Tortoise.init(
        db_url=f"postgres://{os.getenv('DATABASE_USER')}:{os.getenv('DATABASE_PASSWORD')}@"
               f"{os.getenv('DATABASE_URL')}:{os.getenv('DATABASE_PORT')}/{os.getenv('DATABASE_TABLE')}",
        modules={"models": ["models"]}
    )


async def migrate():
    await init_db()
    conn = Tortoise.get_connection("default")

    # 1. 컬럼 추가
    print("Adding acquisition_source column to equipment_item...")
    await conn.execute_script(
        'ALTER TABLE "equipment_item" ADD COLUMN IF NOT EXISTS "acquisition_source" VARCHAR(50) DEFAULT \'\';'
    )
    print("Column added.")

    # 2. CSV에서 획득처 데이터 읽어서 업데이트
    csv_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data", "items_equipment.csv"
    )

    if not os.path.exists(csv_path):
        print(f"CSV not found: {csv_path}")
        await Tortoise.close_connections()
        return

    updated = 0
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            item_id = row.get("ID", "").strip()
            source = row.get("획득처", "").strip()

            if not item_id or not source:
                continue

            await conn.execute_query(
                'UPDATE "equipment_item" SET "acquisition_source" = $1 '
                'WHERE "equipment_item_id" = $2',
                [source, int(item_id)]
            )
            updated += 1

    print(f"Updated {updated} equipment items with acquisition_source.")
    await Tortoise.close_connections()
    print("Migration complete.")


if __name__ == "__main__":
    asyncio.run(migrate())
