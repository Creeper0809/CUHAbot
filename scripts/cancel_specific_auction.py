"""
특정 경매 삭제 스크립트

경매 ID를 입력받아 해당 경매를 취소합니다.
"""
import asyncio
import logging
import os
import sys

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv
from tortoise import Tortoise
from models.auction_listing import AuctionListing, AuctionStatus

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
DATABASE_USER = os.getenv("DATABASE_USER")
DATABASE_PASSWORD = os.getenv("DATABASE_PASSWORD")
DATABASE_PORT = int(os.getenv("DATABASE_PORT") or 0)
DATABASE_TABLE = os.getenv("DATABASE_TABLE")


async def cancel_auction(listing_id: int):
    """특정 경매 취소"""
    logger.info("데이터베이스 연결 중...")

    await Tortoise.init(
        db_url=f"postgres://{DATABASE_USER}:{DATABASE_PASSWORD}@{DATABASE_URL}:{DATABASE_PORT}/{DATABASE_TABLE}",
        modules={"models": ["models"]},
    )

    try:
        # 경매 조회
        listing = await AuctionListing.get_or_none(id=listing_id).prefetch_related("inventory_item")

        if not listing:
            logger.error(f"❌ 경매 ID {listing_id}를 찾을 수 없습니다")
            return

        logger.info(f"경매 정보: {listing.item_name} (상태: {listing.status})")

        # 취소
        listing.status = AuctionStatus.CANCELLED
        await listing.save()

        # 아이템 잠금 해제
        if listing.inventory_item:
            listing.inventory_item.is_locked = False
            await listing.inventory_item.save()
            logger.info(f"✅ 아이템 잠금 해제됨")

        logger.info(f"✅ 경매 ID {listing_id} 취소 완료")

    except Exception as e:
        logger.error(f"❌ 경매 취소 실패: {e}")
        raise
    finally:
        await Tortoise.close_connections()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("사용법: python cancel_specific_auction.py <경매_ID>")
        print("예시: python cancel_specific_auction.py 1")
        sys.exit(1)

    listing_id = int(sys.argv[1])
    asyncio.run(cancel_auction(listing_id))
