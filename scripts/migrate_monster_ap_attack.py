#!/usr/bin/env python3
"""
몬스터 AP_Attack 컬럼 마이그레이션 + CSV 반영

- monster 테이블에 ap_attack 컬럼이 없으면 추가
- data/monsters.csv 기준으로 AP_Attack/Attack 값을 DB에 업데이트

실행: python scripts/migrate_monster_ap_attack.py
"""
import asyncio
import os
import sys
from pathlib import Path

# 프로젝트 루트 경로 추가
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
from tortoise import Tortoise

load_dotenv()


async def init_db():
    db_url = (
        f"postgres://{os.getenv('DATABASE_USER')}:{os.getenv('DATABASE_PASSWORD')}"
        f"@{os.getenv('DATABASE_URL')}:{os.getenv('DATABASE_PORT')}"
        f"/{os.getenv('DATABASE_TABLE')}"
    )
    await Tortoise.init(
        db_url=db_url,
        modules={"models": ["models"]}
    )


async def ensure_ap_attack_column():
    conn = Tortoise.get_connection("default")
    await conn.execute_script(
        'ALTER TABLE "monster" ADD COLUMN IF NOT EXISTS "ap_attack" INT DEFAULT 0;'
    )


async def migrate():
    from scripts.seed_monsters import seed_monsters

    await init_db()
    await ensure_ap_attack_column()
    await seed_monsters()
    await Tortoise.close_connections()


if __name__ == "__main__":
    asyncio.run(migrate())
