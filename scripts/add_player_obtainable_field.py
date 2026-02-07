#!/usr/bin/env python3
"""
Skill 테이블에 player_obtainable 필드 추가

실행: python scripts/add_player_obtainable_field.py
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


async def add_player_obtainable_column():
    """player_obtainable 컬럼 추가"""
    conn = Tortoise.get_connection("default")

    try:
        # 1. 컬럼이 이미 존재하는지 확인
        check_query = """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name='skill' AND column_name='player_obtainable';
        """
        result = await conn.execute_query_dict(check_query)

        if result:
            print("✅ player_obtainable 컬럼이 이미 존재합니다.")
            return

        # 2. 컬럼 추가 (기본값 TRUE)
        alter_query = """
        ALTER TABLE skill
        ADD COLUMN player_obtainable BOOLEAN DEFAULT TRUE NOT NULL;
        """
        await conn.execute_script(alter_query)
        print("✅ player_obtainable 컬럼 추가 완료!")

        # 3. 몬스터 전용 스킬(9000번대)을 FALSE로 설정
        update_query = """
        UPDATE skill
        SET player_obtainable = FALSE
        WHERE id >= 9000 AND id < 10000;
        """
        await conn.execute_script(update_query)

        # 업데이트된 개수 확인
        count_query = "SELECT COUNT(*) as count FROM skill WHERE player_obtainable = FALSE;"
        count_result = await conn.execute_query_dict(count_query)
        monster_count = count_result[0]['count'] if count_result else 0

        print(f"✅ 몬스터 전용 스킬 {monster_count}개를 player_obtainable=FALSE로 설정했습니다.")

        # 전체 통계
        total_query = "SELECT COUNT(*) as count FROM skill;"
        total_result = await conn.execute_query_dict(total_query)
        total_count = total_result[0]['count'] if total_result else 0

        player_count = total_count - monster_count

        print(f"\n📊 통계:")
        print(f"  - 전체 스킬: {total_count}개")
        print(f"  - 플레이어 획득 가능: {player_count}개")
        print(f"  - 몬스터 전용: {monster_count}개")

    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        raise


async def main():
    """메인 실행 함수"""
    try:
        await init_db()
        await add_player_obtainable_column()
    except Exception as e:
        print(f"오류 발생: {e}")
        raise
    finally:
        await Tortoise.close_connections()


if __name__ == "__main__":
    asyncio.run(main())
