"""
인벤토리 unique_together 제약조건 제거 마이그레이션

문제:
- unique_together = [("user", "item", "enhancement_level", "instance_grade")]
- 이 제약조건으로 인해 같은 등급이지만 다른 특수효과/축복/저주를 가진 장비가
  개별 인스턴스로 저장되지 못하고 하나로 합쳐지는 문제 발생

해결:
- 제약조건 제거하여 각 장비 인스턴스를 개별적으로 관리
- 스택 여부는 InventoryService.add_item() 로직으로 제어
"""
import asyncio
import os
import sys

# 프로젝트 루트를 경로에 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv
from tortoise import Tortoise

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
DATABASE_USER = os.getenv("DATABASE_USER")
DATABASE_PASSWORD = os.getenv("DATABASE_PASSWORD")
DATABASE_PORT = int(os.getenv("DATABASE_PORT") or 0)
DATABASE_TABLE = os.getenv("DATABASE_TABLE")


async def main():
    """unique_together 제약조건 제거"""
    print("🔌 데이터베이스 연결 중...")

    await Tortoise.init(
        db_url=f"postgres://{DATABASE_USER}:{DATABASE_PASSWORD}@{DATABASE_URL}:{DATABASE_PORT}/{DATABASE_TABLE}",
        modules={"models": ["models"]},
    )
    conn = Tortoise.get_connection("default")

    print("🔍 현재 user_inventory 테이블 제약조건 확인...")

    # PostgreSQL에서 제약조건 확인
    constraints = await conn.execute_query_dict("""
        SELECT conname, contype
        FROM pg_constraint
        WHERE conrelid = 'user_inventory'::regclass
    """)

    print(f"현재 제약조건: {constraints}")

    # unique_together 제약조건 찾기
    unique_constraint_name = None
    for constraint in constraints:
        if constraint['contype'] == b'u':  # unique constraint
            # 제약조건 상세 확인
            detail = await conn.execute_query_dict(f"""
                SELECT a.attname
                FROM pg_constraint c
                JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY(c.conkey)
                WHERE c.conname = '{constraint['conname']}'
                AND c.conrelid = 'user_inventory'::regclass
                ORDER BY array_position(c.conkey, a.attnum)
            """)

            columns = [d['attname'] for d in detail]
            print(f"  - {constraint['conname']}: {columns}")

            # user_id, item_id, enhancement_level, instance_grade 조합 찾기
            # (순서 무관, 4개 컬럼이면 해당)
            if len(columns) == 4 and set(columns) == {'user_id', 'item_id', 'enhancement_level', 'instance_grade'}:
                unique_constraint_name = constraint['conname']
                print(f"✅ 제거 대상 제약조건 발견: {unique_constraint_name}")

    if not unique_constraint_name:
        print("⚠️  제약조건을 찾을 수 없습니다. 이미 제거되었거나 이름이 다릅니다.")
        await Tortoise.close_connections()
        return

    print(f"\n🗑️  제약조건 '{unique_constraint_name}' 제거 중...")

    try:
        await conn.execute_query(f"""
            ALTER TABLE user_inventory
            DROP CONSTRAINT IF EXISTS {unique_constraint_name}
        """)
        print(f"✅ 제약조건 '{unique_constraint_name}' 제거 완료!")
    except Exception as e:
        print(f"❌ 제약조건 제거 실패: {e}")
        await Tortoise.close_connections()
        return

    # 제거 후 확인
    print("\n🔍 제거 후 제약조건 확인...")
    constraints_after = await conn.execute_query_dict("""
        SELECT conname, contype
        FROM pg_constraint
        WHERE conrelid = 'user_inventory'::regclass
        AND contype = 'u'
    """)
    print(f"남은 unique 제약조건: {constraints_after}")

    print("\n✅ 마이그레이션 완료!")
    print("이제 동일한 instance_grade를 가진 장비도 special_effects/is_blessed/is_cursed가")
    print("다르면 개별 인스턴스로 저장됩니다.")

    await Tortoise.close_connections()


if __name__ == "__main__":
    asyncio.run(main())
