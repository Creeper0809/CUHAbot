"""
관리자 권한 설정 스크립트
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from tortoise import Tortoise


async def set_admin(discord_id: int):
    """특정 사용자를 관리자로 설정"""
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

    # 사용자 존재 확인
    check_sql = f"SELECT discord_id, username, user_role FROM users WHERE discord_id = {discord_id}"
    result = await conn.execute_query(check_sql)

    if not result[1]:
        print(f"사용자를 찾을 수 없습니다: {discord_id}")
        await Tortoise.close_connections()
        return

    current_user = result[1][0]
    print(f"현재 사용자: {current_user}")

    # 관리자로 설정
    update_sql = f"UPDATE users SET user_role = 'admin' WHERE discord_id = {discord_id}"
    await conn.execute_query(update_sql)

    print(f"✅ {discord_id} 사용자를 관리자로 설정했습니다!")

    await Tortoise.close_connections()


if __name__ == "__main__":
    # 설정할 Discord ID
    target_discord_id = 725002757290852432

    asyncio.run(set_admin(target_discord_id))
