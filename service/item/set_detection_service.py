"""
SetDetectionService

장착된 장비를 기반으로 활성 세트 효과를 감지합니다.
"""
import logging
from typing import List, Dict, Tuple
from collections import defaultdict

from models import User, SetItem, SetItemMember, SetEffect
from models.user_equipment import UserEquipment

logger = logging.getLogger(__name__)


class SetDetectionService:
    """세트 아이템 감지 및 효과 적용 서비스"""

    @staticmethod
    async def detect_active_sets(user: User) -> List[SetEffect]:
        """
        사용자가 장착한 장비로부터 활성화된 세트 효과 감지

        Args:
            user: 사용자

        Returns:
            활성화된 세트 효과 리스트 (2세트, 4세트 등)
        """
        # 1. 장착된 장비 조회
        equipped_items = await UserEquipment.filter(
            user=user
        ).prefetch_related("inventory_item__item")

        if not equipped_items:
            return []

        # 2. 장비 ID 추출
        equipped_ids = []
        for user_equip in equipped_items:
            if user_equip.inventory_item and user_equip.inventory_item.item:
                # EquipmentItem ID가 필요하므로 item_id로 조회
                equipped_ids.append(user_equip.inventory_item.item.id)

        if not equipped_ids:
            return []

        # 3. 세트 구성원 정보 조회 (장착된 아이템들이 속한 세트 찾기)
        # EquipmentItem을 item_id로 조회
        from models import EquipmentItem
        equipment_items = await EquipmentItem.filter(
            item_id__in=equipped_ids
        ).prefetch_related("item")

        equipment_item_ids = [eq.id for eq in equipment_items]

        if not equipment_item_ids:
            return []

        set_members = await SetItemMember.filter(
            equipment_item_id__in=equipment_item_ids
        ).prefetch_related("set_item")

        if not set_members:
            return []

        # 4. 세트별 장착 개수 카운트
        set_counts: Dict[int, int] = defaultdict(int)
        for member in set_members:
            set_counts[member.set_item_id] += 1

        # 5. 활성화된 세트 효과 조회
        active_effects = []
        for set_id, count in set_counts.items():
            # 해당 세트의 모든 효과 조회
            effects = await SetEffect.filter(
                set_item_id=set_id,
                pieces_required__lte=count  # 필요 개수 이하인 효과만
            ).order_by("pieces_required")

            active_effects.extend(effects)

        logger.debug(
            f"User {user.id} has {len(active_effects)} active set effects "
            f"from {len(set_counts)} sets"
        )

        return active_effects

    @staticmethod
    async def get_set_bonus_stats(user: User) -> Dict[str, float]:
        """
        세트 효과로부터 스탯 보너스 계산

        Args:
            user: 사용자

        Returns:
            스탯 보너스 딕셔너리 (key: 스탯 이름, value: 보너스 값)
        """
        active_effects = await SetDetectionService.detect_active_sets(user)

        if not active_effects:
            return {}

        # 모든 활성 효과의 스탯 보너스 합산
        total_bonuses: Dict[str, float] = defaultdict(float)

        for effect in active_effects:
            bonuses = effect.get_stat_bonuses()
            for stat, value in bonuses.items():
                total_bonuses[stat] += value

        return dict(total_bonuses)

    @staticmethod
    async def get_set_summary(user: User) -> List[Tuple[str, int, List[str]]]:
        """
        사용자의 세트 장착 상황 요약

        Args:
            user: 사용자

        Returns:
            [(세트 이름, 장착 개수, [활성 효과 설명])] 리스트
        """
        # 장착된 장비 조회
        equipped_items = await UserEquipment.filter(
            user=user
        ).prefetch_related("inventory_item__item")

        if not equipped_items:
            return []

        equipped_ids = []
        for user_equip in equipped_items:
            if user_equip.inventory_item and user_equip.inventory_item.item:
                equipped_ids.append(user_equip.inventory_item.item.id)

        if not equipped_ids:
            return []

        # EquipmentItem 조회
        from models import EquipmentItem
        equipment_items = await EquipmentItem.filter(
            item_id__in=equipped_ids
        ).prefetch_related("item")

        equipment_item_ids = [eq.id for eq in equipment_items]

        if not equipment_item_ids:
            return []

        # 세트 구성원 조회
        set_members = await SetItemMember.filter(
            equipment_item_id__in=equipment_item_ids
        ).prefetch_related("set_item")

        if not set_members:
            return []

        # 세트별 카운트
        set_counts: Dict[int, int] = defaultdict(int)
        set_names: Dict[int, str] = {}

        for member in set_members:
            set_id = member.set_item_id
            set_counts[set_id] += 1
            if set_id not in set_names:
                set_names[set_id] = member.set_item.name

        # 각 세트별 활성 효과 설명 수집
        summaries = []
        for set_id, count in set_counts.items():
            effects = await SetEffect.filter(
                set_item_id=set_id,
                pieces_required__lte=count
            ).order_by("pieces_required")

            effect_descs = [f"{e.pieces_required}세트: {e.effect_description}" for e in effects]

            summaries.append((
                set_names[set_id],
                count,
                effect_descs
            ))

        return summaries
