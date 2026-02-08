"""
EquipmentService

장비 착용/해제/스탯 계산을 담당합니다.
"""
import logging
from typing import Dict, List, Optional

from models import User
from models.user_inventory import UserInventory
from models.user_equipment import UserEquipment, EquipmentSlot
from models.equipment_item import EquipmentItem
from exceptions import (
    ItemNotFoundError,
    ItemNotEquippableError,
    EquipmentSlotMismatchError,
    CombatRestrictionError,
    LevelRequirementError,
    StatRequirementError,
)
from service.session import get_session

logger = logging.getLogger(__name__)


class EquipmentService:
    """장비 비즈니스 로직"""

    @staticmethod
    async def equip_item(
        user: User,
        inventory_item_id: int,
        slot: EquipmentSlot
    ) -> UserEquipment:
        """
        장비 착용

        Args:
            user: 대상 사용자
            inventory_item_id: 인벤토리 아이템 ID
            slot: 장착할 슬롯

        Returns:
            UserEquipment 객체

        Raises:
            CombatRestrictionError: 전투 중 장비 변경 시도
            ItemNotFoundError: 인벤토리 아이템을 찾을 수 없음
            ItemNotEquippableError: 장착 불가능한 아이템
            EquipmentSlotMismatchError: 슬롯 불일치
            LevelRequirementError: 레벨 요구사항 미충족
        """
        # 전투 중 체크
        session = get_session(user.discord_id)
        if session and session.in_combat:
            raise CombatRestrictionError("장비 변경")

        # 인벤토리 아이템 확인
        inv_item = await UserInventory.get_or_none(
            id=inventory_item_id,
            user=user
        ).prefetch_related("item")

        if not inv_item:
            raise ItemNotFoundError(inventory_item_id)

        # 장비 아이템인지 확인
        equipment = await EquipmentItem.get_or_none(item=inv_item.item)
        if not equipment:
            raise ItemNotEquippableError(inv_item.item.name)

        # 슬롯 호환성 체크 (equip_pos가 있는 경우)
        if equipment.equip_pos is not None:
            expected_slot = EquipmentService._get_slot_from_equip_pos(equipment.equip_pos)
            if expected_slot and expected_slot != slot:
                raise EquipmentSlotMismatchError(
                    inv_item.item.name,
                    EquipmentSlot.get_korean_name(expected_slot),
                    EquipmentSlot.get_korean_name(slot)
                )

        # 레벨 요구사항 체크
        if equipment.require_level and user.level < equipment.require_level:
            raise LevelRequirementError(equipment.require_level, user.level)

        # 능력치 요구사항 체크
        stat_checks = [
            ("STR", equipment.require_str, user.bonus_str),
            ("INT", equipment.require_int, user.bonus_int),
            ("DEX", equipment.require_dex, user.bonus_dex),
            ("VIT", equipment.require_vit, user.bonus_vit),
            ("LUK", equipment.require_luk, user.bonus_luk),
        ]
        for stat_name, required, current in stat_checks:
            if required and current < required:
                raise StatRequirementError(stat_name, required, current)

        # 기존 장비 해제
        await UserEquipment.filter(user=user, slot=slot).delete()

        # 새 장비 착용
        equipped = await UserEquipment.create(
            user=user,
            slot=slot,
            inventory_item=inv_item
        )

        logger.info(f"User {user.id} equipped item {inv_item.item.id} in slot {slot.name}")
        await EquipmentService.apply_equipment_stats(user)
        return equipped

    @staticmethod
    def _get_slot_from_equip_pos(equip_pos: int) -> Optional[EquipmentSlot]:
        """equip_pos를 EquipmentSlot으로 변환"""
        pos_to_slot = {
            1: EquipmentSlot.HELMET,
            2: EquipmentSlot.ARMOR,
            3: EquipmentSlot.BOOTS,
            4: EquipmentSlot.WEAPON,
            5: EquipmentSlot.SUB_WEAPON,
        }
        return pos_to_slot.get(equip_pos)

    @staticmethod
    async def unequip_item(user: User, slot: EquipmentSlot) -> bool:
        """
        장비 해제

        Args:
            user: 대상 사용자
            slot: 해제할 슬롯

        Returns:
            성공 여부

        Raises:
            CombatRestrictionError: 전투 중 장비 변경 시도
        """
        session = get_session(user.discord_id)
        if session and session.in_combat:
            raise CombatRestrictionError("장비 변경")

        deleted = await UserEquipment.filter(user=user, slot=slot).delete()
        if deleted:
            logger.info(f"User {user.id} unequipped slot {slot.name}")
            await EquipmentService.apply_equipment_stats(user)
        return deleted > 0

    @staticmethod
    async def get_equipped_items(user: User) -> List[UserEquipment]:
        """
        장착 장비 목록 조회

        Args:
            user: 대상 사용자

        Returns:
            UserEquipment 목록
        """
        return await UserEquipment.filter(user=user).prefetch_related(
            "inventory_item__item"
        )

    @staticmethod
    async def get_equipped_in_slot(
        user: User,
        slot: EquipmentSlot
    ) -> Optional[UserEquipment]:
        """
        특정 슬롯의 장비 조회

        Args:
            user: 대상 사용자
            slot: 조회할 슬롯

        Returns:
            UserEquipment 객체 또는 None
        """
        return await UserEquipment.get_or_none(
            user=user,
            slot=slot
        ).prefetch_related("inventory_item__item")

    @staticmethod
    async def calculate_equipment_stats(user: User) -> Dict[str, int]:
        """
        장착 장비 스탯 합산 (장비 * 등급 배율 + 강화 + 특수효과 + 세트 효과)

        Args:
            user: 대상 사용자

        Returns:
            스탯 딕셔너리
        """
        from service.item.set_detection_service import SetDetectionService
        from service.item.grade_service import GradeService

        equipped = await UserEquipment.filter(user=user).prefetch_related(
            "inventory_item__item"
        )

        total_stats = {
            "hp": 0,
            "attack": 0,
            "ap_attack": 0,
            "ad_defense": 0,
            "ap_defense": 0,
            "speed": 0
        }
        # 퍼센트 기반 특수 효과 누적
        special_effects_agg: Dict[str, float] = {}

        for eq in equipped:
            equipment = await EquipmentItem.get_or_none(
                item=eq.inventory_item.item
            )
            if not equipment:
                continue

            # 인스턴스 등급 배율
            grade_mult = GradeService.get_stat_multiplier(
                eq.inventory_item.instance_grade
            )

            # 기본 스탯 * 등급 배율
            base_stats = {
                "hp": int(equipment.hp * grade_mult) if equipment.hp else 0,
                "attack": int(equipment.attack * grade_mult) if equipment.attack else 0,
                "ap_attack": int(equipment.ap_attack * grade_mult) if equipment.ap_attack else 0,
                "ad_defense": int(equipment.ad_defense * grade_mult) if equipment.ad_defense else 0,
                "ap_defense": int(equipment.ap_defense * grade_mult) if equipment.ap_defense else 0,
                "speed": int(equipment.speed * grade_mult) if equipment.speed else 0,
            }

            for stat_key, base_val in base_stats.items():
                total_stats[stat_key] += base_val

            # 강화 보너스 (등급 적용 후 기준, 5% per level)
            enhancement = eq.inventory_item.enhancement_level
            if enhancement > 0:
                bonus_mult = enhancement * 0.05
                for stat_key, base_val in base_stats.items():
                    total_stats[stat_key] += int(base_val * bonus_mult)

            # 특수 효과 집계
            effects = eq.inventory_item.special_effects
            if effects:
                for effect in effects:
                    etype = effect.get("type", "")
                    value = effect.get("value", 0)
                    special_effects_agg[etype] = (
                        special_effects_agg.get(etype, 0) + value
                    )

        # 특수 효과 → 스탯 변환
        _apply_special_effects_to_stats(total_stats, special_effects_agg)

        # 세트 효과 보너스 적용
        set_bonuses = await SetDetectionService.get_set_bonus_stats(user)
        for stat, bonus in set_bonuses.items():
            if stat not in total_stats:
                continue
            if isinstance(bonus, int):
                total_stats[stat] += bonus
            elif isinstance(bonus, float) and 0 < bonus < 1:
                total_stats[stat] = int(total_stats[stat] * (1 + bonus))
            else:
                total_stats[stat] += int(bonus)

        return total_stats

    @staticmethod
    async def apply_equipment_stats(user: User) -> None:
        """장비 스탯을 런타임 필드에 반영"""
        stats = await EquipmentService.calculate_equipment_stats(user)
        user.equipment_stats = stats


def _apply_special_effects_to_stats(
    stats: Dict[str, int],
    effects_agg: Dict[str, float]
) -> None:
    """
    누적된 특수 효과를 스탯에 반영

    퍼센트 기반 효과는 기존 스탯에 곱연산으로 적용합니다.
    전투 전용 효과 (lifesteal, crit_rate 등)는 별도 딕셔너리에 보관합니다.
    """
    # HP 퍼센트 보너스
    bonus_hp_pct = effects_agg.get("bonus_hp_pct", 0)
    if bonus_hp_pct > 0 and stats["hp"] > 0:
        stats["hp"] += int(stats["hp"] * bonus_hp_pct / 100)

    # 속도 퍼센트 보너스
    bonus_speed_pct = effects_agg.get("bonus_speed_pct", 0)
    if bonus_speed_pct > 0 and stats["speed"] > 0:
        stats["speed"] += int(stats["speed"] * bonus_speed_pct / 100)

    # 전투 전용 효과는 stats에 키로 추가 (combat에서 참조)
    combat_effects = ["lifesteal", "crit_rate", "crit_damage", "armor_pen"]
    for effect_type in combat_effects:
        value = effects_agg.get(effect_type, 0)
        if value > 0:
            stats[effect_type] = value
