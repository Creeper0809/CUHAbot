"""
User 모델 마이그레이션 스크립트

새로 추가된 컬럼들을 데이터베이스에 추가합니다:
- exp (경험치)
- stat_points (분배 가능 스탯 포인트)
- defense (방어력)
- hp_regen (분당 HP 회복량)
- last_regen_time (마지막 회복 시간)
"""
import asyncio
import os
import sys

# 프로젝트 루트를 path에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from tortoise import Tortoise


async def migrate():
    """마이그레이션 실행"""
    # 환경 변수에서 DB 정보 로드
    is_dev = os.getenv("DEV", "FALSE").upper() == "TRUE"

    db_config = {
        "host": os.getenv("DATABASE_URL"),
        "port": int(os.getenv("DATABASE_PORT", 5432)),
        "user": os.getenv("DATABASE_USER"),
        "password": os.getenv("DATABASE_PASSWORD"),
        "database": os.getenv("DATABASE_TABLE"),
    }

    db_url = f"postgres://{db_config['user']}:{db_config['password']}@{db_config['host']}:{db_config['port']}/{db_config['database']}"

    await Tortoise.init(
        db_url=db_url,
        modules={"models": ["models"]}
    )

    conn = Tortoise.get_connection("default")

    # 추가할 컬럼들
    columns_to_add = [
        ("exp", "BIGINT DEFAULT 0"),
        ("stat_points", "INTEGER DEFAULT 0"),
        ("defense", "INTEGER DEFAULT 5"),
        ("speed", "INTEGER DEFAULT 10"),
        ("hp_regen", "INTEGER DEFAULT 5"),
        ("last_regen_time", "TIMESTAMP WITH TIME ZONE DEFAULT NOW()"),
        ("ap_attack", "INTEGER DEFAULT 5"),
        ("ap_defense", "INTEGER DEFAULT 5"),
    ]

    for column_name, column_def in columns_to_add:
        try:
            # 컬럼 존재 여부 확인
            check_sql = f"""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'users' AND column_name = '{column_name}'
            """
            result = await conn.execute_query(check_sql)

            if not result[1]:
                # 컬럼이 없으면 추가
                alter_sql = f"ALTER TABLE users ADD COLUMN {column_name} {column_def}"
                await conn.execute_query(alter_sql)
                print(f"✅ Added column: {column_name}")
            else:
                print(f"⏭️ Column already exists: {column_name}")

        except Exception as e:
            print(f"❌ Error adding column {column_name}: {e}")

    # 기존 사용자의 now_hp가 hp보다 크면 조정
    try:
        await conn.execute_query("UPDATE users SET now_hp = hp WHERE now_hp > hp")
        print("✅ Adjusted now_hp values")
    except Exception as e:
        print(f"⚠️ Warning adjusting now_hp: {e}")

    await Tortoise.close_connections()
    print("\n✅ Migration completed!")


if __name__ == "__main__":
    asyncio.run(migrate())
