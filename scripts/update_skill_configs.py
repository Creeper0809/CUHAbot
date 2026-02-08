#!/usr/bin/env python3
"""
스킬 config를 CSV에서 데이터베이스로 업데이트하는 스크립트
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
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

# 데이터베이스 URL 구성 (seed_skills.py와 동일한 방식)
DATABASE_URL = f"postgres://{os.getenv('DATABASE_USER')}:{os.getenv('DATABASE_PASSWORD')}@{os.getenv('DATABASE_URL')}:{os.getenv('DATABASE_PORT')}/{os.getenv('DATABASE_TABLE')}"


async def update_skills_from_csv():
    """CSV에서 스킬 config를 읽어서 데이터베이스 업데이트"""

    # DB 초기화
    await Tortoise.init(
        db_url=DATABASE_URL,
        modules={"models": ["models"]}
    )

    print(f"Connected to database: {os.getenv('DATABASE_TABLE')}")

    # CSV 파일 읽기
    skills_csv = PROJECT_ROOT / "data" / "skills.csv"
    print(f"\nReading skills from: {skills_csv}")

    with open(skills_csv, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    updated_count = 0
    error_count = 0

    for row in rows:
        try:
            skill_id = int(row['ID'])
            skill_name = row['이름']
            config_str = row.get('config', '{}')

            # JSON 파싱
            try:
                config = json.loads(config_str)
            except json.JSONDecodeError as e:
                print(f"✗ Skill {skill_id} ({skill_name}): Invalid JSON - {e}")
                error_count += 1
                continue

            # 데이터베이스에서 스킬 찾기
            skill = await Skill_Model.get_or_none(id=skill_id)

            if skill:
                # config 업데이트
                old_config = skill.config
                skill.config = config
                await skill.save()

                # 변경사항이 있으면 출력
                if old_config != config:
                    print(f"✓ Skill {skill_id:4d} ({skill_name:30s}): Updated")
                    updated_count += 1
            else:
                print(f"⚠ Skill {skill_id:4d} ({skill_name:30s}): Not found in DB")

        except Exception as e:
            print(f"✗ Error processing skill {row.get('ID', '?')}: {e}")
            error_count += 1

    await Tortoise.close_connections()

    print(f"\n{'='*80}")
    print(f"✅ Updated: {updated_count} skills")
    if error_count > 0:
        print(f"❌ Errors: {error_count}")
    print(f"{'='*80}")


if __name__ == "__main__":
    print("="*80)
    print("스킬 Config 데이터베이스 업데이트")
    print("="*80)
    asyncio.run(update_skills_from_csv())
