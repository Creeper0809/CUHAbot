"""
모든 유저 삭제 스크립트

DB의 모든 유저와 관련 데이터를 삭제합니다.
"""
import asyncio
from tortoise import Tortoise

from models import User, UserStats, UserEquipment, UserInventory, UserOwnedSkill, UserSkillDeck, UserDeckPreset, UserCollection


async def delete_all_users():
    """모든 유저와 관련 데이터 삭제"""
    # DB 연결
    await Tortoise.init(
        db_url='sqlite://db.sqlite3',
        modules={'models': ['models']}
    )

    # 스키마 생성 (없으면)
    await Tortoise.generate_schemas()

    print("🔍 모든 유저 검색 중...")

    # 모든 유저 조회
    users = await User.all()
    user_count = len(users)

    if user_count == 0:
        print("✅ 삭제할 유저가 없습니다.")
        await Tortoise.close_connections()
        return

    print(f"⚠️  총 {user_count}명의 유저가 발견되었습니다:")
    for user in users[:10]:  # 최대 10명까지만 표시
        print(f"   - {user.name} (Lv.{user.level}, Discord ID: {user.discord_id})")
    if user_count > 10:
        print(f"   ... 외 {user_count - 10}명")

    print("\n⚠️  모든 유저의 모든 데이터가 영구적으로 삭제됩니다!")
    print("   이 작업은 되돌릴 수 없습니다.")

    confirm = input("\n정말로 모든 유저를 삭제하시겠습니까? (yes/no): ")

    if confirm.lower() != 'yes':
        print("❌ 삭제 취소됨")
        await Tortoise.close_connections()
        return

    print("\n🗑️  삭제 중...")

    # 관련 데이터 일괄 삭제
    deleted_stats = await UserStats.all().delete()
    deleted_equipment = await UserEquipment.all().delete()
    deleted_inventory = await UserInventory.all().delete()
    deleted_skills = await UserOwnedSkill.all().delete()
    deleted_deck = await UserSkillDeck.all().delete()
    deleted_preset = await UserDeckPreset.all().delete()
    deleted_collection = await UserCollection.all().delete()

    # 모든 유저 삭제
    deleted_users = await User.all().delete()

    print("\n✅ 삭제 완료!")
    print(f"   UserStats: {deleted_stats}개")
    print(f"   UserEquipment: {deleted_equipment}개")
    print(f"   UserInventory: {deleted_inventory}개")
    print(f"   UserOwnedSkill: {deleted_skills}개")
    print(f"   UserSkillDeck: {deleted_deck}개")
    print(f"   UserDeckPreset: {deleted_preset}개")
    print(f"   UserCollection: {deleted_collection}개")
    print(f"   User: {deleted_users}개")
    print("\n🎉 모든 유저 데이터가 삭제되었습니다.")

    await Tortoise.close_connections()


if __name__ == "__main__":
    asyncio.run(delete_all_users())
