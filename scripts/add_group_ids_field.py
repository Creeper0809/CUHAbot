#!/usr/bin/env python3
"""
Monster 테이블에 group_ids 필드 추가

실행: python scripts/add_group_ids_field.py
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


async def add_group_ids_column():
    """group_ids 컬럼 추가"""
    conn = Tortoise.get_connection("default")

    try:
        # 1. 컬럼이 이미 존재하는지 확인
        check_query = """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name='monster' AND column_name='group_ids';
        """
        result = await conn.execute_query_dict(check_query)

        if result:
            print("✅ group_ids 컬럼이 이미 존재합니다.")
            return

        # 2. 컬럼 추가 (기본값 빈 JSON 배열)
        alter_query = """
        ALTER TABLE monster
        ADD COLUMN group_ids JSONB DEFAULT '[]'::jsonb NOT NULL;
        """
        await conn.execute_script(alter_query)
        print("✅ group_ids 컬럼 추가 완료!")

        # 3. 통계 확인
        count_query = "SELECT COUNT(*) as count FROM monster;"
        count_result = await conn.execute_query_dict(count_query)
        total_count = count_result[0]['count'] if count_result else 0

        print(f"\n📊 통계:")
        print(f"  - 전체 몬스터: {total_count}개")
        print(f"  - group_ids는 seed_monsters.py 실행 시 CSV 데이터로 채워집니다.")

    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        raise


async def main():
    """메인 실행 함수"""
    try:
        await init_db()
        await add_group_ids_column()
    except Exception as e:
        print(f"오류 발생: {e}")
        raise
    finally:
        await Tortoise.close_connections()


if __name__ == "__main__":
    asyncio.run(main())
