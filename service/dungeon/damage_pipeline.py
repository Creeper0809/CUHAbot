"""
데미지 파이프라인 - 면역/저항/보호막/반사 처리

모든 데미지는 이 파이프라인을 통해 처리됩니다.
기존 take_damage()는 변경하지 않고, 래퍼 함수로 확장합니다.
"""
import logging
from dataclasses import dataclass, field

from config.attributes import ATTRIBUTE

logger = logging.getLogger(__name__)


@dataclass
class DamageEvent:
    """데미지 처리 결과"""
    raw_damage: int = 0
    actual_damage: int = 0
    absorbed_by_shield: int = 0
    reflected_damage: int = 0
    was_immune: bool = False
    attribute: str = "무속성"
    extra_logs: list[str] = field(default_factory=list)


def process_incoming_damage(
    target,
    damage: int,
    attacker=None,
    attribute: str = "무속성",
    is_reflected: bool = False,
) -> DamageEvent:
    """
    데미지 파이프라인 메인 함수

    처리 순서:
    1. 속성 면역 체크
    2. 속성 저항 적용 (MAX_RESISTANCE 캡)
    3. 보호막 흡수
    4. HP 데미지 적용
    5. 반사 데미지 계산 (is_reflected=True면 스킵)

    Args:
        target: 데미지를 받는 엔티티
        damage: 원본 데미지
        attacker: 공격자 (반사용)
        attribute: 데미지 속성
        is_reflected: 반사 데미지 여부 (무한루프 방지)

    Returns:
        DamageEvent 처리 결과
    """
    event = DamageEvent(raw_damage=damage, attribute=attribute)

    if damage <= 0:
        return event

    remaining = damage

    # 1. 무적 체크
    if _has_invulnerability(target):
        event.was_immune = True
        event.extra_logs.append(f"🛡️ **{target.get_name()}** 무적! 데미지 무효화")
        return event

    # 2. 속성 면역 체크
    immunities = get_passive_immunities(target)
    if attribute in immunities:
        event.was_immune = True
        event.extra_logs.append(f"🛡️ **{target.get_name()}** {attribute} 면역!")
        return event

    # 3. 속성 저항 적용
    resistances = get_passive_resistances(target)
    resist_pct = resistances.get(attribute, 0.0)
    if resist_pct > 0:
        resist_pct = min(resist_pct, ATTRIBUTE.MAX_RESISTANCE)
        reduction = int(remaining * resist_pct)
        remaining -= reduction
        remaining = max(remaining, 1)
        event.extra_logs.append(
            f"🛡️ **{target.get_name()}** {attribute} 저항 {int(resist_pct * 100)}% (-{reduction})"
        )

    # 4. 보호막 흡수
    absorbed = _apply_shield_absorption(target, remaining)
    if absorbed > 0:
        remaining -= absorbed
        event.absorbed_by_shield = absorbed
        event.extra_logs.append(
            f"🛡️ **{target.get_name()}** 보호막 -{absorbed} 흡수"
        )

    # 5. HP 데미지 적용
    remaining = max(remaining, 0)
    event.actual_damage = target.take_damage(remaining)

    # 6. 반사 데미지 계산 (반사 데미지는 다시 반사하지 않음)
    if not is_reflected and event.actual_damage > 0:
        reflect_pct = get_passive_reflection(target)
        if reflect_pct > 0:
            event.reflected_damage = max(1, int(event.actual_damage * reflect_pct))

    return event


# =============================================================================
# 헬퍼 함수
# =============================================================================


def get_passive_immunities(entity) -> set[str]:
    """엔티티의 속성 면역 목록 반환"""
    from models.repos.skill_repo import get_skill_by_id

    immunities: set[str] = set()
    skill_ids = _get_skill_ids(entity)

    for sid in skill_ids:
        if sid == 0:
            continue
        skill = get_skill_by_id(sid)
        if not skill or not skill.is_passive:
            continue
        for comp in skill.components:
            if getattr(comp, '_tag', '') == 'passive_element_immunity':
                for attr in getattr(comp, 'immune_to', []):
                    immunities.add(attr)

    return immunities


def get_passive_resistances(entity) -> dict[str, float]:
    """엔티티의 속성 저항 반환 {속성: 비율}"""
    from models.repos.skill_repo import get_skill_by_id

    resistances: dict[str, float] = {}
    skill_ids = _get_skill_ids(entity)

    for sid in skill_ids:
        if sid == 0:
            continue
        skill = get_skill_by_id(sid)
        if not skill or not skill.is_passive:
            continue
        for comp in skill.components:
            if getattr(comp, '_tag', '') == 'passive_element_resistance':
                resist_type = getattr(comp, 'resist_type', '')
                resist_pct = getattr(comp, 'resist_percent', 0.0)
                if resist_type:
                    resistances[resist_type] = resistances.get(resist_type, 0.0) + resist_pct

    return resistances


def get_passive_reflection(entity) -> float:
    """엔티티의 반사 비율 합계 반환"""
    from models.repos.skill_repo import get_skill_by_id

    total = 0.0
    skill_ids = _get_skill_ids(entity)

    for sid in skill_ids:
        if sid == 0:
            continue
        skill = get_skill_by_id(sid)
        if not skill or not skill.is_passive:
            continue
        for comp in skill.components:
            if getattr(comp, '_tag', '') == 'passive_damage_reflection':
                total += getattr(comp, 'reflect_percent', 0.0)

    return total


def get_status_immunities(entity) -> dict:
    """엔티티의 상태이상 면역 정보 반환"""
    from models.repos.skill_repo import get_skill_by_id

    result = {"all": False, "types": set()}
    skill_ids = _get_skill_ids(entity)

    for sid in skill_ids:
        if sid == 0:
            continue
        skill = get_skill_by_id(sid)
        if not skill or not skill.is_passive:
            continue
        for comp in skill.components:
            if getattr(comp, '_tag', '') == 'passive_status_immunity':
                if getattr(comp, 'immune_all', False):
                    result["all"] = True
                for t in getattr(comp, 'immune_types', []):
                    result["types"].add(t)

    return result


def get_debuff_reduction(entity) -> float:
    """엔티티의 디버프 지속시간 감소 비율 반환"""
    from models.repos.skill_repo import get_skill_by_id

    total = 0.0
    skill_ids = _get_skill_ids(entity)

    for sid in skill_ids:
        if sid == 0:
            continue
        skill = get_skill_by_id(sid)
        if not skill or not skill.is_passive:
            continue
        for comp in skill.components:
            if getattr(comp, '_tag', '') == 'passive_debuff_reduction':
                total += getattr(comp, 'reduction_percent', 0.0)

    return min(total, 0.9)


# =============================================================================
# 내부 헬퍼
# =============================================================================


def _get_skill_ids(entity) -> list[int]:
    """엔티티의 스킬 ID 목록 반환"""
    return getattr(entity, 'equipped_skill', None) or getattr(entity, 'use_skill', [])


def _has_invulnerability(entity) -> bool:
    """무적 버프 보유 여부"""
    for status in getattr(entity, 'status', []):
        if getattr(status, 'buff_type', '') == 'invulnerability':
            return True
    return False


def _apply_shield_absorption(target, damage: int) -> int:
    """보호막으로 데미지 흡수, 흡수량 반환"""
    from service.dungeon.status.stat_buffs import ShieldBuff

    total_absorbed = 0
    for status in target.status[:]:
        if not isinstance(status, ShieldBuff):
            continue
        if damage <= 0:
            break

        remaining, absorbed = status.absorb_damage(damage)
        total_absorbed += absorbed
        damage = remaining

        if status.shield_hp <= 0:
            target.status.remove(status)

    return total_absorbed
