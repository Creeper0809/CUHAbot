"""
장비 스킬 데미지 모디파이어 시스템

장비의 스킬 데미지 강화 효과를 수집하고 적용합니다.
"""
from typing import List, Optional


def _component_damage_multiplier(comp, skill=None, target=None, attacker=None) -> float:
    """Resolve one equipment component's executable outgoing-damage effect."""
    tag = getattr(comp, '_tag', '')
    if tag == "skill_damage_boost":
        return comp.get_skill_damage_multiplier()
    if tag in {"skill_type_damage_boost", "attribute_damage_boost"}:
        return comp.get_skill_damage_multiplier(skill)
    if tag == "conditional_damage_boost" and target is not None:
        return comp.get_conditional_damage_multiplier(target)
    if tag == "race_bonus" and target is not None:
        return comp.get_race_bonus_multiplier(target)
    if tag == "random_damage_variance":
        return comp.get_damage_variance_multiplier()
    if tag == "random_attribute":
        attribute = str(
            getattr(skill, "attribute", getattr(skill, "skill_attribute", "")) or ""
        )
        return comp.get_attribute_damage_multiplier(attribute)
    if tag in {"combat_stat_growth", "on_kill_stack"}:
        bonus = comp.get_stat_bonus()
        return 1.0 + max(
            float(bonus.get("attack", 0.0)),
            float(bonus.get("ap_attack", 0.0)),
        )
    if tag == "conditional_stat_bonus" and attacker is not None:
        # This component's condition is based on the wearer, not the enemy.
        stat = str(getattr(comp, "stat", ""))
        if stat in {"attack", "ap_attack", "all", "all_stats"}:
            return comp.get_conditional_stat_multiplier(attacker)
    return 1.0


def _multiply_components(components, skill=None, target=None, attacker=None) -> float:
    total = 1.0
    for component in components:
        total *= _component_damage_multiplier(component, skill, target, attacker)
    # A corrupted legacy item must not turn one action into an unbounded value.
    return max(0.10, min(total, 4.0))


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
            if not equipment:
                continue

            # 컴포넌트 로드
            components = load_equipment_components(equipment.config) if equipment.config else []
            from service.item.affix_service import get_affix_components
            components.extend(await get_affix_components(eq.inventory_item))

            total_multiplier *= _multiply_components(components, skill, target, attacker)

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
            if not equipment:
                continue

            components = load_equipment_components(equipment.config) if equipment.config else []
            from service.item.affix_service import get_affix_components
            components.extend(await get_affix_components(eq.inventory_item))
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

    return _multiply_components(components, skill, target, attacker)


def get_equipment_cooldown_multiplier_sync(attacker) -> float:
    """Return the capped combined ultimate-cooldown multiplier."""
    multiplier = 1.0
    for component in get_equipment_components_sync(attacker):
        if getattr(component, '_tag', '') == 'cooldown_reduction':
            multiplier *= component.get_cooldown_multiplier()
    return max(0.50, multiplier)


def get_equipment_buff_duration_multiplier_sync(attacker) -> float:
    """Return combined duration multiplier for beneficial statuses."""
    multiplier = 1.0
    for component in get_equipment_components_sync(attacker):
        if getattr(component, '_tag', '') == 'buff_duration_extension':
            multiplier *= component.get_duration_multiplier(is_buff=True)
    return min(2.0, max(1.0, multiplier))
