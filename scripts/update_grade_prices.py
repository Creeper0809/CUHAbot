"""
Grade 테이블 가격 업데이트 스크립트

등급별 상점 가격을 설정합니다.
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
    """데이터베이스 연결 초기화"""
    db_url = (
        f"postgres://{os.getenv('DATABASE_USER')}:{os.getenv('DATABASE_PASSWORD')}@"
        f"{os.getenv('DATABASE_URL')}:{os.getenv('DATABASE_PORT')}/{os.getenv('DATABASE_TABLE')}"
    )
    await Tortoise.init(
        db_url=db_url,
        modules={"models": ["models"]}
    )
    await Tortoise.generate_schemas(safe=True)


async def update_grade_prices():
    """등급 테이블 가격 업데이트"""
    from models.grade import Grade

    grade_prices = {
        1: 100,      # D
        2: 300,      # C
        3: 800,      # B
        4: 2000,     # A
        5: 5000,     # S
        6: 12000,    # SS
        7: 30000,    # SSS
        8: 80000,    # Mythic
    }

    for grade_id, price in grade_prices.items():
        grade = await Grade.get_or_none(id=grade_id)
        if grade:
            grade.shop_price = price
            await grade.save()
            print(f"✓ {grade.name} 등급 가격: {price}G")
        else:
            print(f"⚠ {grade_id} 등급을 찾을 수 없습니다")

    print(f"\n✓ 총 {len(grade_prices)}개 등급 가격 업데이트 완료")


async def main():
    print("=" * 60)
    print("Grade 테이블 가격 업데이트")
    print("=" * 60)

    await init_db()
    await update_grade_prices()
    await Tortoise.close_connections()

    print("\n" + "=" * 60)
    print("완료!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
