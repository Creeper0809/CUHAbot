"""
ShopService

NPC 상점 거래를 담당합니다.
장비, 포션, 스킬 구매/판매 기능을 제공합니다.
"""
import logging
import random
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional

from config import DROP
from models import EquipmentItem, Grade, Item, Skill_Model, User
from models.user_inventory import UserInventory
from resources.item_emoji import ItemType
from exceptions import (
    InsufficientGoldError,
    ItemNotFoundError,
    SkillNotFoundError,
)
from service.skill_ownership_service import SkillOwnershipService
from service.collection_service import CollectionService

# Grade name → ID 캐시 (load_grade_cache로 초기화)
_grade_name_to_id: Dict[str, int] = {}
_grade_price_cache: Dict[int, int] = {}

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
    grade_id: Optional[int] = None  # 등급 ID (1=D, 2=C, 3=B, 4=A, 5=S)


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

    DEFAULT_SKILL_PRICE: int = 500
    """등급 정보가 없는 스킬의 기본 가격"""

    @staticmethod
    async def load_grade_cache() -> None:
        """Grade 테이블 캐시 로드 (봇 시작 시 호출)"""
        global _grade_name_to_id, _grade_price_cache
        grades = await Grade.all()
        _grade_name_to_id = {g.name: g.id for g in grades if g.name}
        _grade_price_cache = {g.id: (g.shop_price or 0) for g in grades}
        logger.info(f"Grade cache loaded: {len(grades)} grades")

    @staticmethod
    def get_grade_price(grade_id: Optional[int]) -> int:
        """등급 ID로 상점 가격 조회"""
        if grade_id is None:
            return ShopService.DEFAULT_SKILL_PRICE
        return _grade_price_cache.get(grade_id, ShopService.DEFAULT_SKILL_PRICE)

    @staticmethod
    async def get_grade_name_by_id(grade_id: Optional[int]) -> str:
        """등급 ID로 등급 이름 조회"""
        if grade_id is None:
            return "D"
        grade = await Grade.get_or_none(id=grade_id)
        return grade.name if grade else "D"

    @staticmethod
    def get_shop_item_from_list(
        shop_items: List[ShopItem],
        shop_item_id: int
    ) -> Optional[ShopItem]:
        """상점 아이템 조회 (목록 기반)"""
        for item in shop_items:
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
        shop_items: List[ShopItem],
        shop_item_id: int,
        quantity: int = 1
    ) -> PurchaseResult:
        """
        아이템 구매

        Args:
            user: 구매자
            shop_items: 현재 상점에 표시된 아이템 목록
            shop_item_id: 상점 아이템 ID
            quantity: 구매 수량

        Returns:
            구매 결과

        Raises:
            InsufficientGoldError: 골드 부족
            ItemNotFoundError: 아이템 없음
            SkillNotFoundError: 스킬 없음
        """
        shop_item = ShopService.get_shop_item_from_list(shop_items, shop_item_id)
        if not shop_item:
            raise ItemNotFoundError(shop_item_id)

        return await ShopService.purchase_shop_item(user, shop_item, quantity)

    @staticmethod
    async def purchase_shop_item(
        user: User,
        shop_item: ShopItem,
        quantity: int = 1
    ) -> PurchaseResult:
        """상점 아이템 구매 처리 (ShopItem 직접 전달)"""
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
            raise ItemNotFoundError(shop_item.id)

        return result

    @staticmethod
    async def get_shop_items_for_display() -> List[ShopItem]:
        """상점 드롭다운에 표시할 아이템 구성"""
        potions = await ShopService._build_potion_items()
        random_equipment = await ShopService._build_random_equipment_items(count=5)
        random_skills = await ShopService._build_random_skill_items(count=5)
        return potions + random_equipment + random_skills

    @staticmethod
    async def _build_potion_items() -> List[ShopItem]:
        """포션 아이템 고정 표시 (DB 조회)"""
        potion_items = await Item.filter(
            type=ItemType.CONSUME,
            name__contains="포션"
        ).all()

        shop_items = []
        for item in potion_items:
            shop_items.append(
                ShopItem(
                    id=ShopService._build_shop_item_id("potion", item.id),
                    name=item.name,
                    description=item.description or "포션",
                    price=item.cost or 50,
                    item_type=ShopItemType.CONSUMABLE,
                    target_id=item.id
                )
            )
        return shop_items

    @staticmethod
    async def _build_random_equipment_items(count: int = 5) -> List[ShopItem]:
        """장비를 등급 확률에 따라 랜덤 선택"""
        grade_map = {grade.id: grade.name for grade in await Grade.all()}
        equipment_items = await EquipmentItem.all().prefetch_related("item")

        equipment_by_grade: Dict[str, List[EquipmentItem]] = {}
        for equipment in equipment_items:
            grade_name = grade_map.get(equipment.grade, "D")
            equipment_by_grade.setdefault(grade_name, []).append(equipment)

        grade_weights = [
            ("D", DROP.DROP_RATE_D),
            ("C", DROP.DROP_RATE_C),
            ("B", DROP.DROP_RATE_B),
            ("A", DROP.DROP_RATE_A),
            ("S", DROP.DROP_RATE_S),
            ("SS", DROP.DROP_RATE_SS),
            ("SSS", DROP.DROP_RATE_SSS),
            ("Mythic", DROP.DROP_RATE_MYTHIC),
        ]

        selected: List[ShopItem] = []
        selected_targets = set()
        attempts = 0
        all_candidates = []
        for grade_items in equipment_by_grade.values():
            all_candidates.extend(grade_items)

        while len(selected) < count and attempts < 100:
            attempts += 1
            grades, weights = zip(*grade_weights)
            grade = random.choices(grades, weights=weights, k=1)[0]

            candidates = equipment_by_grade.get(grade, [])

            if not candidates:
                continue

            chosen = random.choice(candidates)
            target_key = chosen.id
            if target_key in selected_targets:
                continue

            selected_targets.add(target_key)
            item = chosen.item
            selected.append(
                ShopItem(
                    id=ShopService._build_shop_item_id("equipment", item.id),
                    name=item.name,
                    description=item.description or "장비",
                    price=item.cost or 100,
                    item_type=ShopItemType.EQUIPMENT,
                    target_id=item.id,
                    grade_id=getattr(item, 'grade_id', chosen.grade)
                )
            )

        if len(selected) < count and all_candidates:
            for chosen in all_candidates:
                if len(selected) >= count:
                    break
                target_key = chosen.id
                if target_key in selected_targets:
                    continue
                selected_targets.add(target_key)
                item = chosen.item
                selected.append(
                    ShopItem(
                        id=ShopService._build_shop_item_id("equipment", item.id),
                        name=item.name,
                        description=item.description or "장비",
                        price=item.cost or 100,
                        item_type=ShopItemType.EQUIPMENT,
                        target_id=item.id,
                        grade_id=getattr(item, 'grade_id', chosen.grade)
                    )
                )

        return selected

    @staticmethod
    async def _build_random_skill_items(count: int = 5) -> List[ShopItem]:
        """스킬을 등급 확률에 따라 랜덤 선택 (DB 조회)"""
        grade_map = {grade.id: grade.name for grade in await Grade.all()}
        skills = await Skill_Model.all()

        skills_by_grade: Dict[str, List[Skill_Model]] = {}
        for skill in skills:
            grade_name = grade_map.get(skill.grade, "D") if skill.grade else "D"
            skills_by_grade.setdefault(grade_name, []).append(skill)

        grade_weights = [
            ("D", DROP.DROP_RATE_D),
            ("C", DROP.DROP_RATE_C),
            ("B", DROP.DROP_RATE_B),
            ("A", DROP.DROP_RATE_A),
            ("S", DROP.DROP_RATE_S),
            ("SS", DROP.DROP_RATE_SS),
            ("SSS", DROP.DROP_RATE_SSS),
            ("Mythic", DROP.DROP_RATE_MYTHIC),
        ]

        selected: List[ShopItem] = []
        selected_targets = set()
        attempts = 0

        while len(selected) < count and attempts < 100:
            attempts += 1
            grades, weights = zip(*grade_weights)
            grade = random.choices(grades, weights=weights, k=1)[0]

            candidates = skills_by_grade.get(grade, [])
            if not candidates:
                continue

            chosen = random.choice(candidates)
            if chosen.id in selected_targets:
                continue

            selected_targets.add(chosen.id)
            price = ShopService.get_grade_price(chosen.grade)
            selected.append(
                ShopItem(
                    id=ShopService._build_shop_item_id("skill", chosen.id),
                    name=chosen.name,
                    description=chosen.description or "스킬",
                    price=price,
                    item_type=ShopItemType.SKILL,
                    target_id=chosen.id,
                    grade_id=chosen.grade
                )
            )

        # 부족 시 남은 스킬로 채우기
        if len(selected) < count:
            all_candidates = [s for s in skills if s.id not in selected_targets]
            for chosen in all_candidates:
                if len(selected) >= count:
                    break
                selected_targets.add(chosen.id)
                price = ShopService.get_grade_price(chosen.grade)
                selected.append(
                    ShopItem(
                        id=ShopService._build_shop_item_id("skill", chosen.id),
                        name=chosen.name,
                        description=chosen.description or "스킬",
                        price=price,
                        item_type=ShopItemType.SKILL,
                        target_id=chosen.id,
                        grade_id=chosen.grade
                    )
                )

        return selected

    @staticmethod
    def _build_shop_item_id(prefix: str, target_id: int) -> int:
        prefix_map = {
            "potion": 100000,
            "equipment": 200000,
            "skill": 300000,
        }
        return prefix_map.get(prefix, 900000) + target_id

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
        base_price = inventory.item.cost or 50
        sell_price = (base_price // 2) * quantity

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
