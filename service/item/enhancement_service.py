"""
EnhancementService

아이템 강화 시스템을 담당합니다.
"""
import logging
import random
from dataclasses import dataclass
from typing import Optional

from models import User
from models.user_inventory import UserInventory
from models.equipment_item import EquipmentItem
from resources.item_emoji import ItemType
from exceptions import (
    ItemNotFoundError,
    InsufficientGoldError,
    CombatRestrictionError,
)
from config import ENHANCEMENT
from service.session import get_session

logger = logging.getLogger(__name__)


class EnhancementResult:
    """강화 결과"""
    SUCCESS = "success"          # 성공 (+1)
    FAIL_MAINTAIN = "maintain"   # 실패 (유지)
    FAIL_DECREASE = "decrease"   # 실패 (하락)
    FAIL_RESET = "reset"         # 실패 (초기화)
    FAIL_DESTROY = "destroy"     # 실패 (파괴)


@dataclass
class EnhancementAttempt:
    """강화 시도 결과"""
    success: bool
    result_type: str  # EnhancementResult
    previous_level: int
    new_level: int
    cost: int
    item_name: str
    item_destroyed: bool = False


class EnhancementService:
    """아이템 강화 서비스"""

    # 강화 성공률 (레벨 범위별)
    SUCCESS_RATES = {
        (0, 3): 1.0,    # +0~3: 100%
        (4, 6): 0.8,    # +4~6: 80%
        (7, 9): 0.6,    # +7~9: 60%
        (10, 12): 0.4,  # +10~12: 40%
        (13, 15): 0.2,  # +13~15: 20%
    }

    GRADE_MULTIPLIERS = {
        1: 0.5,   # D등급
        2: 0.8,   # C등급
        3: 1.0,   # B등급
        4: 1.5,   # A등급
        5: 2.0,   # S등급
        6: 3.0,   # SS등급
        7: 5.0,   # SSS등급
        8: 10.0,  # 신화등급
    }

    @staticmethod
    def _get_success_rate(current_level: int) -> float:
        """강화 성공률 조회"""
        for (min_lvl, max_lvl), rate in EnhancementService.SUCCESS_RATES.items():
            if min_lvl <= current_level <= max_lvl:
                return rate
        return 0.0

    @staticmethod
    def _calculate_cost(grade_id: int, current_level: int) -> int:
        """
        강화 비용 계산

        Args:
            grade_id: 아이템 등급 ID
            current_level: 현재 강화 레벨

        Returns:
            필요 골드
        """
        grade_mult = EnhancementService.GRADE_MULTIPLIERS.get(grade_id, 1.0)
        level_mult = 1.0 + (current_level * ENHANCEMENT.COST_PER_LEVEL_MULTIPLIER)
        cost = int(ENHANCEMENT.BASE_COST * grade_mult * level_mult)
        return cost

    @staticmethod
    async def get_enhancement_info(
        user: User,
        inventory_id: int
    ) -> dict:
        """
        강화 가능 여부 및 정보 조회

        Args:
            user: 사용자
            inventory_id: 인벤토리 아이템 ID

        Returns:
            강화 정보 딕셔너리

        Raises:
            ItemNotFoundError: 아이템을 찾을 수 없음
        """
        inv_item = await UserInventory.get_or_none(
            id=inventory_id,
            user=user
        ).prefetch_related("item")

        if not inv_item:
            raise ItemNotFoundError(inventory_id)

        # 장비 아이템만 강화 가능
        if inv_item.item.type != ItemType.EQUIP:
            return {
                "can_enhance": False,
                "reason": "장비 아이템만 강화할 수 있습니다."
            }

        equipment = await EquipmentItem.get_or_none(item=inv_item.item)
        if not equipment:
            return {
                "can_enhance": False,
                "reason": "장비 정보를 찾을 수 없습니다."
            }

        current_level = inv_item.enhancement_level
        if current_level >= ENHANCEMENT.MAX_LEVEL:
            return {
                "can_enhance": False,
                "reason": f"최대 강화 레벨입니다 (+{ENHANCEMENT.MAX_LEVEL})"
            }

        # 강화 비용 계산
        grade_id = getattr(inv_item.item, 'grade_id', 3)
        cost = EnhancementService._calculate_cost(grade_id, current_level)

        # 성공률 조회 (축복/저주 보정)
        success_rate = EnhancementService._get_success_rate(current_level)
        is_blessed = inv_item.is_blessed
        is_cursed = inv_item.is_cursed

        if is_blessed:
            success_rate = min(1.0, success_rate + 0.10)
        if is_cursed:
            success_rate = max(0.0, success_rate - 0.10)

        # 골드 확인
        current_gold = user.gold

        can_enhance = current_gold >= cost
        reason = None
        if not can_enhance:
            reason = f"골드가 부족합니다 ({current_gold:,}G / {cost:,}G)"

        return {
            "can_enhance": can_enhance,
            "current_level": current_level,
            "success_rate": success_rate,
            "cost": cost,
            "current_gold": current_gold,
            "item_name": inv_item.item.name,
            "grade_id": grade_id,
            "reason": reason,
            "is_blessed": is_blessed,
            "is_cursed": is_cursed,
        }

    @staticmethod
    async def attempt_enhancement(
        user: User,
        inventory_id: int
    ) -> EnhancementAttempt:
        """
        강화 시도

        Args:
            user: 사용자
            inventory_id: 인벤토리 아이템 ID

        Returns:
            강화 시도 결과

        Raises:
            CombatRestrictionError: 전투 중 강화 시도
            ItemNotFoundError: 아이템을 찾을 수 없음
            InsufficientGoldError: 골드 부족
        """
        # 전투 중 체크
        session = get_session(user.discord_id)
        if session and session.in_combat:
            raise CombatRestrictionError("강화")

        # 아이템 조회
        inv_item = await UserInventory.get_or_none(
            id=inventory_id,
            user=user
        ).prefetch_related("item")

        if not inv_item:
            raise ItemNotFoundError(inventory_id)

        # 장비 확인
        if inv_item.item.type != ItemType.EQUIP:
            raise ValueError("장비 아이템만 강화할 수 있습니다.")

        equipment = await EquipmentItem.get_or_none(item=inv_item.item)
        if not equipment:
            raise ValueError("장비 정보를 찾을 수 없습니다.")

        current_level = inv_item.enhancement_level
        if current_level >= ENHANCEMENT.MAX_LEVEL:
            raise ValueError(f"최대 강화 레벨입니다 (+{ENHANCEMENT.MAX_LEVEL})")

        # 비용 계산 및 차감
        grade_id = getattr(inv_item.item, 'grade_id', 3)
        cost = EnhancementService._calculate_cost(grade_id, current_level)

        if user.gold < cost:
            raise InsufficientGoldError(cost, user.gold)

        user.gold -= cost
        await user.save()

        # 성공률 조회 (축복/저주 보정)
        success_rate = EnhancementService._get_success_rate(current_level)
        is_blessed = inv_item.is_blessed
        is_cursed = inv_item.is_cursed

        if is_blessed:
            success_rate = min(1.0, success_rate + 0.10)
        if is_cursed:
            success_rate = max(0.0, success_rate - 0.10)

        # 강화 시도
        roll = random.random()
        success = roll < success_rate

        result_type = ""
        new_level = current_level
        item_destroyed = False

        if success:
            # 성공: +1
            new_level = current_level + 1
            result_type = EnhancementResult.SUCCESS
            inv_item.enhancement_level = new_level
            await inv_item.save()

        else:
            # 축복 상태: 실패 시 항상 유지
            if is_blessed:
                result_type = EnhancementResult.FAIL_MAINTAIN

            elif current_level <= 6:
                # +0~6: 유지
                result_type = EnhancementResult.FAIL_MAINTAIN

            elif current_level <= 9:
                # +7~9: -1
                new_level = max(0, current_level - 1)
                result_type = EnhancementResult.FAIL_DECREASE
                inv_item.enhancement_level = new_level
                await inv_item.save()

            elif current_level <= 12:
                # +10~12: -2
                new_level = max(0, current_level - 2)
                result_type = EnhancementResult.FAIL_DECREASE
                inv_item.enhancement_level = new_level
                await inv_item.save()

            else:
                # +13~15: 초기화 또는 파괴
                destroy_rate = ENHANCEMENT.DESTRUCTION_RATE
                if is_cursed:
                    destroy_rate *= 2  # 저주 시 파괴 확률 2배

                destruction_roll = random.random()
                if destruction_roll < destroy_rate:
                    result_type = EnhancementResult.FAIL_DESTROY
                    item_destroyed = True
                    new_level = 0
                    await inv_item.delete()
                else:
                    new_level = 0
                    result_type = EnhancementResult.FAIL_RESET
                    inv_item.enhancement_level = 0
                    await inv_item.save()

        logger.info(
            f"User {user.id} enhancement attempt: {inv_item.item.name} "
            f"+{current_level} → +{new_level} ({result_type}), cost={cost}"
        )

        return EnhancementAttempt(
            success=success,
            result_type=result_type,
            previous_level=current_level,
            new_level=new_level,
            cost=cost,
            item_name=inv_item.item.name,
            item_destroyed=item_destroyed
        )

    @staticmethod
    def get_success_rate_description(current_level: int) -> str:
        """강화 성공률 설명"""
        rate = EnhancementService._get_success_rate(current_level)
        percentage = int(rate * 100)

        if current_level <= 3:
            penalty = "실패 시: 유지"
        elif current_level <= 6:
            penalty = "실패 시: 유지"
        elif current_level <= 9:
            penalty = "실패 시: -1"
        elif current_level <= 12:
            penalty = "실패 시: -2"
        else:
            penalty = "실패 시: 초기화 (20% 파괴)"

        return f"성공률 {percentage}% | {penalty}"
