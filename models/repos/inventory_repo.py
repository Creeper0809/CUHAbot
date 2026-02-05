"""
UserInventory Repository

사용자 인벤토리 데이터 접근 레이어입니다.
"""
from typing import List, Optional

from models import User, Item
from models.user_inventory import UserInventory


async def get_user_inventory(user: User) -> List[UserInventory]:
    """
    사용자 인벤토리 전체 조회

    Args:
        user: 대상 사용자

    Returns:
        UserInventory 목록
    """
    return await UserInventory.filter(user=user).prefetch_related("item")


async def get_inventory_item(user: User, item_id: int) -> Optional[UserInventory]:
    """
    특정 아이템 조회

    Args:
        user: 대상 사용자
        item_id: 아이템 ID

    Returns:
        UserInventory 객체 또는 None
    """
    return await UserInventory.get_or_none(
        user=user,
        item_id=item_id
    ).prefetch_related("item")


async def get_inventory_by_id(inventory_id: int) -> Optional[UserInventory]:
    """
    인벤토리 ID로 조회

    Args:
        inventory_id: 인벤토리 항목 ID

    Returns:
        UserInventory 객체 또는 None
    """
    return await UserInventory.get_or_none(id=inventory_id).prefetch_related("item")


async def count_item(user: User, item_id: int) -> int:
    """
    아이템 수량 조회

    Args:
        user: 대상 사용자
        item_id: 아이템 ID

    Returns:
        아이템 수량 (없으면 0)
    """
    inv = await get_inventory_item(user, item_id)
    return inv.quantity if inv else 0


async def get_inventory_count(user: User) -> int:
    """
    인벤토리 사용 슬롯 수 조회

    Args:
        user: 대상 사용자

    Returns:
        사용 중인 슬롯 수
    """
    return await UserInventory.filter(user=user).count()
