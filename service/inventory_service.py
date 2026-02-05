"""
InventoryService

인벤토리 관리 (아이템 추가/삭제/조회)를 담당합니다.
"""
import logging
from typing import List, Optional

from models import Item, User
from models.user_inventory import UserInventory
from resources.item_emoji import ItemType
from exceptions import (
    ItemNotFoundError,
    InsufficientItemError,
    InventoryFullError,
)
from service.collection_service import CollectionService

logger = logging.getLogger(__name__)

# 인벤토리 최대 슬롯 수
MAX_INVENTORY_SLOTS = 100


class InventoryService:
    """인벤토리 비즈니스 로직"""

    @staticmethod
    async def add_item(
        user: User,
        item_id: int,
        quantity: int = 1,
        enhancement_level: int = 0
    ) -> UserInventory:
        """
        아이템 추가

        Args:
            user: 대상 사용자
            item_id: 아이템 ID
            quantity: 수량
            enhancement_level: 강화 레벨 (장비만 해당)

        Returns:
            UserInventory 객체

        Raises:
            ItemNotFoundError: 아이템을 찾을 수 없음
            InventoryFullError: 인벤토리가 가득 참
        """
        item = await Item.get_or_none(id=item_id)
        if not item:
            raise ItemNotFoundError(item_id)

        # 인벤토리 슬롯 체크
        current_slots = await UserInventory.filter(user=user).count()
        if current_slots >= MAX_INVENTORY_SLOTS:
            raise InventoryFullError(MAX_INVENTORY_SLOTS)

        # 소비 아이템은 스택
        if item.type == ItemType.CONSUME:
            existing = await UserInventory.get_or_none(
                user=user,
                item=item,
                enhancement_level=0
            )
            if existing:
                existing.quantity += quantity
                await existing.save()
                logger.debug(f"Stacked item {item_id} x{quantity} for user {user.id}")
                # 도감에 등록 (이미 등록된 경우 무시됨)
                await CollectionService.register_item(user, item_id)
                return existing

        # 새 인벤토리 항목 생성
        inv_item = await UserInventory.create(
            user=user,
            item=item,
            quantity=quantity,
            enhancement_level=enhancement_level
        )
        logger.info(f"Added item {item_id} x{quantity} to user {user.id}")

        # 도감에 등록
        await CollectionService.register_item(user, item_id)

        return inv_item

    @staticmethod
    async def remove_item(
        user: User,
        item_id: int,
        quantity: int = 1
    ) -> bool:
        """
        아이템 제거

        Args:
            user: 대상 사용자
            item_id: 아이템 ID
            quantity: 제거할 수량

        Returns:
            성공 여부

        Raises:
            ItemNotFoundError: 아이템을 찾을 수 없음
            InsufficientItemError: 아이템 수량 부족
        """
        inv_item = await UserInventory.get_or_none(
            user=user,
            item_id=item_id
        ).prefetch_related("item")

        if not inv_item:
            raise ItemNotFoundError(item_id)

        if inv_item.quantity < quantity:
            item = await Item.get(id=item_id)
            raise InsufficientItemError(
                item.name,
                quantity,
                inv_item.quantity
            )

        inv_item.quantity -= quantity
        if inv_item.quantity <= 0:
            await inv_item.delete()
            logger.info(f"Removed all of item {item_id} from user {user.id}")
        else:
            await inv_item.save()
            logger.debug(f"Removed item {item_id} x{quantity} from user {user.id}")

        return True

    @staticmethod
    async def get_inventory(user: User) -> List[UserInventory]:
        """
        인벤토리 전체 조회

        Args:
            user: 대상 사용자

        Returns:
            UserInventory 목록
        """
        return await UserInventory.filter(user=user).prefetch_related("item")

    @staticmethod
    async def get_inventory_item(
        user: User,
        inventory_id: int
    ) -> Optional[UserInventory]:
        """
        특정 인벤토리 아이템 조회

        Args:
            user: 대상 사용자
            inventory_id: 인벤토리 항목 ID

        Returns:
            UserInventory 객체 또는 None
        """
        return await UserInventory.get_or_none(
            id=inventory_id,
            user=user
        ).prefetch_related("item")

    @staticmethod
    async def get_item_by_item_id(
        user: User,
        item_id: int
    ) -> Optional[UserInventory]:
        """
        아이템 ID로 인벤토리 아이템 조회

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

    @staticmethod
    async def count_item(user: User, item_id: int) -> int:
        """
        아이템 수량 조회

        Args:
            user: 대상 사용자
            item_id: 아이템 ID

        Returns:
            아이템 수량 (없으면 0)
        """
        inv_item = await UserInventory.get_or_none(
            user=user,
            item_id=item_id
        )
        return inv_item.quantity if inv_item else 0

    @staticmethod
    async def get_inventory_count(user: User) -> int:
        """
        인벤토리 사용 슬롯 수 조회

        Args:
            user: 대상 사용자

        Returns:
            사용 중인 슬롯 수
        """
        return await UserInventory.filter(user=user).count()
