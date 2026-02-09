"""
몬스터 테이블에 race 컬럼 추가 마이그레이션

DB 스키마를 업데이트하여 race 필드를 추가합니다.
"""
import asyncio
import sys
import os
from dotenv import load_dotenv

# .env 로드
load_dotenv()

# 프로젝트 루트를 sys.path에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tortoise import Tortoise

# 환경변수에서 DB 정보 가져오기
DATABASE_URL = f"postgres://{os.getenv('DATABASE_USER')}:{os.getenv('DATABASE_PASSWORD')}@{os.getenv('DATABASE_URL')}:{os.getenv('DATABASE_PORT')}/{os.getenv('DATABASE_TABLE')}"


async def migrate_add_race_column():
    """몬스터 테이블에 race 컬럼 추가"""
    # 데이터베이스 초기화
    await Tortoise.init(
        db_url=DATABASE_URL,
        modules={'models': ['models']},
    )

    # DB 연결 가져오기
    connection = Tortoise.get_connection("default")

    print("=" * 80)
    print("몬스터 테이블 race 컬럼 추가 마이그레이션")
    print("=" * 80)
    print()

    try:
        # 1. race 컬럼이 이미 있는지 확인
        check_query = """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'monster' AND column_name = 'race';
        """
        result = await connection.execute_query_dict(check_query)

        if result:
            print("⚠️  race 컬럼이 이미 존재합니다. 마이그레이션을 건너뜁니다.")
        else:
            # 2. race 컬럼 추가
            print("📝 race 컬럼 추가 중...")
            add_column_query = """
            ALTER TABLE monster
            ADD COLUMN race VARCHAR(30) DEFAULT '미지';
            """
            await connection.execute_query(add_column_query)
            print("✅ race 컬럼 추가 완료")

        print()
        print("=" * 80)
        print("마이그레이션 완료")
        print("=" * 80)

    except Exception as e:
        print(f"❌ 마이그레이션 실패: {e}")
        raise
    finally:
        await Tortoise.close_connections()


if __name__ == "__main__":
    asyncio.run(migrate_add_race_column())
