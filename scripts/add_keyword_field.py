"""
Skill 테이블에 keyword 필드 추가 마이그레이션

실행: python scripts/add_keyword_field.py
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
    """데이터베이스 연결 초기화"""
    db_url = f"postgres://{os.getenv('DATABASE_USER')}:{os.getenv('DATABASE_PASSWORD')}@{os.getenv('DATABASE_URL')}:{os.getenv('DATABASE_PORT')}/{os.getenv('DATABASE_TABLE')}"
    await Tortoise.init(
        db_url=db_url,
        modules={"models": ["models"]}
    )


async def add_keyword_field():
    """skill 테이블에 keyword 컬럼 추가"""
    conn = Tortoise.get_connection("default")

    try:
        # keyword 컬럼이 이미 있는지 확인
        check_query = """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name='skill' AND column_name='keyword';
        """
        result = await conn.execute_query_dict(check_query)

        if result:
            print("✅ keyword 컬럼이 이미 존재합니다.")
            return

        # keyword 컬럼 추가
        add_column_query = """
        ALTER TABLE skill
        ADD COLUMN keyword VARCHAR(100) DEFAULT '' NULL;
        """
        await conn.execute_script(add_column_query)
        print("✅ keyword 컬럼이 성공적으로 추가되었습니다!")

    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        raise


async def main():
    """메인 실행"""
    try:
        print("데이터베이스 연결 중...")
        await init_db()
        print("마이그레이션 시작...")
        await add_keyword_field()
        print("\n마이그레이션 완료! 이제 python scripts/seed_skills.py를 실행하세요.")
    except Exception as e:
        print(f"오류 발생: {e}")
        raise
    finally:
        await Tortoise.close_connections()


if __name__ == "__main__":
    asyncio.run(main())
