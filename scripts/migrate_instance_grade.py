"""
인스턴스 등급 시스템 마이그레이션 스크립트

user_inventory 테이블에 인스턴스 등급 관련 컬럼을 추가하고,
기존 장비 아이템에 기본 등급을 부여합니다.

변경사항:
- instance_grade 컬럼 추가 (INTEGER DEFAULT 0)
- special_effects 컬럼 추가 (JSONB NULL)
- unique constraint 변경: (user_id, item_id, enhancement_level)
  → (user_id, item_id, enhancement_level, instance_grade)
- 기존 장비 아이템: EquipmentItem의 grade를 instance_grade로 복사
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from tortoise import Tortoise


async def migrate():
    """마이그레이션 실행"""
    db_config = {
        "host": os.getenv("DATABASE_URL"),
        "port": int(os.getenv("DATABASE_PORT", 5432)),
        "user": os.getenv("DATABASE_USER"),
        "password": os.getenv("DATABASE_PASSWORD"),
        "database": os.getenv("DATABASE_TABLE"),
    }

    db_url = (
        f"postgres://{db_config['user']}:{db_config['password']}"
        f"@{db_config['host']}:{db_config['port']}/{db_config['database']}"
    )

    await Tortoise.init(
        db_url=db_url,
        modules={"models": ["models"]}
    )

    conn = Tortoise.get_connection("default")

    # 1. instance_grade 컬럼 추가
    await _add_column_if_not_exists(
        conn, "user_inventory", "instance_grade", "INTEGER DEFAULT 0"
    )

    # 2. special_effects 컬럼 추가
    await _add_column_if_not_exists(
        conn, "user_inventory", "special_effects", "JSONB NULL"
    )

    # 3. 기존 장비 아이템에 등급 부여 (EquipmentItem.grade 참조)
    await _assign_existing_grades(conn)

    # 4. unique constraint 변경
    await _update_unique_constraint(conn)

    # 5. equipment_item.grade 컬럼 삭제 (인스턴스 등급으로 대체)
    await _drop_column_if_exists(conn, "equipment_item", "grade")

    await Tortoise.close_connections()
    print("\n✅ 인스턴스 등급 마이그레이션 완료!")


async def _add_column_if_not_exists(conn, table: str, column: str, definition: str):
    """컬럼이 없으면 추가"""
    check_sql = f"""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = '{table}' AND column_name = '{column}'
    """
    result = await conn.execute_query(check_sql)

    if not result[1]:
        alter_sql = f"ALTER TABLE {table} ADD COLUMN {column} {definition}"
        await conn.execute_query(alter_sql)
        print(f"✅ 컬럼 추가: {table}.{column}")
    else:
        print(f"⏭️ 이미 존재: {table}.{column}")


async def _assign_existing_grades(conn):
    """기존 장비 아이템에 EquipmentItem의 grade를 instance_grade로 복사"""
    try:
        # item 타입이 'equip'인 인벤토리 아이템에 대해
        # EquipmentItem의 grade 값을 instance_grade로 설정
        update_sql = """
            UPDATE user_inventory ui
            SET instance_grade = COALESCE(ei.grade, 1)
            FROM item i
            JOIN equipment_item ei ON ei.item_id = i.id
            WHERE ui.item_id = i.id
              AND i.type = 'equip'
              AND ui.instance_grade = 0
        """
        result = await conn.execute_query(update_sql)
        updated = result[0] if result[0] else 0
        print(f"✅ 기존 장비 등급 부여: {updated}개 업데이트")
    except Exception as e:
        print(f"⚠️ 등급 부여 중 오류: {e}")


async def _drop_column_if_exists(conn, table: str, column: str):
    """컬럼이 있으면 삭제"""
    check_sql = f"""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = '{table}' AND column_name = '{column}'
    """
    result = await conn.execute_query(check_sql)

    if result[1]:
        alter_sql = f"ALTER TABLE {table} DROP COLUMN {column}"
        await conn.execute_query(alter_sql)
        print(f"✅ 컬럼 삭제: {table}.{column}")
    else:
        print(f"⏭️ 이미 없음: {table}.{column}")


async def _update_unique_constraint(conn):
    """unique constraint 변경"""
    try:
        # 기존 constraint 찾기 및 삭제
        find_sql = """
            SELECT constraint_name
            FROM information_schema.table_constraints
            WHERE table_name = 'user_inventory'
              AND constraint_type = 'UNIQUE'
        """
        result = await conn.execute_query(find_sql)

        for row in result[1]:
            constraint_name = row["constraint_name"]
            drop_sql = f"ALTER TABLE user_inventory DROP CONSTRAINT {constraint_name}"
            await conn.execute_query(drop_sql)
            print(f"✅ 기존 constraint 삭제: {constraint_name}")

        # 새 constraint 추가
        add_sql = """
            ALTER TABLE user_inventory
            ADD CONSTRAINT uid_user_inven_user_id_instance_grade
            UNIQUE (user_id, item_id, enhancement_level, instance_grade)
        """
        await conn.execute_query(add_sql)
        print("✅ 새 unique constraint 추가: (user, item, enhancement_level, instance_grade)")

    except Exception as e:
        print(f"⚠️ Constraint 변경 중 오류: {e}")


if __name__ == "__main__":
    asyncio.run(migrate())
