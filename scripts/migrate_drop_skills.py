#!/usr/bin/env python3
"""
몬스터 드랍 스킬 데이터베이스 마이그레이션 스크립트

1. 새로운 8100번대 스킬을 데이터베이스에 추가
2. 몬스터의 skill_ids 업데이트
"""
import asyncio
import csv
import json
import os
import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tortoise import Tortoise
from models.skill import Skill_Model
from models.monster import Monster
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

# 데이터베이스 URL 구성
DATABASE_URL = f"postgres://{os.getenv('DATABASE_USER')}:{os.getenv('DATABASE_PASSWORD')}@{os.getenv('DATABASE_URL')}:{os.getenv('DATABASE_PORT')}/{os.getenv('DATABASE_TABLE')}"


async def migrate_drop_skills():
    """드랍 스킬 마이그레이션 메인 함수"""

    # DB 초기화
    await Tortoise.init(
        db_url=DATABASE_URL,
        modules={"models": ["models"]}
    )

    print(f"Connected to database: {os.getenv('DATABASE_TABLE')}")

    # 1. 스킬 CSV에서 8100번대 스킬 읽기
    skills_csv = PROJECT_ROOT / "data" / "skills.csv"
    print(f"\n[1/2] Reading new skills from: {skills_csv}")

    new_skills = []
    with open(skills_csv, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            skill_id = int(row['ID'])
            if 8100 <= skill_id <= 8200:  # 8100번대 스킬만
                new_skills.append(row)

    print(f"Found {len(new_skills)} new drop skills (8101-8130)")

    # 스킬 추가/업데이트
    skill_created = 0
    skill_updated = 0

    for row in new_skills:
        try:
            skill_id = int(row['ID'])
            config = json.loads(row.get('config', '{}'))
            player_obtainable = row.get('플레이어_획득가능', 'Y').strip().upper() == 'Y'

            # get_or_create
            skill, created = await Skill_Model.get_or_create(
                id=skill_id,
                defaults={
                    "name": row['이름'],
                    "description": row['효과'],
                    "config": config,
                    "attribute": row.get('속성', '무속성') or '무속성',
                    "keyword": row.get('키워드', ''),
                    "player_obtainable": player_obtainable,
                }
            )

            if created:
                skill_created += 1
                print(f"  ✓ Created: {skill_id:4d} {row['이름']:30s}")
            else:
                # 업데이트
                skill.name = row['이름']
                skill.description = row['효과']
                skill.config = config
                skill.attribute = row.get('속성', '무속성') or '무속성'
                skill.keyword = row.get('키워드', '')
                skill.player_obtainable = player_obtainable
                await skill.save()
                skill_updated += 1
                print(f"  ✓ Updated: {skill_id:4d} {row['이름']:30s}")

        except Exception as e:
            print(f"  ✗ Error: {row.get('ID', '?')} - {e}")

    print(f"\n스킬 마이그레이션 완료: 생성 {skill_created}, 업데이트 {skill_updated}")

    # 2. 몬스터 CSV에서 skill_ids 읽기
    monsters_csv = PROJECT_ROOT / "data" / "monsters.csv"
    print(f"\n[2/2] Reading monsters from: {monsters_csv}")

    monster_updated = 0

    with open(monsters_csv, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                monster_id = int(row['ID'])
                skill_ids_str = row.get('skill_ids', '[]')
                skill_ids = json.loads(skill_ids_str)

                # 8100번대 스킬이 있는지 확인
                has_drop_skill = any(8100 <= sid <= 8200 for sid in skill_ids)
                if not has_drop_skill:
                    continue

                # 데이터베이스에서 몬스터 찾기
                monster = await Monster.get_or_none(id=monster_id)
                if not monster:
                    print(f"  ⚠ Monster {monster_id} ({row.get('이름', '?')}) not found in DB")
                    continue

                # skill_ids 업데이트
                old_skill_ids = monster.skill_ids
                monster.skill_ids = skill_ids
                await monster.save()

                if old_skill_ids != skill_ids:
                    print(f"  ✓ Updated: {monster_id:3d} {row['이름']:30s} - {skill_ids}")
                    monster_updated += 1

            except Exception as e:
                print(f"  ✗ Error: {row.get('ID', '?')} - {e}")

    print(f"\n몬스터 마이그레이션 완료: 업데이트 {monster_updated}")

    await Tortoise.close_connections()

    print(f"\n{'='*80}")
    print(f"✅ 마이그레이션 완료!")
    print(f"   - 스킬: 생성 {skill_created}, 업데이트 {skill_updated}")
    print(f"   - 몬스터: 업데이트 {monster_updated}")
    print(f"{'='*80}")


if __name__ == "__main__":
    print("="*80)
    print("몬스터 드랍 스킬 데이터베이스 마이그레이션")
    print("="*80)
    asyncio.run(migrate_drop_skills())
