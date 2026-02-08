"""
사용자 스탯 버그 수정 스크립트

HP가 최대치를 초과하거나 경험치가 음수인 사용자를 수정합니다.
"""
import asyncio
from tortoise import Tortoise

from models import User, UserStats


async def fix_user_stats():
    """사용자 스탯 버그 수정"""
    # DB 연결
    await Tortoise.init(
        db_url='sqlite://db.sqlite3',
        modules={'models': ['models']}
    )

    print("🔍 버그가 있는 사용자 검색 중...")

    # 모든 사용자 확인
    users = await User.all()
    fixed_count = 0

    for user in users:
        fixed = False

        # HP 초과 확인
        if user.now_hp > user.hp:
            print(f"⚠️ {user.name} (ID: {user.id}): HP 초과 - {user.now_hp}/{user.hp}")
            user.now_hp = user.hp
            fixed = True

        # 경험치 음수 확인
        stats = await UserStats.get_or_none(user=user)
        if stats and stats.experience < 0:
            print(f"⚠️ {user.name} (ID: {user.id}): 경험치 음수 - {stats.experience}")
            stats.experience = 0
            await stats.save()
            fixed = True

        if fixed:
            await user.save()
            fixed_count += 1
            print(f"✅ {user.name} 수정 완료")

    print(f"\n📊 총 {fixed_count}명의 사용자 수정 완료")

    await Tortoise.close_connections()


if __name__ == "__main__":
    asyncio.run(fix_user_stats())
