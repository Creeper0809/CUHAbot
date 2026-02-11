"""
auction_bid 테이블 컬럼명 수정

bid_at → created_at
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
    """컬럼명 수정"""
    logger.info("데이터베이스 연결 중...")

    await Tortoise.init(
        db_url=f"postgres://{DATABASE_USER}:{DATABASE_PASSWORD}@{DATABASE_URL}:{DATABASE_PORT}/{DATABASE_TABLE}",
        modules={"models": ["models"]},
    )

    conn = Tortoise.get_connection("default")

    logger.info("auction_bid 테이블 컬럼명 수정 시작")

    try:
        await conn.execute_script("""
            -- bid_at을 created_at으로 변경
            DO $$
            BEGIN
                -- bid_at 컬럼이 있으면 created_at으로 이름 변경
                IF EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'auction_bid'
                    AND column_name = 'bid_at'
                ) THEN
                    ALTER TABLE auction_bid
                    RENAME COLUMN bid_at TO created_at;
                    RAISE NOTICE 'bid_at → created_at 변경 완료';
                ELSE
                    RAISE NOTICE 'bid_at 컬럼이 없습니다 (이미 변경되었거나 created_at이 존재함)';
                END IF;
            END $$;
        """)
        logger.info("✅ 컬럼명 수정 완료")
    except Exception as e:
        logger.error(f"❌ 컬럼명 수정 실패: {e}")
        raise

    await Tortoise.close_connections()
    logger.info("🎉 완료!")


if __name__ == "__main__":
    asyncio.run(fix_columns())
