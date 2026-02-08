#!/usr/bin/env python3
"""
DB 스키마 동기화 마이그레이션

모델에 정의된 컬럼이 DB에 없으면 자동으로 추가합니다.
안전하게 IF NOT EXISTS 패턴을 사용하므로 여러 번 실행해도 문제없습니다.

실행: python scripts/migrate_sync_schema.py
"""
import asyncio
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv
from tortoise import Tortoise

load_dotenv()


# =============================================================================
# 누락 가능한 컬럼 정의
# (table_name, column_name, column_type, default_value)
# =============================================================================

EXPECTED_COLUMNS = [
    # ── Monster 테이블 ──
    ("monster", "skill_ids", "JSONB", "'[]'::jsonb"),
    ("monster", "drop_skill_ids", "JSONB", "'[]'::jsonb"),
    ("monster", "group_ids", "JSONB", "'[]'::jsonb"),
    ("monster", "attribute", "VARCHAR(20)", "'무속성'"),
    ("monster", "ap_attack", "INTEGER", "0"),
    ("monster", "ap_defense", "INTEGER", "0"),
    ("monster", "speed", "INTEGER", "10"),
    ("monster", "evasion", "INTEGER", "0"),

    # ── Skill 테이블 ──
    ("skill", "grade", "INTEGER", "NULL"),
    ("skill", "attribute", "VARCHAR(20)", "'무속성'"),
    ("skill", "keyword", "VARCHAR(100)", "NULL"),
    ("skill", "player_obtainable", "BOOLEAN", "TRUE"),

    # ── ConsumeItem 테이블 ──
    ("consume_item", "buff_type", "VARCHAR(50)", "NULL"),
    ("consume_item", "buff_amount", "INTEGER", "NULL"),
    ("consume_item", "buff_duration", "INTEGER", "NULL"),
    ("consume_item", "cleanse_debuff", "BOOLEAN", "FALSE"),
    ("consume_item", "throwable_damage", "INTEGER", "NULL"),

    # ── EquipmentItem 테이블 ──
    ("equipment_item", "require_level", "INTEGER", "1"),
    ("equipment_item", "require_str", "INTEGER", "0"),
    ("equipment_item", "require_int", "INTEGER", "0"),
    ("equipment_item", "require_dex", "INTEGER", "0"),
    ("equipment_item", "require_vit", "INTEGER", "0"),
    ("equipment_item", "require_luk", "INTEGER", "0"),
    ("equipment_item", "ap_attack", "INTEGER", "NULL"),
    ("equipment_item", "ad_defense", "INTEGER", "NULL"),
    ("equipment_item", "ap_defense", "INTEGER", "NULL"),

    # ── User 테이블 ──
    ("users", "bonus_str", "INTEGER", "0"),
    ("users", "bonus_int", "INTEGER", "0"),
    ("users", "bonus_dex", "INTEGER", "0"),
    ("users", "bonus_vit", "INTEGER", "0"),
    ("users", "bonus_luk", "INTEGER", "0"),
    ("users", "stat_points", "INTEGER", "0"),
    ("users", "accuracy", "INTEGER", "90"),
    ("users", "evasion", "INTEGER", "5"),
    ("users", "critical_rate", "INTEGER", "5"),
    ("users", "critical_damage", "INTEGER", "150"),
    ("users", "last_attendance", "DATE", "NULL"),
    ("users", "attendance_streak", "INTEGER", "0"),

    # ── UserInventory 테이블 ──
    ("user_inventory", "enhancement_level", "INTEGER", "0"),
    ("user_inventory", "is_blessed", "BOOLEAN", "FALSE"),
    ("user_inventory", "is_cursed", "BOOLEAN", "FALSE"),
    ("user_inventory", "instance_grade", "INTEGER", "0"),
    ("user_inventory", "special_effects", "JSONB", "NULL"),
]

# =============================================================================
# 누락 가능한 테이블 (세트 아이템 등)
# =============================================================================

EXPECTED_TABLES = [
    (
        "set_items",
        """
        CREATE TABLE IF NOT EXISTS set_items (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100) UNIQUE NOT NULL,
            description TEXT
        );
        """,
    ),
    (
        "set_item_members",
        """
        CREATE TABLE IF NOT EXISTS set_item_members (
            id SERIAL PRIMARY KEY,
            set_item_id INTEGER NOT NULL REFERENCES set_items(id) ON DELETE CASCADE,
            equipment_item_id BIGINT NOT NULL REFERENCES equipment_item(id) ON DELETE CASCADE,
            UNIQUE(set_item_id, equipment_item_id)
        );
        """,
    ),
    (
        "set_effects",
        """
        CREATE TABLE IF NOT EXISTS set_effects (
            id SERIAL PRIMARY KEY,
            set_item_id INTEGER NOT NULL REFERENCES set_items(id) ON DELETE CASCADE,
            pieces_required INTEGER NOT NULL,
            effect_description TEXT NOT NULL,
            effect_config JSONB NOT NULL,
            UNIQUE(set_item_id, pieces_required)
        );
        """,
    ),
]


async def check_column_exists(conn, table: str, column: str) -> bool:
    """컬럼 존재 여부 확인"""
    result = await conn.execute_query_dict(
        """
        SELECT 1 FROM information_schema.columns
        WHERE table_name = $1 AND column_name = $2
        """,
        [table, column],
    )
    return len(result) > 0


async def check_table_exists(conn, table: str) -> bool:
    """테이블 존재 여부 확인"""
    result = await conn.execute_query_dict(
        """
        SELECT 1 FROM information_schema.tables
        WHERE table_name = $1 AND table_schema = 'public'
        """,
        [table],
    )
    return len(result) > 0


async def main():
    db_url = (
        f"postgres://{os.getenv('DATABASE_USER')}:{os.getenv('DATABASE_PASSWORD')}"
        f"@{os.getenv('DATABASE_URL')}:{os.getenv('DATABASE_PORT')}"
        f"/{os.getenv('DATABASE_TABLE')}"
    )

    print(f"📡 연결 중: {os.getenv('DATABASE_URL')}:{os.getenv('DATABASE_PORT')}/{os.getenv('DATABASE_TABLE')}")
    await Tortoise.init(
        db_url=db_url,
        modules={"models": ["models"]},
    )

    conn = Tortoise.get_connection("default")
    added = 0
    skipped = 0
    errors = 0

    # ── 1) 테이블 생성 ──
    print("\n━━━ 테이블 체크 ━━━")
    for table_name, create_sql in EXPECTED_TABLES:
        exists = await check_table_exists(conn, table_name)
        if exists:
            print(f"  ✅ {table_name} - 이미 존재")
            skipped += 1
        else:
            try:
                await conn.execute_script(create_sql)
                print(f"  🆕 {table_name} - 생성 완료")
                added += 1
            except Exception as e:
                print(f"  ❌ {table_name} - 오류: {e}")
                errors += 1

    # ── 2) 컬럼 추가 ──
    print("\n━━━ 컬럼 체크 ━━━")
    current_table = ""
    for table, column, col_type, default in EXPECTED_COLUMNS:
        if table != current_table:
            current_table = table
            table_exists = await check_table_exists(conn, table)
            if not table_exists:
                print(f"\n  ⚠️  테이블 '{table}' 없음 - 건너뜀")
                continue
            print(f"\n  [{table}]")

        if not await check_table_exists(conn, table):
            continue

        exists = await check_column_exists(conn, table, column)
        if exists:
            print(f"    ✅ {column}")
            skipped += 1
            continue

        default_clause = f" DEFAULT {default}" if default != "NULL" else ""
        null_clause = " NULL" if default == "NULL" else " NOT NULL" if default != "NULL" else ""

        # JSONB, BOOLEAN 등은 NOT NULL + DEFAULT 조합
        # NULL default는 컬럼 자체를 nullable로
        if default == "NULL":
            sql = f"ALTER TABLE {table} ADD COLUMN {column} {col_type} NULL;"
        else:
            sql = f"ALTER TABLE {table} ADD COLUMN {column} {col_type} NOT NULL DEFAULT {default};"

        try:
            await conn.execute_script(sql)
            print(f"    🆕 {column} ({col_type}, default={default})")
            added += 1
        except Exception as e:
            print(f"    ❌ {column} - 오류: {e}")
            errors += 1

    # ── 3) 결과 ──
    print(f"\n━━━ 결과 ━━━")
    print(f"  추가: {added}개 | 이미 존재: {skipped}개 | 오류: {errors}개")

    if errors > 0:
        print(f"\n⚠️  {errors}개 오류 발생 - 위 로그를 확인하세요")
    else:
        print("\n✅ 스키마 동기화 완료!")

    await Tortoise.close_connections()


if __name__ == "__main__":
    asyncio.run(main())
