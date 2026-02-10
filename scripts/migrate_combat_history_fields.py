"""
CombatHistory 모델에 멀티플레이어 및 난이도 필드 추가 마이그레이션

실행 방법:
    python scripts/migrate_combat_history_fields.py
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
        logger.info("Adding columns to combat_history table...")

        # participant_ids (JSON)
        await conn.execute_query(
            "ALTER TABLE combat_history ADD COLUMN participant_ids JSON DEFAULT ('[]')"
        )
        logger.info("✅ Added participant_ids column")

        # participants_count (INT)
        await conn.execute_query(
            "ALTER TABLE combat_history ADD COLUMN participants_count INT DEFAULT 1"
        )
        logger.info("✅ Added participants_count column")

        # difficulty_multiplier (FLOAT)
        await conn.execute_query(
            "ALTER TABLE combat_history ADD COLUMN difficulty_multiplier FLOAT DEFAULT 1.0"
        )
        logger.info("✅ Added difficulty_multiplier column")

        # dungeon_name (VARCHAR)
        await conn.execute_query(
            "ALTER TABLE combat_history ADD COLUMN dungeon_name VARCHAR(100) NULL DEFAULT NULL"
        )
        logger.info("✅ Added dungeon_name column")

        # monster_level (INT)
        await conn.execute_query(
            "ALTER TABLE combat_history ADD COLUMN monster_level INT DEFAULT 1"
        )
        logger.info("✅ Added monster_level column")

        logger.info("✅ All migrations completed successfully!")

    except Exception as e:
        if "Duplicate column name" in str(e):
            logger.warning(f"⚠️ Some columns already exist, skipping: {e}")
        else:
            logger.error(f"❌ Migration failed: {e}")
            raise

    finally:
        await Tortoise.close_connections()


if __name__ == "__main__":
    asyncio.run(migrate())
