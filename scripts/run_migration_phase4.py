"""
Phase 4 마이그레이션 실행 스크립트
"""
import asyncio
import asyncpg
import os
from pathlib import Path
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# 데이터베이스 연결 정보
DB_HOST = os.getenv("DATABASE_URL")
DB_USER = os.getenv("DATABASE_USER")
DB_PASSWORD = os.getenv("DATABASE_PASSWORD")
DB_PORT = int(os.getenv("DATABASE_PORT", "5432"))
DB_NAME = os.getenv("DATABASE_TABLE")


async def run_migration():
    """마이그레이션 실행"""
    print("=" * 60)
    print("Phase 4 Database Migration")
    print("=" * 60)
    print(f"Host: {DB_HOST}:{DB_PORT}")
    print(f"Database: {DB_NAME}")
    print(f"User: {DB_USER}")
    print("=" * 60)

    # SQL 파일 읽기
    sql_file = Path(__file__).parent / "migrate_phase4.sql"
    if not sql_file.exists():
        print(f"❌ SQL 파일을 찾을 수 없습니다: {sql_file}")
        return

    with open(sql_file, "r", encoding="utf-8") as f:
        sql_content = f.read()

    # 데이터베이스 연결
    try:
        print("\n📡 데이터베이스 연결 중...")
        conn = await asyncpg.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        print("✅ 연결 성공!")

        # SQL 실행
        print("\n🔧 마이그레이션 실행 중...")

        # SQL을 세미콜론으로 분리하여 개별 실행
        statements = [s.strip() for s in sql_content.split(';') if s.strip() and not s.strip().startswith('--')]

        for i, statement in enumerate(statements, 1):
            if statement.upper().startswith('COMMENT'):
                # COMMENT 문은 별도 처리
                await conn.execute(statement)
            elif statement.upper().startswith('SELECT'):
                # SELECT 문은 결과 출력
                result = await conn.fetchval(statement)
                if result:
                    print(f"\n{result}")
            else:
                # 기타 DDL/DML 문 실행
                await conn.execute(statement)
                print(f"  [{i}/{len(statements)}] 실행 완료")

        print("\n✅ 마이그레이션 성공!")

        # 테이블 확인
        print("\n📊 새로 생성된 테이블 확인:")
        tables = await conn.fetch("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name IN ('set_items', 'set_item_members', 'set_effects')
            ORDER BY table_name
        """)

        for table in tables:
            print(f"  ✓ {table['table_name']}")

        # 컬럼 확인
        print("\n📊 추가된 컬럼 확인:")

        # equipment_item 테이블
        columns = await conn.fetch("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'equipment_item'
            AND column_name = 'require_level'
        """)
        if columns:
            print("  ✓ equipment_item.require_level")

        # consume_item 테이블
        columns = await conn.fetch("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'consume_item'
            AND column_name IN ('buff_type', 'buff_amount', 'buff_duration', 'cleanse_debuff', 'throwable_damage')
            ORDER BY column_name
        """)
        for col in columns:
            print(f"  ✓ consume_item.{col['column_name']}")

        print("\n" + "=" * 60)
        print("마이그레이션 완료! 봇을 재시작하세요.")
        print("=" * 60)

        await conn.close()

    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        return False

    return True


if __name__ == "__main__":
    success = asyncio.run(run_migration())
    exit(0 if success else 1)
