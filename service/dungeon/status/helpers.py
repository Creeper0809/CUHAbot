"""
상태이상 헬퍼 함수

엔티티에 상태이상을 적용/제거/조회하는 유틸리티 함수들입니다.
"""
import logging
from typing import Optional

from config import STATUS_EFFECT
from service.dungeon.status.base import (
    Buff, StatusEffect,
    status_effect_register, get_status_effect_by_type,
)

logger = logging.getLogger(__name__)


def apply_status_effect(
    entity,
    effect_type: str,
    stacks: int = 1,
    duration: int = 0,
) -> str:
    """
    엔티티에 상태이상 적용 (기존 효과가 있으면 스택/지속시간 갱신)

    Args:
        entity: 대상 엔티티 (User 또는 Monster)
        effect_type: 상태이상 타입
        stacks: 적용할 스택 수
        duration: 지속 턴 수 (0이면 기본값 사용)

    Returns:
        적용 결과 로그 문자열
    """
    if effect_type not in status_effect_register:
        logger.warning(f"Unknown status effect type: {effect_type}")
        return ""

    existing = _find_status_effect(entity, effect_type)
    if existing:
        existing.add_stacks(stacks)
        if duration > 0:
            existing.duration = max(existing.duration, duration)
        emoji = existing.get_emoji()
        stack_text = f" x{existing.stacks}" if existing.stacks > 1 else ""
        return f"{emoji} **{entity.get_name()}** {effect_type}{stack_text}!"

    effect = get_status_effect_by_type(effect_type)
    effect.stacks = min(stacks, effect.max_stacks)
    effect.duration = duration if duration > 0 else _get_default_duration(effect_type)

    entity.status.append(effect)
    emoji = effect.get_emoji()
    stack_text = f" x{effect.stacks}" if effect.stacks > 1 else ""
    return f"{emoji} **{entity.get_name()}** {effect_type}{stack_text} ({effect.duration}턴)!"


def remove_status_effects(
    entity,
    count: int = 1,
    filter_debuff: bool = True,
    filter_type: Optional[str] = None,
) -> str:
    """
    상태이상 제거

    Args:
        entity: 대상 엔티티
        count: 제거할 수 (99 = 모두)
        filter_debuff: True면 디버프만 제거
        filter_type: 특정 타입만 제거

    Returns:
        제거 결과 로그 문자열
    """
    removed = []
    remaining = []

    for status in entity.status:
        if not isinstance(status, StatusEffect):
            remaining.append(status)
            continue

        should_remove = False
        if filter_type and status.effect_type == filter_type:
            should_remove = True
        elif filter_debuff and status.is_debuff and not filter_type:
            should_remove = True

        if should_remove and len(removed) < count:
            removed.append(status)
        else:
            remaining.append(status)

    entity.status = remaining

    if not removed:
        return ""

    names = ", ".join(r.effect_type for r in removed)
    return f"✨ **{entity.get_name()}** {names} 해제!"


def process_status_ticks(entity) -> list[str]:
    """모든 상태이상 tick 처리 (DOT 데미지 등)"""
    logs = []
    for status in entity.status:
        if isinstance(status, StatusEffect):
            log = status.tick(entity)
            if log:
                logs.append(log)
    return logs


def has_status_effect(entity, effect_type: str) -> bool:
    """특정 상태이상 보유 여부"""
    return _find_status_effect(entity, effect_type) is not None


def get_status_stacks(entity, effect_type: str) -> int:
    """특정 상태이상의 현재 스택 수"""
    effect = _find_status_effect(entity, effect_type)
    return effect.stacks if effect else 0


def can_entity_act(entity) -> bool:
    """CC로 인한 행동불가 확인"""
    for status in entity.status:
        if isinstance(status, StatusEffect) and not status.can_act():
            return False
    return True


def get_cc_effect_name(entity) -> str:
    """행동불가 상태의 이름 반환"""
    for status in entity.status:
        if isinstance(status, StatusEffect) and not status.can_act():
            return status.effect_type
    return ""


def decay_all_durations(entity) -> list[str]:
    """모든 버프/상태이상 지속시간 감소 + 만료 제거"""
    logs = []
    remaining = []

    for buff in entity.status:
        buff.decrement_duration()
        if buff.is_expired():
            emoji = buff.get_emoji()
            if isinstance(buff, StatusEffect):
                logs.append(f"{emoji} **{entity.get_name()}** {buff.effect_type} 해제")
            else:
                logs.append(f"{emoji} **{entity.get_name()}** 버프 만료")
        else:
            remaining.append(buff)

    entity.status = remaining
    return logs


def get_damage_taken_multiplier(entity) -> float:
    """받는 피해 배율 계산 (동결, 표식 등)"""
    from service.dungeon.status.cc_effects import FreezeEffect
    from service.dungeon.status.debuff_effects import MarkEffect

    multiplier = 1.0
    for status in entity.status:
        if isinstance(status, FreezeEffect):
            multiplier *= (1.0 + STATUS_EFFECT.FREEZE_DAMAGE_INCREASE)
        elif isinstance(status, MarkEffect):
            multiplier *= 1.2
    return multiplier


def has_curse_effect(entity) -> bool:
    """저주 효과 보유 여부 (회복량 감소용)"""
    return has_status_effect(entity, "curse")


def get_status_icons(entity) -> str:
    """상태이상 아이콘 문자열 반환"""
    icons = []
    for status in entity.status:
        if isinstance(status, StatusEffect):
            icon = status.get_emoji()
            if status.stacks > 1:
                icon += f"×{status.stacks}"
            icons.append(icon)
        elif isinstance(status, Buff) and not isinstance(status, StatusEffect):
            icons.append(status.get_emoji())
    return " ".join(icons)


# =============================================================================
# 내부 헬퍼
# =============================================================================


def _find_status_effect(entity, effect_type: str) -> Optional[StatusEffect]:
    """엔티티에서 특정 상태이상 찾기"""
    for status in entity.status:
        if isinstance(status, StatusEffect) and status.effect_type == effect_type:
            return status
    return None


def _get_default_duration(effect_type: str) -> int:
    """상태이상 기본 지속 턴"""
    defaults = {
        "burn": STATUS_EFFECT.BURN_DEFAULT_DURATION,
        "poison": STATUS_EFFECT.POISON_DEFAULT_DURATION,
        "bleed": STATUS_EFFECT.BLEED_DEFAULT_DURATION,
        "slow": STATUS_EFFECT.SLOW_DEFAULT_DURATION,
        "freeze": STATUS_EFFECT.FREEZE_DEFAULT_DURATION,
        "stun": 1,
        "paralyze": 1,
        "curse": 3,
        "mark": 5,
        "erode": 3,
        "submerge": 3,
        "shock": 2,
        "infection": 3,
        "combo": 5,
    }
    return defaults.get(effect_type, 3)
