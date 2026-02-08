#!/usr/bin/env python3
"""
데이터베이스 전체 초기화 및 데이터 시드

실행: python scripts/init_database.py
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
    print(f"📡 데이터베이스 연결 중: {os.getenv('DATABASE_URL')}:{os.getenv('DATABASE_PORT')}/{os.getenv('DATABASE_TABLE')}")

    await Tortoise.init(
        db_url=db_url,
        modules={"models": ["models"]}
    )


async def create_schema():
    """스키마 생성"""
    print("\n📋 테이블 스키마 생성 중...")
    await Tortoise.generate_schemas()
    print("✅ 스키마 생성 완료!")


async def add_custom_columns():
    """커스텀 컬럼 추가"""
    conn = Tortoise.get_connection("default")

    print("\n🔧 커스텀 컬럼 추가 중...")

    # 1. skill.player_obtainable 컬럼 추가
    try:
        check_query = """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name='skill' AND column_name='player_obtainable';
        """
        result = await conn.execute_query_dict(check_query)

        if not result:
            alter_query = """
            ALTER TABLE skill
            ADD COLUMN player_obtainable BOOLEAN DEFAULT TRUE NOT NULL;
            """
            await conn.execute_script(alter_query)
            print("  ✅ skill.player_obtainable 컬럼 추가")
        else:
            print("  ⏭️  skill.player_obtainable 이미 존재")
    except Exception as e:
        print(f"  ⚠️  skill.player_obtainable 추가 실패: {e}")

    # 2. monster.group_ids 컬럼 추가
    try:
        check_query = """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name='monster' AND column_name='group_ids';
        """
        result = await conn.execute_query_dict(check_query)

        if not result:
            alter_query = """
            ALTER TABLE monster
            ADD COLUMN group_ids JSONB DEFAULT '[]'::jsonb NOT NULL;
            """
            await conn.execute_script(alter_query)
            print("  ✅ monster.group_ids 컬럼 추가")
        else:
            print("  ⏭️  monster.group_ids 이미 존재")
    except Exception as e:
        print(f"  ⚠️  monster.group_ids 추가 실패: {e}")


async def seed_data():
    """모든 데이터 시드"""
    print("\n📦 데이터 시드 시작...")

    # Skills 시드
    print("\n--- 스킬 데이터 ---")
    from scripts.seed_skills import seed_skills
    await seed_skills()

    # Monsters 시드
    print("\n--- 몬스터 데이터 ---")
    from scripts.seed_monsters import seed_monsters
    await seed_monsters()

    # 기타 데이터 시드 (던전, 아이템 등)
    print("\n--- 기타 데이터 ---")
    try:
        from scripts.seed_data import seed_all_data
        await seed_all_data()
    except ImportError:
        print("  ⚠️  seed_data.py가 없습니다. 스킵...")
    except Exception as e:
        print(f"  ⚠️  기타 데이터 시드 실패: {e}")


async def verify_data():
    """데이터 확인"""
    print("\n📊 데이터 검증 중...")

    conn = Tortoise.get_connection("default")

    # 스킬 카운트
    skill_count = await conn.execute_query_dict("SELECT COUNT(*) as count FROM skill;")
    skill_total = skill_count[0]['count'] if skill_count else 0

    skill_obtainable = await conn.execute_query_dict(
        "SELECT COUNT(*) as count FROM skill WHERE player_obtainable = TRUE;"
    )
    skill_obtainable_count = skill_obtainable[0]['count'] if skill_obtainable else 0

    # 몬스터 카운트
    monster_count = await conn.execute_query_dict("SELECT COUNT(*) as count FROM monster;")
    monster_total = monster_count[0]['count'] if monster_count else 0

    monster_group = await conn.execute_query_dict(
        "SELECT COUNT(*) as count FROM monster WHERE jsonb_array_length(group_ids) > 0;"
    )
    monster_group_count = monster_group[0]['count'] if monster_group else 0

    print(f"\n✅ 데이터베이스 초기화 완료!")
    print(f"\n📈 통계:")
    print(f"  스킬:")
    print(f"    - 전체: {skill_total}개")
    print(f"    - 플레이어 획득 가능: {skill_obtainable_count}개")
    print(f"    - 몬스터 전용: {skill_total - skill_obtainable_count}개")
    print(f"\n  몬스터:")
    print(f"    - 전체: {monster_total}개")
    print(f"    - 그룹 스폰 가능: {monster_group_count}개")
    print(f"    - 솔로 전용: {monster_total - monster_group_count}개")


async def main():
    """메인 실행 함수"""
    try:
        print("=" * 60)
        print("🚀 CUHABot 데이터베이스 초기화 시작")
        print("=" * 60)

        # 1. DB 연결
        await init_db()

        # 2. 스키마 생성
        await create_schema()

        # 3. 커스텀 컬럼 추가
        await add_custom_columns()

        # 4. 데이터 시드
        await seed_data()

        # 5. 검증
        await verify_data()

        print("\n" + "=" * 60)
        print("✨ 모든 작업이 완료되었습니다!")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        await Tortoise.close_connections()


if __name__ == "__main__":
    asyncio.run(main())
