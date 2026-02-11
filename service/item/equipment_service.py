"""
EquipmentService

장비 착용/해제/스탯 계산을 담당합니다.
"""
import logging
from typing import Any, Dict, List, Optional

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
from service.tower.tower_restriction import enforce_equipment_change_restriction
from service.item.equipment_component_loader import (
    load_equipment_components,
    get_equipment_passive_stats
)

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
        enforce_equipment_change_restriction(session)

        # 인벤토리 아이템 확인
        inv_item = await UserInventory.filter(
            id=inventory_item_id,
            user=user
        ).prefetch_related("item").first()

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
        enforce_equipment_change_restriction(session)

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
        return await UserEquipment.filter(
            user=user,
            slot=slot
        ).prefetch_related("inventory_item__item").first()

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

        # 모든 장비의 컴포넌트를 수집
        all_components = []

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

            # 베이스 아이템 컴포넌트 로드 (EquipmentItem.config에서)
            if equipment.config:
                components = load_equipment_components(equipment.config)
                all_components.extend(components)

            # 랜덤 특수 효과 컴포넌트 (A등급 이상 인스턴스)
            if eq.inventory_item.special_effects:
                # special_effects를 components 형식으로 변환
                special_config = _convert_effects_to_components(
                    eq.inventory_item.special_effects
                )
                if special_config:
                    components = load_equipment_components(special_config)
                    all_components.extend(components)

        # 컴포넌트에서 스탯 추출
        passive_stats = get_equipment_passive_stats(all_components)

        # 퍼센트 기반 효과 계산
        passive_stats = _apply_percent_bonuses(passive_stats, total_stats)

        # 집계된 특수 효과 스탯을 total_stats에 병합
        for stat_key, value in passive_stats.items():
            total_stats[stat_key] = total_stats.get(stat_key, 0) + int(value)

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


def _convert_effects_to_components(effects: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    legacy effects 형식을 components 형식으로 변환 (special_effects 호환성)

    Args:
        effects: [{"type": "crit_rate", "value": 5}, ...]

    Returns:
        {"components": [{"tag": "passive_buff", "crit_rate": 5, ...}]}
    """
    if not effects:
        return None

    # 효과 집계
    aggregated = {}
    for effect in effects:
        effect_type = effect.get("type", "")
        value = effect.get("value", 0)
        if effect_type:
            aggregated[effect_type] = aggregated.get(effect_type, 0) + value

    if not aggregated:
        return None

    # PassiveBuffComponent config 생성
    component_config = {"tag": "passive_buff"}
    component_config.update(aggregated)

    return {"components": [component_config]}


def _apply_percent_bonuses(
    passive_stats: Dict[str, float],
    base_stats: Dict[str, int]
) -> Dict[str, float]:
    """
    퍼센트 기반 스탯 보너스 계산

    Args:
        passive_stats: 컴포넌트에서 추출한 스탯
        base_stats: 기본 스탯 (퍼센트 계산 기준)

    Returns:
        퍼센트 효과가 적용된 스탯 보너스
    """
    result = dict(passive_stats)

    # HP 퍼센트 보너스
    bonus_hp_pct = result.get("bonus_hp_pct", 0)
    if bonus_hp_pct > 0 and base_stats.get("hp", 0) > 0:
        result["hp"] = result.get("hp", 0) + int(base_stats["hp"] * bonus_hp_pct / 100)
        del result["bonus_hp_pct"]

    # 속도 퍼센트 보너스
    bonus_speed_pct = result.get("bonus_speed_pct", 0)
    if bonus_speed_pct > 0 and base_stats.get("speed", 0) > 0:
        result["speed"] = result.get("speed", 0) + int(base_stats["speed"] * bonus_speed_pct / 100)
        del result["bonus_speed_pct"]

    # 모든 스탯 퍼센트 보너스
    bonus_all_stats_pct = result.get("bonus_all_stats_pct", 0)
    if bonus_all_stats_pct > 0:
        for stat_key in ["hp", "attack", "ap_attack", "ad_defense", "ap_defense", "speed"]:
            if base_stats.get(stat_key, 0) > 0:
                result[stat_key] = (
                    result.get(stat_key, 0) +
                    int(base_stats[stat_key] * bonus_all_stats_pct / 100)
                )
        del result["bonus_all_stats_pct"]

    return result
