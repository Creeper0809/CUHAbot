#!/usr/bin/env python3
"""
레이드 시스템 마이그레이션

실행:
    python scripts/migrate_raid_system.py

기능:
1) 레이드 관련 테이블 스키마 생성 (없을 때만)
2) 레이드 CSV(data/raid_*.csv, data/raids.csv) 기준 리시드
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
        f"postgres://{os.getenv('DATABASE_USER')}:{os.getenv('DATABASE_PASSWORD')}@"
        f"{os.getenv('DATABASE_URL')}:{os.getenv('DATABASE_PORT')}/{os.getenv('DATABASE_TABLE')}"
    )
    await Tortoise.init(
        db_url=db_url,
        modules={"models": ["models"]},
    )


async def migrate_schema():
    # 새 모델 기준 테이블 생성 (safe=True: 기존 테이블 보존)
    await Tortoise.generate_schemas(safe=True)

    # raid_boss_skill.skill_id 컬럼 추가 (기존 DB 호환)
    conn = Tortoise.get_connection("default")
    check_query = """
    SELECT column_name
    FROM information_schema.columns
    WHERE table_name='raid_boss_skill' AND column_name='skill_id';
    """
    result = await conn.execute_query_dict(check_query)
    if not result:
        await conn.execute_script(
            "ALTER TABLE raid_boss_skill ADD COLUMN skill_id INTEGER NULL;"
        )


async def reseed_raid_data():
    from models.raid import (
        Raid,
        RaidTargetingRule,
        RaidSpecialAction,
        RaidMinigame,
        RaidPhaseTransition,
        RaidPart,
        RaidGimmick,
        RaidBossSkill,
    )
    from scripts.seed_from_csv import seed_raids

    # 레이드 테이블만 비우고 CSV로 재삽입
    await RaidBossSkill.all().delete()
    await RaidGimmick.all().delete()
    await RaidPart.all().delete()
    await RaidPhaseTransition.all().delete()
    await RaidMinigame.all().delete()
    await RaidSpecialAction.all().delete()
    await RaidTargetingRule.all().delete()
    await Raid.all().delete()

    await seed_raids()


async def main():
    try:
        print("=" * 60)
        print("RAID SYSTEM MIGRATION START")
        print("=" * 60)
        await init_db()
        print("1) DB connected")

        await migrate_schema()
        print("2) Schema migration done")

        await reseed_raid_data()
        print("3) Raid CSV seed done")

        print("=" * 60)
        print("RAID SYSTEM MIGRATION COMPLETE")
        print("=" * 60)
    finally:
        await Tortoise.close_connections()


if __name__ == "__main__":
    asyncio.run(main())
