"""
ItemUseService

아이템 사용 (장비 장착 / 소모품 사용)을 담당합니다.
"""
import logging
from dataclasses import dataclass
from typing import Optional

from models import User
from models.user_inventory import UserInventory
from models.equipment_item import EquipmentItem
from models.consume_item import ConsumeItem
from models.user_equipment import EquipmentSlot
from resources.item_emoji import ItemType
from exceptions import (
    ItemNotFoundError,
    ItemNotEquippableError,
    CombatRestrictionError,
)
from service.session import get_session
from service.equipment_service import EquipmentService

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
