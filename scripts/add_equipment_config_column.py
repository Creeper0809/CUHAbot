"""
equipment_item 테이블에 config 컬럼 추가

DB 마이그레이션 스크립트
"""
import asyncio
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
from tortoise import Tortoise

load_dotenv()


async def add_config_column():
    """equipment_item 테이블에 config 컬럼 추가"""
    db_url = (
        f"postgres://{os.getenv('DATABASE_USER')}:{os.getenv('DATABASE_PASSWORD')}@"
        f"{os.getenv('DATABASE_URL')}:{os.getenv('DATABASE_PORT')}/{os.getenv('DATABASE_TABLE')}"
    )

    await Tortoise.init(
        db_url=db_url,
        modules={"models": ["models"]}
    )

    conn = Tortoise.get_connection("default")

    # config 컬럼 추가
    try:
        await conn.execute_query(
            'ALTER TABLE equipment_item ADD COLUMN IF NOT EXISTS config JSONB;'
        )
        print("✅ equipment_item.config 컬럼 추가 완료")
    except Exception as e:
        print(f"❌ 오류: {e}")

    await Tortoise.close_connections()


if __name__ == "__main__":
    asyncio.run(add_config_column())
