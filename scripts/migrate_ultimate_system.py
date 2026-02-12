#!/usr/bin/env python3
"""
궁극기 슬롯 테이블 생성 마이그레이션

실행: python scripts/migrate_ultimate_system.py
"""
import asyncio
import os
import sys

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
    await Tortoise.init(
        db_url=db_url,
        modules={"models": ["models"]},
    )


async def migrate_ultimate_table():
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
    CREATE TABLE IF NOT EXISTS user_ultimate_deck (
        id BIGSERIAL PRIMARY KEY,
        user_id INT NOT NULL REFERENCES "{user_table}"(id) ON DELETE CASCADE,
        skill_id INT NOT NULL DEFAULT 0,
        mode VARCHAR(10) NOT NULL DEFAULT 'manual',
        UNIQUE (user_id)
    );
    """
    await conn.execute_script(create_table_sql)


async def main():
    try:
        print("궁극기 시스템 마이그레이션 시작")
        await init_db()
        await migrate_ultimate_table()
        print("궁극기 시스템 마이그레이션 완료")
    finally:
        await Tortoise.close_connections()


if __name__ == "__main__":
    asyncio.run(main())
