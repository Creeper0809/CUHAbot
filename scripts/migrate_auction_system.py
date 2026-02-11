"""
경매 시스템 마이그레이션 스크립트

- UserInventory에 is_locked 필드 추가
- 새 테이블 생성: auction_listing, auction_bid, buy_order, auction_history
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


async def migrate():
    """마이그레이션 실행"""
    logger.info("데이터베이스 연결 중...")

    await Tortoise.init(
        db_url=f"postgres://{DATABASE_USER}:{DATABASE_PASSWORD}@{DATABASE_URL}:{DATABASE_PORT}/{DATABASE_TABLE}",
        modules={"models": ["models"]},
    )

    conn = Tortoise.get_connection("default")

    logger.info("마이그레이션 시작")

    # 1. UserInventory에 필드 추가
    try:
        logger.info("1/5: UserInventory에 필드 추가 중...")
        await conn.execute_script("""
            -- is_blessed 필드가 없으면 추가
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'user_inventory'
                    AND column_name = 'is_blessed'
                ) THEN
                    ALTER TABLE user_inventory
                    ADD COLUMN is_blessed BOOLEAN NOT NULL DEFAULT FALSE;
                END IF;
            END $$;

            -- is_cursed 필드가 없으면 추가
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'user_inventory'
                    AND column_name = 'is_cursed'
                ) THEN
                    ALTER TABLE user_inventory
                    ADD COLUMN is_cursed BOOLEAN NOT NULL DEFAULT FALSE;
                END IF;
            END $$;

            -- is_locked 필드가 없으면 추가
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'user_inventory'
                    AND column_name = 'is_locked'
                ) THEN
                    ALTER TABLE user_inventory
                    ADD COLUMN is_locked BOOLEAN NOT NULL DEFAULT FALSE;
                END IF;
            END $$;
        """)
        logger.info("✅ UserInventory 필드 추가 완료 (is_blessed, is_cursed, is_locked)")
    except Exception as e:
        logger.error(f"❌ UserInventory 필드 추가 실패: {e}")
        raise

    # 2. auction_listing 테이블 생성
    try:
        logger.info("2/5: auction_listing 테이블 생성 중...")
        await conn.execute_script("""
            CREATE TABLE IF NOT EXISTS auction_listing (
                id BIGSERIAL PRIMARY KEY,

                -- 판매자
                seller_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,

                -- 에스크로: 등록된 아이템 (판매 후 NULL)
                inventory_item_id BIGINT REFERENCES user_inventory(id) ON DELETE SET NULL,

                -- 아이템 스냅샷 (판매 후에도 히스토리 유지)
                item_id INT NOT NULL,
                item_name VARCHAR(255) NOT NULL,
                enhancement_level INT NOT NULL DEFAULT 0,
                instance_grade INT NOT NULL DEFAULT 0,
                is_blessed BOOLEAN NOT NULL DEFAULT FALSE,
                is_cursed BOOLEAN NOT NULL DEFAULT FALSE,
                special_effects JSONB,

                -- 경매 타입: 'bid' (입찰) 또는 'buynow' (즉시구매)
                auction_type VARCHAR(20) NOT NULL,

                -- 상태: 'active', 'sold', 'expired', 'cancelled'
                status VARCHAR(20) NOT NULL DEFAULT 'active',

                -- 가격
                starting_price BIGINT NOT NULL,
                buyout_price BIGINT,  -- 입찰 경매에서 즉구가 (optional)
                current_price BIGINT NOT NULL,  -- 현재가 (입찰 최고가 or 즉구가)

                -- 시간
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                expires_at TIMESTAMPTZ NOT NULL,

                -- 판매 정보
                buyer_id BIGINT,
                sold_at TIMESTAMPTZ,
                final_price BIGINT
            );

            -- 인덱스
            CREATE INDEX IF NOT EXISTS idx_auction_status_expires
                ON auction_listing(status, expires_at);
            CREATE INDEX IF NOT EXISTS idx_auction_seller_status
                ON auction_listing(seller_id, status);
            CREATE INDEX IF NOT EXISTS idx_auction_status_item
                ON auction_listing(status, item_id);
        """)
        logger.info("✅ auction_listing 테이블 생성 완료")
    except Exception as e:
        logger.error(f"❌ auction_listing 테이블 생성 실패: {e}")
        raise

    # 3. auction_bid 테이블 생성
    try:
        logger.info("3/5: auction_bid 테이블 생성 중...")
        await conn.execute_script("""
            CREATE TABLE IF NOT EXISTS auction_bid (
                id BIGSERIAL PRIMARY KEY,

                -- 경매
                auction_id BIGINT NOT NULL REFERENCES auction_listing(id) ON DELETE CASCADE,

                -- 입찰자
                bidder_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,

                -- 입찰 금액 (에스크로로 차감됨)
                bid_amount BIGINT NOT NULL,

                -- 환불 여부
                is_refunded BOOLEAN NOT NULL DEFAULT FALSE,

                -- 입찰 시간
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );

            -- 인덱스
            CREATE INDEX IF NOT EXISTS idx_bid_auction_amount
                ON auction_bid(auction_id, bid_amount DESC);
            CREATE INDEX IF NOT EXISTS idx_bid_bidder_refunded
                ON auction_bid(bidder_id, is_refunded);
        """)
        logger.info("✅ auction_bid 테이블 생성 완료")
    except Exception as e:
        logger.error(f"❌ auction_bid 테이블 생성 실패: {e}")
        raise

    # 4. buy_order 테이블 생성
    try:
        logger.info("4/5: buy_order 테이블 생성 중...")
        await conn.execute_script("""
            CREATE TABLE IF NOT EXISTS buy_order (
                id BIGSERIAL PRIMARY KEY,

                -- 구매자
                buyer_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,

                -- 원하는 아이템 조건
                item_id INT NOT NULL,
                min_enhancement_level INT NOT NULL DEFAULT 0,
                max_enhancement_level INT NOT NULL DEFAULT 99,
                min_instance_grade INT NOT NULL DEFAULT 0,
                max_instance_grade INT NOT NULL DEFAULT 8,

                -- 가격
                max_price BIGINT NOT NULL,

                -- 에스크로: 주문 시 골드 차감
                escrowed_gold BIGINT NOT NULL,

                -- 시간
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                expires_at TIMESTAMPTZ NOT NULL,

                -- 상태: 'active', 'fulfilled', 'cancelled', 'expired'
                status VARCHAR(20) NOT NULL DEFAULT 'active',

                -- 체결 정보
                seller_id BIGINT,
                fulfilled_at TIMESTAMPTZ,
                final_price BIGINT
            );

            -- 인덱스
            CREATE INDEX IF NOT EXISTS idx_buy_order_status_item
                ON buy_order(status, item_id);
            CREATE INDEX IF NOT EXISTS idx_buy_order_buyer_status
                ON buy_order(buyer_id, status);
        """)
        logger.info("✅ buy_order 테이블 생성 완료")
    except Exception as e:
        logger.error(f"❌ buy_order 테이블 생성 실패: {e}")
        raise

    # 5. auction_history 테이블 생성
    try:
        logger.info("5/5: auction_history 테이블 생성 중...")
        await conn.execute_script("""
            CREATE TABLE IF NOT EXISTS auction_history (
                id BIGSERIAL PRIMARY KEY,

                -- 아이템 정보 (가격 히스토리 키)
                item_id INT NOT NULL,
                enhancement_level INT NOT NULL DEFAULT 0,
                instance_grade INT NOT NULL DEFAULT 0,

                -- 거래 정보
                sale_price BIGINT NOT NULL,
                sale_type VARCHAR(20) NOT NULL,  -- 'auction', 'buynow', 'buy_order'
                sold_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

                -- 거래 당사자
                seller_id BIGINT NOT NULL,
                buyer_id BIGINT NOT NULL
            );

            -- 인덱스 (가격 히스토리 조회용)
            CREATE INDEX IF NOT EXISTS idx_history_item_combo
                ON auction_history(item_id, enhancement_level, instance_grade, sold_at DESC);
        """)
        logger.info("✅ auction_history 테이블 생성 완료")
    except Exception as e:
        logger.error(f"❌ auction_history 테이블 생성 실패: {e}")
        raise

    logger.info("🎉 마이그레이션 완료!")

    await Tortoise.close_connections()


if __name__ == "__main__":
    asyncio.run(migrate())
