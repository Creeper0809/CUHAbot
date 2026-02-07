"""
스킬 등급 및 등급별 상점 가격 마이그레이션 스크립트

기존 ShopService에 하드코딩되어 있던 SKILL_GRADE_MAP, SKILL_GRADE_PRICE를
DB의 skill.grade 컬럼과 grade.shop_price 컬럼으로 이전합니다.

실행: python scripts/migrate_skill_grade.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from tortoise import Tortoise

load_dotenv()

# 기존 하드코딩 데이터 (ShopService에서 가져옴)
SKILL_GRADE_MAP = {
    1: "D",
    2: "D",
    3: "C",
    4: "C",
    5: "B",
    101: "C",
    102: "C",
    103: "B",
    104: "B",
    201: "C",
    202: "C",
    203: "B",
    301: "B",
    302: "B",
    303: "A",
    401: "C",
    402: "C",
    403: "B",
    501: "B",
    502: "B",
    503: "A",
    504: "A",
    601: "B",
    602: "B",
    603: "A",
    1001: "D",
    1002: "C",
    1003: "B",
    1004: "A",
    2001: "D",
    2002: "C",
    2003: "B",
    2004: "A",
    3001: "C",
    3002: "C",
    3003: "B",
}

GRADE_SHOP_PRICES = {
    "D": 500,
    "C": 800,
    "B": 1200,
    "A": 1800,
    "S": 3000,
    "SS": 5000,
    "SSS": 8000,
    "Mythic": 12000,
}


async def migrate():
    db_url = os.getenv('DATABASE_URL')
    db_user = os.getenv('DATABASE_USER')
    db_password = os.getenv('DATABASE_PASSWORD')
    db_port = os.getenv('DATABASE_PORT')
    db_table = os.getenv('DATABASE_TABLE')

    await Tortoise.init(
        db_url=f"postgres://{db_user}:{db_password}@{db_url}:{db_port}/{db_table}",
        modules={"models": ["models"]}
    )

    # 새 컬럼 추가 (이미 존재하면 무시)
    conn = Tortoise.get_connection("default")
    print("=== 컬럼 추가 (ALTER TABLE) ===")
    for sql in [
        "ALTER TABLE grade ADD COLUMN IF NOT EXISTS shop_price INT DEFAULT 0",
        "ALTER TABLE skill ADD COLUMN IF NOT EXISTS grade INT DEFAULT NULL",
    ]:
        await conn.execute_script(sql)
        print(f"  {sql}")

    from models import Skill_Model
    from models.grade import Grade

    # 1. Grade 테이블에 shop_price 업데이트
    print("\n=== Grade shop_price 업데이트 ===")
    grade_name_to_id = {}
    grades = await Grade.all()
    for grade in grades:
        if grade.name in GRADE_SHOP_PRICES:
            grade.shop_price = GRADE_SHOP_PRICES[grade.name]
            await grade.save()
            print(f"  Grade '{grade.name}' (id={grade.id}): shop_price = {grade.shop_price}")
        grade_name_to_id[grade.name] = grade.id

    # 2. Skill 테이블에 grade 업데이트
    print("\n=== Skill grade 업데이트 ===")
    skills = await Skill_Model.all()
    updated = 0
    skipped = 0

    for skill in skills:
        grade_name = SKILL_GRADE_MAP.get(skill.id)
        if grade_name is None:
            print(f"  SKIP: Skill {skill.id} ({skill.name}) - 매핑 없음")
            skipped += 1
            continue

        grade_id = grade_name_to_id.get(grade_name)
        if grade_id is None:
            print(f"  WARN: Skill {skill.id} ({skill.name}) - Grade '{grade_name}' 없음")
            skipped += 1
            continue

        skill.grade = grade_id
        await skill.save()
        print(f"  OK: Skill {skill.id} ({skill.name}) -> grade={grade_id} ({grade_name})")
        updated += 1

    print(f"\n=== 완료: {updated}개 업데이트, {skipped}개 스킵 ===")

    await Tortoise.close_connections()


if __name__ == "__main__":
    asyncio.run(migrate())
