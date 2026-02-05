"""
ShopService

NPC 상점 거래를 담당합니다.
장비, 포션, 스킬 구매/판매 기능을 제공합니다.
"""
import logging
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

from models import User, Item, Skill_Model
from models.user_inventory import UserInventory
from exceptions import (
    InsufficientGoldError,
    ItemNotFoundError,
    SkillNotFoundError,
)
from service.skill_ownership_service import SkillOwnershipService
from service.collection_service import CollectionService

logger = logging.getLogger(__name__)


class ShopItemType(str, Enum):
    """상점 아이템 타입"""
    EQUIPMENT = "EQUIPMENT"
    CONSUMABLE = "CONSUMABLE"
    SKILL = "SKILL"


@dataclass
class ShopItem:
    """상점 판매 아이템"""
    id: int
    name: str
    description: str
    price: int
    item_type: ShopItemType
    # 아이템일 경우 Item ID, 스킬일 경우 Skill ID
    target_id: int


@dataclass
class PurchaseResult:
    """구매 결과"""
    success: bool
    message: str
    item_name: str
    quantity: int
    total_cost: int
    remaining_gold: int


class ShopService:
    """상점 서비스"""

    # 기본 상점 아이템 정의
    DEFAULT_SHOP_ITEMS: List[ShopItem] = [
        # 소비 아이템 (포션) - Item ID는 docs/Items.md 기준
        ShopItem(1, "초급 HP 포션", "HP 100 회복", 50, ShopItemType.CONSUMABLE, 5001),
        ShopItem(2, "중급 HP 포션", "HP 300 회복", 150, ShopItemType.CONSUMABLE, 5002),
        ShopItem(3, "고급 HP 포션", "HP 700 회복", 400, ShopItemType.CONSUMABLE, 5003),

        # 무기 - docs/Items.md 기준
        ShopItem(11, "나무 검", "기본 검 (Attack +5)", 100, ShopItemType.EQUIPMENT, 1001),
        ShopItem(12, "철검", "튼튼한 검 (Attack +12)", 300, ShopItemType.EQUIPMENT, 1002),
        ShopItem(13, "강철검", "강철 검 (Attack +25)", 800, ShopItemType.EQUIPMENT, 1003),
        ShopItem(14, "전투 도끼", "강력한 도끼 (Attack +35)", 1200, ShopItemType.EQUIPMENT, 1103),
        ShopItem(15, "장궁", "원거리 무기 (Attack +22)", 700, ShopItemType.EQUIPMENT, 1303),

        # 방어구 - 투구
        ShopItem(21, "천 두건", "기본 투구 (HP +20)", 80, ShopItemType.EQUIPMENT, 2001),
        ShopItem(22, "가죽 모자", "가죽 투구 (HP +40)", 200, ShopItemType.EQUIPMENT, 2002),
        ShopItem(23, "철 투구", "철 투구 (HP +80)", 500, ShopItemType.EQUIPMENT, 2003),

        # 방어구 - 갑옷
        ShopItem(31, "천 옷", "기본 갑옷 (HP +30)", 100, ShopItemType.EQUIPMENT, 2101),
        ShopItem(32, "가죽 갑옷", "가죽 갑옷 (HP +60)", 250, ShopItemType.EQUIPMENT, 2102),
        ShopItem(33, "사슬 갑옷", "사슬 갑옷 (HP +120)", 600, ShopItemType.EQUIPMENT, 2103),

        # 방어구 - 장갑
        ShopItem(41, "천 장갑", "기본 장갑 (Attack +2)", 60, ShopItemType.EQUIPMENT, 2201),
        ShopItem(42, "가죽 장갑", "가죽 장갑 (Attack +5)", 150, ShopItemType.EQUIPMENT, 2202),

        # 기본 스킬
        ShopItem(101, "강타", "100% 물리 데미지", 500, ShopItemType.SKILL, 1001),
        ShopItem(102, "연속 베기", "60% 물리 데미지 x 2회", 800, ShopItemType.SKILL, 1002),
        ShopItem(103, "급소 찌르기", "120% + 치명타 보너스", 1000, ShopItemType.SKILL, 1003),
        ShopItem(104, "응급 처치", "HP 15% 회복", 600, ShopItemType.SKILL, 2001),
        ShopItem(105, "결의", "공격력/방어력 +15%", 1200, ShopItemType.SKILL, 3005),
    ]

    @staticmethod
    def get_shop_items() -> List[ShopItem]:
        """상점 아이템 목록 반환"""
        return ShopService.DEFAULT_SHOP_ITEMS.copy()

    @staticmethod
    def get_shop_item(shop_item_id: int) -> Optional[ShopItem]:
        """상점 아이템 조회"""
        for item in ShopService.DEFAULT_SHOP_ITEMS:
            if item.id == shop_item_id:
                return item
        return None

    @staticmethod
    async def get_user_gold(user: User) -> int:
        """유저 골드 조회"""
        return user.cuha_point

    @staticmethod
    async def purchase_item(
        user: User,
        shop_item_id: int,
        quantity: int = 1
    ) -> PurchaseResult:
        """
        아이템 구매

        Args:
            user: 구매자
            shop_item_id: 상점 아이템 ID
            quantity: 구매 수량

        Returns:
            구매 결과

        Raises:
            InsufficientGoldError: 골드 부족
            ItemNotFoundError: 아이템 없음
            SkillNotFoundError: 스킬 없음
        """
        shop_item = ShopService.get_shop_item(shop_item_id)
        if not shop_item:
            raise ItemNotFoundError(shop_item_id)

        total_cost = shop_item.price * quantity

        # 골드 확인
        if user.cuha_point < total_cost:
            raise InsufficientGoldError(total_cost, user.cuha_point)

        # 타입별 처리
        if shop_item.item_type == ShopItemType.SKILL:
            result = await ShopService._purchase_skill(
                user, shop_item, quantity
            )
        elif shop_item.item_type in (ShopItemType.EQUIPMENT, ShopItemType.CONSUMABLE):
            result = await ShopService._purchase_item(
                user, shop_item, quantity
            )
        else:
            raise ItemNotFoundError(shop_item_id)

        return result

    @staticmethod
    async def _purchase_skill(
        user: User,
        shop_item: ShopItem,
        quantity: int
    ) -> PurchaseResult:
        """스킬 구매 처리"""
        skill_id = shop_item.target_id
        total_cost = shop_item.price * quantity

        # 스킬 존재 확인
        skill = await Skill_Model.get_or_none(id=skill_id)
        if not skill:
            raise SkillNotFoundError(skill_id)

        # 골드 차감
        user.cuha_point -= total_cost
        await user.save()

        # 스킬 소유권 추가
        await SkillOwnershipService.add_skill(user, skill_id, quantity)

        # 도감에 등록
        await CollectionService.register_skill(user, skill_id)

        logger.info(
            f"User {user.id} purchased skill {skill_id} x{quantity} "
            f"for {total_cost} gold"
        )

        return PurchaseResult(
            success=True,
            message=f"'{shop_item.name}' 스킬을 {quantity}개 구매했습니다!",
            item_name=shop_item.name,
            quantity=quantity,
            total_cost=total_cost,
            remaining_gold=user.cuha_point
        )

    @staticmethod
    async def _purchase_item(
        user: User,
        shop_item: ShopItem,
        quantity: int
    ) -> PurchaseResult:
        """아이템 구매 처리"""
        item_id = shop_item.target_id
        total_cost = shop_item.price * quantity

        # 아이템 존재 확인
        item = await Item.get_or_none(id=item_id)
        if not item:
            raise ItemNotFoundError(item_id)

        # 골드 차감
        user.cuha_point -= total_cost
        await user.save()

        # 인벤토리에 추가
        inventory, created = await UserInventory.get_or_create(
            user=user,
            item=item,
            enhancement_level=0,
            defaults={"quantity": quantity}
        )

        if not created:
            inventory.quantity += quantity
            await inventory.save()

        # 도감에 등록
        await CollectionService.register_item(user, item_id)

        logger.info(
            f"User {user.id} purchased item {item_id} x{quantity} "
            f"for {total_cost} gold"
        )

        return PurchaseResult(
            success=True,
            message=f"'{shop_item.name}'을(를) {quantity}개 구매했습니다!",
            item_name=shop_item.name,
            quantity=quantity,
            total_cost=total_cost,
            remaining_gold=user.cuha_point
        )

    @staticmethod
    async def sell_item(
        user: User,
        inventory_id: int,
        quantity: int = 1
    ) -> PurchaseResult:
        """
        아이템 판매 (50% 가격)

        Args:
            user: 판매자
            inventory_id: 인벤토리 아이템 ID
            quantity: 판매 수량

        Returns:
            판매 결과
        """
        inventory = await UserInventory.get_or_none(
            id=inventory_id, user=user
        ).prefetch_related("item")

        if not inventory:
            raise ItemNotFoundError(inventory_id)

        if inventory.quantity < quantity:
            raise ItemNotFoundError(inventory_id)

        # 판매 가격 (기본 가격의 50%)
        # TODO: Item 모델에 base_price 필드 필요
        sell_price = 50 * quantity  # 임시 고정 가격

        # 골드 추가
        user.cuha_point += sell_price
        await user.save()

        # 인벤토리에서 제거
        item_name = inventory.item.name
        inventory.quantity -= quantity
        if inventory.quantity <= 0:
            await inventory.delete()
        else:
            await inventory.save()

        logger.info(
            f"User {user.id} sold item {inventory_id} x{quantity} "
            f"for {sell_price} gold"
        )

        return PurchaseResult(
            success=True,
            message=f"'{item_name}'을(를) {quantity}개 판매했습니다!",
            item_name=item_name,
            quantity=quantity,
            total_cost=-sell_price,  # 음수 = 획득
            remaining_gold=user.cuha_point
        )
