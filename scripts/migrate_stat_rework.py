"""
능력치 시스템 리워크 마이그레이션

기존 6개 보너스 필드(bonus_hp, bonus_attack, ...)를
5대 능력치(bonus_str, bonus_int, bonus_dex, bonus_vit, bonus_luk)로 전환합니다.

전략: 기존 투자된 포인트를 모두 반환하여 재분배하도록 합니다.
(역산이 불완전할 수 있으므로 가장 안전한 방식)

실행: python scripts/migrate_stat_rework.py
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
    db_url = (
        f"postgres://{os.getenv('DATABASE_USER')}:{os.getenv('DATABASE_PASSWORD')}@"
        f"{os.getenv('DATABASE_URL')}:{os.getenv('DATABASE_PORT')}/{os.getenv('DATABASE_TABLE')}"
    )
    await Tortoise.init(
        db_url=db_url,
        modules={"models": ["models"]}
    )
    await Tortoise.generate_schemas(safe=True)


async def migrate():
    """
    마이그레이션 로직:
    1. 기존 bonus_* 필드 합산 → stat_points로 반환
    2. 새 bonus_str/int/dex/vit/luk = 0 으로 초기화
    3. hp_regen 필드 제거 (VIT 기반 동적 계산으로 대체)
    """
    conn = Tortoise.get_connection("default")

    # 1. 새 컬럼 추가 (존재하지 않으면)
    new_columns = [
        ("bonus_str", "INTEGER DEFAULT 0"),
        ("bonus_int", "INTEGER DEFAULT 0"),
        ("bonus_dex", "INTEGER DEFAULT 0"),
        ("bonus_vit", "INTEGER DEFAULT 0"),
        ("bonus_luk", "INTEGER DEFAULT 0"),
    ]

    for col_name, col_type in new_columns:
        try:
            await conn.execute_query(
                f'ALTER TABLE "users" ADD COLUMN "{col_name}" {col_type};'
            )
            print(f"  + 컬럼 추가: {col_name}")
        except Exception:
            print(f"  - 컬럼 이미 존재: {col_name}")

    # 2. 기존 포인트 반환: 이전 bonus 필드 합산 → stat_points에 가산
    # 기존 increment 값: HP=3, Attack=1, Defense=1, AP_Attack=1, AP_Defense=1, Speed=1
    # bonus_* / increment = 사용한 포인트 수
    old_columns = [
        ("bonus_hp", 3),
        ("bonus_attack", 1),
        ("bonus_ad_defense", 1),
        ("bonus_ap_attack", 1),
        ("bonus_ap_defense", 1),
        ("bonus_speed", 1),
    ]

    # 기존 컬럼 존재 여부 확인
    existing_columns = set()
    try:
        result = await conn.execute_query(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'users';"
        )
        for row in result[1]:
            existing_columns.add(row["column_name"])
    except Exception:
        pass

    has_old_columns = any(col in existing_columns for col, _ in old_columns)

    if has_old_columns:
        # 각 유저별로 사용된 포인트 역산 후 반환
        users = await conn.execute_query('SELECT * FROM "users";')

        migrated = 0
        for row in users[1]:
            used_points = 0
            for col_name, increment in old_columns:
                if col_name in existing_columns:
                    val = row.get(col_name, 0) or 0
                    used_points += val // increment

            if used_points > 0:
                user_id = row["id"]
                current_stat_points = row.get("stat_points", 0) or 0

                await conn.execute_query(
                    f'UPDATE "users" SET '
                    f'"stat_points" = {current_stat_points + used_points}, '
                    f'"bonus_str" = 0, "bonus_int" = 0, "bonus_dex" = 0, '
                    f'"bonus_vit" = 0, "bonus_luk" = 0 '
                    f'WHERE "id" = {user_id};'
                )
                migrated += 1
                print(
                    f"  User {user_id}: {used_points}포인트 반환 "
                    f"(stat_points: {current_stat_points} → {current_stat_points + used_points})"
                )

        print(f"\n✓ {migrated}명의 유저 마이그레이션 완료")

        # 3. 기존 컬럼 제거
        for col_name, _ in old_columns:
            if col_name in existing_columns:
                try:
                    await conn.execute_query(
                        f'ALTER TABLE "users" DROP COLUMN "{col_name}";'
                    )
                    print(f"  - 컬럼 제거: {col_name}")
                except Exception as e:
                    print(f"  ⚠ 컬럼 제거 실패: {col_name} ({e})")

        # 4. hp_regen 제거
        if "hp_regen" in existing_columns:
            try:
                await conn.execute_query(
                    'ALTER TABLE "users" DROP COLUMN "hp_regen";'
                )
                print("  - 컬럼 제거: hp_regen")
            except Exception as e:
                print(f"  ⚠ hp_regen 제거 실패: {e}")
    else:
        print("  기존 bonus 컬럼이 없습니다 (이미 마이그레이션됨)")

    # 5. 장비 테이블에 능력치 요구 컬럼 추가
    equip_columns = [
        ("require_str", "INTEGER DEFAULT 0"),
        ("require_int", "INTEGER DEFAULT 0"),
        ("require_dex", "INTEGER DEFAULT 0"),
        ("require_vit", "INTEGER DEFAULT 0"),
        ("require_luk", "INTEGER DEFAULT 0"),
        ("ap_attack", "INTEGER"),
        ("ad_defense", "INTEGER"),
        ("ap_defense", "INTEGER"),
    ]

    for col_name, col_type in equip_columns:
        try:
            await conn.execute_query(
                f'ALTER TABLE "equipment_item" ADD COLUMN "{col_name}" {col_type};'
            )
            print(f"  + equipment_item 컬럼 추가: {col_name}")
        except Exception:
            print(f"  - equipment_item 컬럼 이미 존재: {col_name}")


async def main():
    print("=" * 60)
    print("능력치 시스템 리워크 마이그레이션")
    print("=" * 60)

    await init_db()
    await migrate()
    await Tortoise.close_connections()

    print("\n" + "=" * 60)
    print("마이그레이션 완료!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
