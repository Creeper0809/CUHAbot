"""
auction_listing 테이블에 누락된 컬럼 추가

is_blessed, is_cursed 필드를 추가합니다.
"""
import asyncio
import logging
import os
import sys

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv
from tortoise import Tortoise

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
DATABASE_USER = os.getenv("DATABASE_USER")
DATABASE_PASSWORD = os.getenv("DATABASE_PASSWORD")
DATABASE_PORT = int(os.getenv("DATABASE_PORT") or 0)
DATABASE_TABLE = os.getenv("DATABASE_TABLE")


async def fix_columns():
    """누락된 컬럼 추가"""
    logger.info("데이터베이스 연결 중...")

    await Tortoise.init(
        db_url=f"postgres://{DATABASE_USER}:{DATABASE_PASSWORD}@{DATABASE_URL}:{DATABASE_PORT}/{DATABASE_TABLE}",
        modules={"models": ["models"]},
    )

    conn = Tortoise.get_connection("default")

    logger.info("auction_listing 테이블에 필드 추가 시작")

    try:
        await conn.execute_script("""
            -- is_blessed 필드가 없으면 추가
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'auction_listing'
                    AND column_name = 'is_blessed'
                ) THEN
                    ALTER TABLE auction_listing
                    ADD COLUMN is_blessed BOOLEAN NOT NULL DEFAULT FALSE;
                    RAISE NOTICE 'is_blessed 필드 추가 완료';
                ELSE
                    RAISE NOTICE 'is_blessed 필드가 이미 존재합니다';
                END IF;
            END $$;

            -- is_cursed 필드가 없으면 추가
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'auction_listing'
                    AND column_name = 'is_cursed'
                ) THEN
                    ALTER TABLE auction_listing
                    ADD COLUMN is_cursed BOOLEAN NOT NULL DEFAULT FALSE;
                    RAISE NOTICE 'is_cursed 필드 추가 완료';
                ELSE
                    RAISE NOTICE 'is_cursed 필드가 이미 존재합니다';
                END IF;
            END $$;
        """)
        logger.info("✅ 필드 추가 완료")
    except Exception as e:
        logger.error(f"❌ 필드 추가 실패: {e}")
        raise

    await Tortoise.close_connections()
    logger.info("🎉 완료!")


if __name__ == "__main__":
    asyncio.run(fix_columns())
