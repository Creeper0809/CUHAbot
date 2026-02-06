"""
ItemUseService

아이템 사용 (장비 장착 / 소모품 사용)을 담당합니다.
"""
import logging
import random
from dataclasses import dataclass
from typing import Optional

from models import EquipmentItem, Grade, ItemGradeProbability, User
from models.user_stats import UserStats
from models.user_inventory import UserInventory
from models.consume_item import ConsumeItem
from models.user_equipment import EquipmentSlot
from resources.item_emoji import ItemType
from config import DROP
from exceptions import (
    ItemNotFoundError,
    ItemNotEquippableError,
    CombatRestrictionError,
    InventoryFullError,
)
from service.session import get_session
from service.equipment_service import EquipmentService
from service.inventory_service import InventoryService

logger = logging.getLogger(__name__)


@dataclass
class ItemUseResult:
    """아이템 사용 결과"""
    success: bool
    message: str
    item_name: str
    effect_description: Optional[str] = None


class ItemUseService:
    """아이템 사용 서비스"""

    # equip_pos -> EquipmentSlot 매핑
    EQUIP_POS_TO_SLOT = {
        1: EquipmentSlot.HELMET,
        2: EquipmentSlot.ARMOR,
        3: EquipmentSlot.BOOTS,
        4: EquipmentSlot.WEAPON,
        5: EquipmentSlot.SUB_WEAPON,
        6: EquipmentSlot.GLOVES,
        7: EquipmentSlot.NECKLACE,
        8: EquipmentSlot.RING1,
    }

    @staticmethod
    async def use_item(
        user: User,
        inventory_id: int
    ) -> ItemUseResult:
        """
        아이템 사용

        Args:
            user: 사용자
            inventory_id: 인벤토리 아이템 ID

        Returns:
            사용 결과

        Raises:
            CombatRestrictionError: 전투 중 아이템 사용 시도
            ItemNotFoundError: 아이템을 찾을 수 없음
        """
        # 전투 중 체크
        session = get_session(user.discord_id)
        if session and session.in_combat:
            raise CombatRestrictionError("아이템 사용")

        # 인벤토리 아이템 조회
        inv_item = await UserInventory.get_or_none(
            id=inventory_id,
            user=user
        ).prefetch_related("item")

        if not inv_item:
            raise ItemNotFoundError(inventory_id)

        item = inv_item.item
        item_type = item.type

        # 타입별 처리
        if item_type == ItemType.EQUIP:
            return await ItemUseService._use_equipment(user, inv_item)
        elif item_type == ItemType.CONSUME:
            return await ItemUseService._use_consumable(user, inv_item)
        elif item_type == ItemType.SKILL:
            return ItemUseResult(
                success=False,
                message="스킬 아이템은 사용할 수 없습니다.",
                item_name=item.name
            )
        else:
            return ItemUseResult(
                success=False,
                message="이 아이템은 사용할 수 없습니다.",
                item_name=item.name
            )

    @staticmethod
    async def _use_equipment(
        user: User,
        inv_item: UserInventory
    ) -> ItemUseResult:
        """장비 아이템 사용 (장착)"""
        item = inv_item.item

        # 장비 정보 조회
        equipment = await EquipmentItem.get_or_none(item=item)
        if not equipment:
            raise ItemNotEquippableError(item.name)

        # equip_pos로 슬롯 결정
        slot = ItemUseService.EQUIP_POS_TO_SLOT.get(equipment.equip_pos)
        if not slot:
            # equip_pos가 없으면 기본적으로 무기 슬롯 사용
            slot = EquipmentSlot.WEAPON

        # 장비 장착
        await EquipmentService.equip_item(user, inv_item.id, slot)

        slot_name = EquipmentSlot.get_korean_name(slot)

        logger.info(
            f"User {user.id} equipped item {item.id} ({item.name}) "
            f"in slot {slot_name}"
        )

        return ItemUseResult(
            success=True,
            message=f"'{item.name}'을(를) [{slot_name}]에 장착했습니다!",
            item_name=item.name,
            effect_description=f"슬롯: {slot_name}"
        )

    @staticmethod
    async def _use_consumable(
        user: User,
        inv_item: UserInventory
    ) -> ItemUseResult:
        """소모품 아이템 사용"""
        item = inv_item.item

        # 소모품 정보 조회
        consume = await ConsumeItem.get_or_none(item=item)
        if not consume:
            return ItemUseResult(
                success=False,
                message="소모품 정보를 찾을 수 없습니다.",
                item_name=item.name
            )

        chest_grade = ItemUseService._get_chest_grade(item.id)
        if chest_grade:
            return await ItemUseService._use_chest_consumable(user, inv_item, chest_grade)

        # 효과 적용
        effect_desc = await ItemUseService._apply_consume_effect(user, consume)

        # 수량 차감
        inv_item.quantity -= 1
        if inv_item.quantity <= 0:
            await inv_item.delete()
        else:
            await inv_item.save()

        # 유저 저장
        await user.save()

        logger.info(
            f"User {user.id} used consumable {item.id} ({item.name}): {effect_desc}"
        )

        return ItemUseResult(
            success=True,
            message=f"'{item.name}'을(를) 사용했습니다!",
            item_name=item.name,
            effect_description=effect_desc
        )

    @staticmethod
    async def _apply_consume_effect(user: User, consume: ConsumeItem) -> str:
        """소모품 효과 적용"""
        effects = []

        # HP 회복
        if consume.amount and consume.amount > 0:
            actual_heal = user.heal(consume.amount)
            effects.append(f"HP +{actual_heal}")

        if not effects:
            effects.append("효과 없음")

        return ", ".join(effects)

    @staticmethod
    def _get_chest_grade(item_id: int) -> Optional[str]:
        chest_map = {
            DROP.CHEST_ITEM_NORMAL_ID: "normal",
            DROP.CHEST_ITEM_SILVER_ID: "silver",
            DROP.CHEST_ITEM_GOLD_ID: "gold",
        }
        return chest_map.get(item_id)

    @staticmethod
    def _calculate_chest_gold(user_level: int, chest_grade: str) -> int:
        grade_multiplier = {
            "normal": 1.0,
            "silver": 2.0,
            "gold": 5.0
        }.get(chest_grade, 1.0)
        base_gold = 20
        gold = int(base_gold * grade_multiplier * (1 + user_level / 10))
        return int(gold * random.uniform(0.8, 1.2))

    @staticmethod
    async def _roll_item_grade(chest_grade: str) -> Optional[str]:
        chest_id_map = {"normal": 1, "silver": 2, "gold": 3}
        chest_id = chest_id_map.get(chest_grade)

        if chest_id is not None:
            grade_probs = await ItemGradeProbability.filter(cheat_id=chest_id).all()
            if grade_probs:
                grades = []
                weights = []
                for entry in grade_probs:
                    if entry.grade is None:
                        continue
                    grade_value = entry.grade.value if hasattr(entry.grade, "value") else str(entry.grade)
                    grades.append(grade_value)
                    weights.append(float(entry.probability or 0))
                if grades and sum(weights) > 0:
                    return random.choices(grades, weights=weights, k=1)[0]

        grades = ["D", "C", "B", "A", "S", "SS", "SSS", "Mythic"]
        weights = [
            DROP.DROP_RATE_D,
            DROP.DROP_RATE_C,
            DROP.DROP_RATE_B,
            DROP.DROP_RATE_A,
            DROP.DROP_RATE_S,
            DROP.DROP_RATE_SS,
            DROP.DROP_RATE_SSS,
            DROP.DROP_RATE_MYTHIC,
        ]
        return random.choices(grades, weights=weights, k=1)[0]

    @staticmethod
    async def _pick_equipment_by_grade(grade_name: str) -> Optional[EquipmentItem]:
        grade = await Grade.get_or_none(name=grade_name)
        if not grade:
            return None
        candidates = await EquipmentItem.filter(grade=grade.id).prefetch_related("item")
        if not candidates:
            return None
        return random.choice(candidates)

    @staticmethod
    async def _use_chest_consumable(
        user: User,
        inv_item: UserInventory,
        chest_grade: str
    ) -> ItemUseResult:
        item = inv_item.item
        stats = await UserStats.get_or_none(user=user)
        if not stats:
            stats = await UserStats.create(user=user)

        if random.random() < DROP.CHEST_GOLD_RATE:
            gold_gained = ItemUseService._calculate_chest_gold(user.level, chest_grade)
            stats.gold += gold_gained
            await stats.save()

            inv_item.quantity -= 1
            if inv_item.quantity <= 0:
                await inv_item.delete()
            else:
                await inv_item.save()

            logger.info(
                f"User {user.id} opened chest {item.id} ({item.name}): gold={gold_gained}"
            )

            return ItemUseResult(
                success=True,
                message=f"'{item.name}'을(를) 열었습니다!",
                item_name=item.name,
                effect_description=f"골드 +{gold_gained}"
            )

        grade_name = await ItemUseService._roll_item_grade(chest_grade)
        if not grade_name:
            return ItemUseResult(
                success=False,
                message="상자 등급 판정에 실패했습니다.",
                item_name=item.name
            )

        equipment = await ItemUseService._pick_equipment_by_grade(grade_name)
        if not equipment or not equipment.item:
            return ItemUseResult(
                success=False,
                message="상자에서 나올 장비를 찾을 수 없습니다.",
                item_name=item.name
            )

        try:
            await InventoryService.add_item(user, equipment.item.id, 1)
        except InventoryFullError:
            return ItemUseResult(
                success=False,
                message="인벤토리가 가득 차서 상자를 열 수 없습니다.",
                item_name=item.name
            )

        inv_item.quantity -= 1
        if inv_item.quantity <= 0:
            await inv_item.delete()
        else:
            await inv_item.save()

        logger.info(
            f"User {user.id} opened chest {item.id} ({item.name}): item={equipment.item.id}"
        )

        return ItemUseResult(
            success=True,
            message=f"'{item.name}'을(를) 열었습니다!",
            item_name=item.name,
            effect_description=f"장비 '{equipment.item.name}' 획득"
        )
