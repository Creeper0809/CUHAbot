"""
User 모델에 last_intervention_time 필드 추가 마이그레이션

실행 방법:
    python scripts/migrate_add_last_intervention_time.py
"""
import asyncio
import logging
import sys
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from tortoise import Tortoise

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def migrate():
    """마이그레이션 실행"""
    import os
    from dotenv import load_dotenv

    # .env 파일 로드
    load_dotenv()

    DATABASE_URL = os.getenv('DATABASE_URL')
    DATABASE_USER = os.getenv('DATABASE_USER')
    DATABASE_PASSWORD = os.getenv('DATABASE_PASSWORD')
    DATABASE_PORT = int(os.getenv('DATABASE_PORT') or 0)
    DATABASE_TABLE = os.getenv('DATABASE_TABLE')

    # Tortoise ORM 초기화
    await Tortoise.init(
        db_url=f"postgres://{DATABASE_USER}:{DATABASE_PASSWORD}@{DATABASE_URL}:{DATABASE_PORT}/{DATABASE_TABLE}",
        modules={"models": ["models"]},
    )

    # 마이그레이션 SQL 실행
    conn = Tortoise.get_connection("default")

    try:
        # User 테이블에 last_intervention_time 컬럼 추가
        logger.info("Adding last_intervention_time column to users table...")
        await conn.execute_query(
            "ALTER TABLE users ADD COLUMN last_intervention_time TIMESTAMP NULL DEFAULT NULL"
        )
        logger.info("✅ Migration completed successfully!")

    except Exception as e:
        if "Duplicate column name" in str(e):
            logger.warning("⚠️ Column last_intervention_time already exists, skipping migration")
        else:
            logger.error(f"❌ Migration failed: {e}")
            raise

    finally:
        await Tortoise.close_connections()


if __name__ == "__main__":
    asyncio.run(migrate())
