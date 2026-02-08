"""
유저 삭제 스크립트

Discord ID로 유저를 찾아서 모든 관련 데이터와 함께 삭제합니다.
"""
import asyncio
import sys
from tortoise import Tortoise

from models import User, UserStats, UserEquipment, UserInventory, UserOwnedSkill, UserSkillDeck, UserDeckPreset, UserCollection


async def delete_user(discord_id: int):
    """유저와 관련 데이터 모두 삭제"""
    # DB 연결
    await Tortoise.init(
        db_url='sqlite://db.sqlite3',
        modules={'models': ['models']}
    )

    print(f"🔍 Discord ID {discord_id} 유저 검색 중...")

    # 유저 찾기
    user = await User.get_or_none(discord_id=discord_id)

    if not user:
        print(f"❌ Discord ID {discord_id}인 유저를 찾을 수 없습니다.")
        await Tortoise.close_connections()
        return

    print(f"✅ 유저 찾음: {user.name} (ID: {user.id})")
    print(f"   레벨: {user.level}, HP: {user.now_hp}/{user.hp}")

    # 삭제 확인
    print("\n⚠️  이 유저의 모든 데이터가 삭제됩니다:")
    print("   - 기본 정보 (User)")
    print("   - 스탯 (UserStats)")
    print("   - 장비 (UserEquipment)")
    print("   - 인벤토리 (UserInventory)")
    print("   - 보유 스킬 (UserOwnedSkill)")
    print("   - 스킬 덱 (UserSkillDeck)")
    print("   - 덱 프리셋 (UserDeckPreset)")
    print("   - 도감 (UserCollection)")

    confirm = input("\n정말로 삭제하시겠습니까? (yes/no): ")

    if confirm.lower() != 'yes':
        print("❌ 삭제 취소됨")
        await Tortoise.close_connections()
        return

    print("\n🗑️  삭제 중...")

    # 관련 데이터 삭제
    deleted_stats = await UserStats.filter(user=user).delete()
    deleted_equipment = await UserEquipment.filter(user=user).delete()
    deleted_inventory = await UserInventory.filter(user=user).delete()
    deleted_skills = await UserOwnedSkill.filter(user=user).delete()
    deleted_deck = await UserSkillDeck.filter(user=user).delete()
    deleted_preset = await UserDeckPreset.filter(user=user).delete()
    deleted_collection = await UserCollection.filter(user=user).delete()

    # 유저 삭제
    await user.delete()

    print("\n✅ 삭제 완료!")
    print(f"   UserStats: {deleted_stats}개")
    print(f"   UserEquipment: {deleted_equipment}개")
    print(f"   UserInventory: {deleted_inventory}개")
    print(f"   UserOwnedSkill: {deleted_skills}개")
    print(f"   UserSkillDeck: {deleted_deck}개")
    print(f"   UserDeckPreset: {deleted_preset}개")
    print(f"   UserCollection: {deleted_collection}개")
    print(f"   User: 1개")

    await Tortoise.close_connections()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("사용법: python scripts/delete_user.py <Discord ID>")
        print("예시: python scripts/delete_user.py 123456789012345678")
        sys.exit(1)

    try:
        discord_id = int(sys.argv[1])
        asyncio.run(delete_user(discord_id))
    except ValueError:
        print("❌ Discord ID는 숫자여야 합니다.")
        sys.exit(1)
