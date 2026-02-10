"""
VoiceChannelLevel 모델에 통계 필드 추가 마이그레이션

실행 방법:
    python scripts/migrate_voice_channel_level_stats.py
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
        logger.info("Adding statistics columns to voice_channel_level table...")

        # total_exp_gained (BIGINT)
        await conn.execute_query(
            "ALTER TABLE voice_channel_level ADD COLUMN total_exp_gained BIGINT DEFAULT 0"
        )
        logger.info("✅ Added total_exp_gained column")

        # active_players (INT)
        await conn.execute_query(
            "ALTER TABLE voice_channel_level ADD COLUMN active_players INT DEFAULT 0"
        )
        logger.info("✅ Added active_players column")

        # intervention_count (INT)
        await conn.execute_query(
            "ALTER TABLE voice_channel_level ADD COLUMN intervention_count INT DEFAULT 0"
        )
        logger.info("✅ Added intervention_count column")

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
