#!/usr/bin/env python3
"""
주간 타워 테이블 생성 및 초기 데이터 마이그레이션

실행: python scripts/migrate_tower_system.py
"""
import asyncio
import os
import sys

# 프로젝트 루트를 path에 추가
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv
from tortoise import Tortoise

load_dotenv()


async def init_db():
    db_url = (
        f"postgres://{os.getenv('DATABASE_USER')}:"
        f"{os.getenv('DATABASE_PASSWORD')}@{os.getenv('DATABASE_URL')}"
        f":{os.getenv('DATABASE_PORT')}/{os.getenv('DATABASE_TABLE')}"
    )
    print(f"📡 데이터베이스 연결 중: {os.getenv('DATABASE_URL')}:{os.getenv('DATABASE_PORT')}/{os.getenv('DATABASE_TABLE')}")

    await Tortoise.init(
        db_url=db_url,
        modules={"models": ["models"]}
    )


async def migrate_tower_progress():
    conn = Tortoise.get_connection("default")

    table_check_sql = """
    SELECT table_name
    FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name IN ('user', 'users');
    """
    table_rows = await conn.execute_query_dict(table_check_sql)
    table_names = {row["table_name"] for row in table_rows}
    if "user" in table_names:
        user_table = "user"
    elif "users" in table_names:
        user_table = "users"
    else:
        raise RuntimeError("User 테이블을 찾을 수 없습니다. 먼저 DB 초기화를 진행하세요.")

    create_table_sql = f"""
    CREATE TABLE IF NOT EXISTS user_tower_progress (
        id SERIAL PRIMARY KEY,
        user_id INT NOT NULL REFERENCES "{user_table}"(id) ON DELETE CASCADE,
        season_id INT NOT NULL DEFAULT 1,
        highest_floor_reached INT NOT NULL DEFAULT 0,
        current_floor INT NOT NULL DEFAULT 0,
        rewards_claimed JSONB NOT NULL DEFAULT '[]'::jsonb,
        tower_coins INT NOT NULL DEFAULT 0,
        last_attempt_time TIMESTAMPTZ NULL,
        season_start_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE (user_id, season_id)
    );
    """

    print("\n📋 주간 타워 테이블 생성 중...")
    await conn.execute_script(create_table_sql)
    print("✅ user_tower_progress 테이블 확인/생성 완료")

    print("\n🧩 기존 유저 진행도 초기화 중...")
    seed_sql = f"""
    INSERT INTO user_tower_progress (user_id, season_id, highest_floor_reached, current_floor, rewards_claimed, tower_coins, last_attempt_time, season_start_time)
    SELECT u.id, 1, 0, 0, '[]'::jsonb, 0, NULL, NOW()
    FROM "{user_table}" u
    WHERE NOT EXISTS (
        SELECT 1 FROM user_tower_progress p
        WHERE p.user_id = u.id AND p.season_id = 1
    );
    """
    await conn.execute_script(seed_sql)
    print("✅ 초기 진행도 생성 완료")


async def main():
    try:
        print("=" * 60)
        print("🗼 주간 타워 마이그레이션 시작")
        print("=" * 60)

        await init_db()
        await migrate_tower_progress()

        print("\n✨ 주간 타워 마이그레이션 완료")
    finally:
        await Tortoise.close_connections()


if __name__ == "__main__":
    asyncio.run(main())
