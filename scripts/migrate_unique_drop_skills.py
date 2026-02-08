#!/usr/bin/env python3
"""
고유 드랍 스킬 DB 마이그레이션

1. 82개 신규 드랍 스킬 (8131-8212) DB 삽입
2. 모든 몬스터의 skill_ids 업데이트
"""
import asyncio
import csv
import json
import os
from pathlib import Path
from dotenv import load_dotenv
from tortoise import Tortoise

# 환경변수 로드
load_dotenv()

PROJECT_ROOT = Path("/mnt/SSD/01_Programming/01_Project/98_Misc/CUHABot")

# DB 설정
DB_CONFIG = {
    "connections": {
        "default": {
            "engine": "tortoise.backends.asyncpg",
            "credentials": {
                "host": os.getenv("DATABASE_URL"),
                "port": int(os.getenv("DATABASE_PORT", 5432)),
                "user": os.getenv("DATABASE_USER"),
                "password": os.getenv("DATABASE_PASSWORD"),
                "database": os.getenv("DATABASE_TABLE"),
            }
        }
    },
    "apps": {
        "models": {
            "models": ["models"],
            "default_connection": "default",
        }
    },
}


async def migrate_skills():
    """신규 드랍 스킬 마이그레이션"""
    print("\n=== 1. 신규 드랍 스킬 삽입 ===")

    skills_csv = PROJECT_ROOT / "data" / "skills.csv"

    with open(skills_csv, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        new_skills = [row for row in reader if 8131 <= int(row['ID']) <= 8212]

    print(f"신규 스킬: {len(new_skills)}개")

    from models.skill import Skill_Model

    inserted = 0
    updated = 0

    for row in new_skills:
        skill_id = int(row['ID'])

        # 기존 스킬 확인
        existing = await Skill_Model.filter(id=skill_id).first()

        skill_data = {
            "id": skill_id,
            "name": row['이름'],
            "skill_type": row['타입'],
            "category": row['카테고리'],
            "element": row['속성'],
            "grade": row['등급'],
            "description": row['효과'],
            "source": row['획득처'],
            "keywords": row.get('키워드', ''),
            "config": json.loads(row['config']) if row.get('config') else {},
            "player_obtainable": row.get('플레이어_획득가능', 'N') == 'Y',
        }

        if existing:
            # 업데이트
            await Skill_Model.filter(id=skill_id).update(**skill_data)
            updated += 1
        else:
            # 삽입
            await Skill_Model.create(**skill_data)
            inserted += 1

        if (inserted + updated) % 10 == 0:
            print(f"  진행: {inserted + updated}/{len(new_skills)}")

    print(f"✅ 스킬 삽입: {inserted}개")
    print(f"✅ 스킬 업데이트: {updated}개")


async def migrate_monsters():
    """몬스터 skill_ids 업데이트"""
    print("\n=== 2. 몬스터 skill_ids 업데이트 ===")

    monsters_csv = PROJECT_ROOT / "data" / "monsters.csv"

    with open(monsters_csv, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        monsters = list(reader)

    print(f"총 몬스터: {len(monsters)}마리")

    from models.monster import Monster

    updated = 0

    for row in monsters:
        monster_id = int(row['ID'])

        # skill_ids 파싱
        skill_ids_str = row.get('skill_ids', '[]')
        skill_ids_str = skill_ids_str.replace('[', '').replace(']', '')
        skill_ids = [int(x.strip()) for x in skill_ids_str.split(',') if x.strip()]

        # DB 업데이트
        await Monster.filter(id=monster_id).update(skill_ids=skill_ids)
        updated += 1

        if updated % 20 == 0:
            print(f"  진행: {updated}/{len(monsters)}")

    print(f"✅ 몬스터 업데이트: {updated}마리")


async def verify_migration():
    """마이그레이션 검증"""
    print("\n=== 3. 마이그레이션 검증 ===")

    from models.skill import Skill_Model
    from models.monster import Monster

    # 스킬 확인
    skill_count = await Skill_Model.filter(id__gte=8131, id__lte=8212).count()
    print(f"신규 드랍 스킬: {skill_count}개 (예상: 82개)")

    # 드랍 스킬 보유 몬스터 확인
    monsters = await Monster.all()
    monsters_with_drop = 0

    for monster in monsters:
        has_drop = any(8100 <= sid <= 8999 for sid in monster.skill_ids)
        if has_drop:
            monsters_with_drop += 1

    print(f"드랍 스킬 보유 몬스터: {monsters_with_drop}마리 (예상: 112마리)")

    if skill_count == 82 and monsters_with_drop == 112:
        print("\n✅ 마이그레이션 성공!")
    else:
        print("\n⚠️ 마이그레이션 검증 실패")


async def main():
    """메인 마이그레이션"""
    print("=" * 80)
    print("고유 드랍 스킬 DB 마이그레이션")
    print("=" * 80)

    # Tortoise 초기화
    await Tortoise.init(config=DB_CONFIG)

    try:
        # 마이그레이션 실행
        await migrate_skills()
        await migrate_monsters()
        await verify_migration()

    finally:
        # 연결 종료
        await Tortoise.close_connections()

    print("\n" + "=" * 80)
    print("완료!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
