"""
장비 스킬 데미지 모디파이어 시스템

장비의 스킬 데미지 강화 효과를 수집하고 적용합니다.
"""
from typing import List, Optional


async def get_equipment_skill_damage_multiplier(attacker, skill=None, target=None) -> float:
    """
    장비에서 스킬 데미지 배율 수집

    Args:
        attacker: 공격자 엔티티 (User 또는 Monster)
        skill: 현재 사용 중인 스킬 객체 (선택)
        target: 공격 대상 엔티티 (선택, conditional 효과용)

    Returns:
        총 스킬 데미지 배율 (1.0 = 기본, 1.5 = 50% 증가)
    """
    # 몬스터는 장비 미착용
    from models.users import User as UserClass
    if not isinstance(attacker, UserClass):
        return 1.0

    # 장비 미착용 시
    if not hasattr(attacker, 'discord_id'):
        return 1.0

    try:
        from models.user_equipment import UserEquipment
        from models.equipment_item import EquipmentItem
        from service.item.equipment_component_loader import load_equipment_components

        # 장착 장비 조회
        equipped = await UserEquipment.filter(user=attacker).prefetch_related(
            "inventory_item__item"
        )

        total_multiplier = 1.0

        for eq in equipped:
            equipment = await EquipmentItem.get_or_none(
                item=eq.inventory_item.item
            )
            if not equipment or not equipment.config:
                continue

            # 컴포넌트 로드
            components = load_equipment_components(equipment.config)

            # 각 컴포넌트에서 스킬 데미지 배율 수집
            for comp in components:
                tag = getattr(comp, '_tag', '')

                # 일반 스킬 데미지 증폭
                if tag == "skill_damage_boost":
                    mult = comp.get_skill_damage_multiplier()
                    total_multiplier *= mult

                # 특정 타입 스킬 데미지 증폭
                elif tag == "skill_type_damage_boost":
                    mult = comp.get_skill_damage_multiplier(skill)
                    total_multiplier *= mult

                # 속성 스킬 데미지 증폭
                elif tag == "attribute_damage_boost":
                    mult = comp.get_skill_damage_multiplier(skill)
                    total_multiplier *= mult

                # 조건부 스킬 데미지 증폭
                elif tag == "conditional_damage_boost" and target:
                    mult = comp.get_conditional_damage_multiplier(target)
                    total_multiplier *= mult

        return total_multiplier

    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error getting equipment skill damage multiplier: {e}", exc_info=True)
        return 1.0


def get_equipment_components_sync(attacker) -> List:
    """
    장비 컴포넌트 동기 수집 (전투 중 캐싱용)

    Note: 비동기 DB 쿼리가 불가능한 경우 사용
    전투 시작 시 미리 컴포넌트를 캐싱하는 것을 권장합니다.

    Args:
        attacker: 공격자 엔티티

    Returns:
        컴포넌트 리스트
    """
    # 런타임 캐시에서 가져오기
    if hasattr(attacker, '_equipment_components_cache'):
        return attacker._equipment_components_cache

    return []


async def cache_equipment_components(attacker):
    """
    전투 시작 시 장비 컴포넌트를 미리 캐싱

    Args:
        attacker: 공격자 엔티티 (User)
    """
    from models.users import User as UserClass
    if not isinstance(attacker, UserClass):
        return

    try:
        from models.user_equipment import UserEquipment
        from models.equipment_item import EquipmentItem
        from service.item.equipment_component_loader import load_equipment_components

        equipped = await UserEquipment.filter(user=attacker).prefetch_related(
            "inventory_item__item"
        )

        all_components = []

        for eq in equipped:
            equipment = await EquipmentItem.get_or_none(
                item=eq.inventory_item.item
            )
            if not equipment or not equipment.config:
                continue

            components = load_equipment_components(equipment.config)
            all_components.extend(components)

        # 런타임 캐시에 저장
        attacker._equipment_components_cache = all_components

    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error caching equipment components: {e}", exc_info=True)
        attacker._equipment_components_cache = []


def get_equipment_skill_damage_multiplier_sync(attacker, skill=None, target=None) -> float:
    """
    장비 스킬 데미지 배율 동기 수집 (캐시 사용)

    Args:
        attacker: 공격자 엔티티
        skill: 현재 사용 중인 스킬 객체
        target: 공격 대상 엔티티

    Returns:
        총 스킬 데미지 배율
    """
    components = get_equipment_components_sync(attacker)
    if not components:
        return 1.0

    total_multiplier = 1.0

    for comp in components:
        tag = getattr(comp, '_tag', '')

        # 일반 스킬 데미지 증폭
        if tag == "skill_damage_boost":
            if hasattr(comp, 'get_skill_damage_multiplier'):
                mult = comp.get_skill_damage_multiplier()
                total_multiplier *= mult

        # 특정 타입 스킬 데미지 증폭
        elif tag == "skill_type_damage_boost":
            if hasattr(comp, 'get_skill_damage_multiplier'):
                mult = comp.get_skill_damage_multiplier(skill)
                total_multiplier *= mult

        # 속성 스킬 데미지 증폭
        elif tag == "attribute_damage_boost":
            if hasattr(comp, 'get_skill_damage_multiplier'):
                mult = comp.get_skill_damage_multiplier(skill)
                total_multiplier *= mult

        # 조건부 스킬 데미지 증폭
        elif tag == "conditional_damage_boost" and target:
            if hasattr(comp, 'get_conditional_damage_multiplier'):
                mult = comp.get_conditional_damage_multiplier(target)
                total_multiplier *= mult

    return total_multiplier
