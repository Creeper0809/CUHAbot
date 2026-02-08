"""
Users Repository

사용자 데이터 접근 레이어입니다.
"""
from typing import Optional

from models import User, SkillEquip
from models.user_skill_deck import UserSkillDeck
from config import SKILL_DECK_SIZE


async def find_account_by_discordid(discord_id: int) -> Optional[User]:
    """
    Discord ID로 사용자 조회 (스킬 덱 로드 포함)

    Args:
        discord_id: Discord 사용자 ID

    Returns:
        User 객체 (스킬 덱 로드됨) 또는 None
    """
    user = await User.get_or_none(discord_id=discord_id)
    if not user:
        return None

    # DB에서 로드 시 런타임 필드 초기화
    if not hasattr(user, 'status') or user.status is None:
        user._init_runtime_fields()

    # UserSkillDeck에서 스킬 로드 (새 시스템)
    deck_slots = await UserSkillDeck.filter(user=user).order_by("slot_index")

    if deck_slots:
        # 새 시스템 사용
        user.equipped_skill = [0] * SKILL_DECK_SIZE
        for slot in deck_slots:
            if 0 <= slot.slot_index < SKILL_DECK_SIZE:
                user.equipped_skill[slot.slot_index] = slot.skill_id
    else:
        # 기존 SkillEquip 시스템 폴백 (마이그레이션 전 호환성)
        equipped = await SkillEquip.filter(user=user).prefetch_related("skill")
        for eq in equipped:
            if eq.pos is not None and 0 <= eq.pos < SKILL_DECK_SIZE:
                user.equipped_skill[eq.pos] = eq.skill.id

    return user


async def exists_account_by_discordid(discord_id: int) -> bool:
    """
    Discord ID로 사용자 존재 여부 확인

    Args:
        discord_id: Discord 사용자 ID

    Returns:
        존재하면 True
    """
    return await User.exists(discord_id=discord_id)


async def exists_account_by_username(username: str) -> bool:
    """
    사용자명 존재 여부 확인

    Args:
        username: 사용자명

    Returns:
        존재하면 True
    """
    return await User.exists(username=username)
