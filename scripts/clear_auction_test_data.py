"""
경매 테스트 데이터 삭제 스크립트

모든 경매 관련 데이터를 초기화합니다.
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


async def clear_auction_data():
    """경매 테스트 데이터 삭제"""
    logger.info("데이터베이스 연결 중...")

    await Tortoise.init(
        db_url=f"postgres://{DATABASE_USER}:{DATABASE_PASSWORD}@{DATABASE_URL}:{DATABASE_PORT}/{DATABASE_TABLE}",
        modules={"models": ["models"]},
    )

    conn = Tortoise.get_connection("default")

    logger.info("경매 데이터 삭제 시작")

    try:
        # 1. 입찰 기록 삭제
        result = await conn.execute_query("DELETE FROM auction_bid")
        logger.info(f"✅ auction_bid 삭제 완료 ({result[0]} rows)")

        # 2. 구매 주문 삭제
        result = await conn.execute_query("DELETE FROM buy_order")
        logger.info(f"✅ buy_order 삭제 완료 ({result[0]} rows)")

        # 3. 경매 내역 삭제
        result = await conn.execute_query("DELETE FROM auction_history")
        logger.info(f"✅ auction_history 삭제 완료 ({result[0]} rows)")

        # 4. 경매 리스팅 삭제 (잠긴 아이템도 해제됨)
        result = await conn.execute_query("DELETE FROM auction_listing")
        logger.info(f"✅ auction_listing 삭제 완료 ({result[0]} rows)")

        # 5. 잠긴 아이템 해제
        result = await conn.execute_query(
            "UPDATE user_inventory SET is_locked = FALSE WHERE is_locked = TRUE"
        )
        logger.info(f"✅ 잠긴 아이템 해제 완료 ({result[0]} rows)")

    except Exception as e:
        logger.error(f"❌ 데이터 삭제 실패: {e}")
        raise

    await Tortoise.close_connections()
    logger.info("🎉 완료!")


if __name__ == "__main__":
    asyncio.run(clear_auction_data())
