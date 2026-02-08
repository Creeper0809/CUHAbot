"""
스탯 시너지 전투 효과 서비스

스탯 시너지의 특수효과(special)를 전투 시스템에서 조회하는 함수를 제공합니다.
유저 객체에 캐싱하여 매 턴 재계산을 방지합니다.
"""
import random
from typing import Any, Dict, List

from config.stat_synergies import ALL_SYNERGIES, Synergy


_CACHE_ATTR = "_synergy_specials_cache"


def _get_active_specials(user) -> List[Dict[str, Any]]:
    """
    유저의 활성 시너지 special 목록 반환 (캐싱)

    Args:
        user: User 객체 (bonus_str/int/dex/vit/luk 필요)

    Returns:
        활성 시너지의 special dict 리스트 (빈 dict 제외)
    """
    # 몬스터 등 User가 아닌 엔티티는 시너지 없음
    if not hasattr(user, 'bonus_str'):
        return []

    cached = getattr(user, _CACHE_ATTR, None)
    if cached is not None:
        return cached

    specials = []
    for synergy in ALL_SYNERGIES:
        if not synergy.effect.special:
            continue
        if synergy.condition.is_met(
            user.bonus_str, user.bonus_int, user.bonus_dex,
            user.bonus_vit, user.bonus_luk
        ):
            specials.append(synergy.effect.special)

    try:
        setattr(user, _CACHE_ATTR, specials)
    except AttributeError:
        pass

    return specials


def clear_cache(user) -> None:
    """유저의 시너지 캐시 초기화 (스탯 변경 시 호출)"""
    try:
        delattr(user, _CACHE_ATTR)
    except AttributeError:
        pass


# =========================================================================
# 전투 특수효과 조회 함수
# =========================================================================


def has_first_strike(user) -> bool:
    """선공 확정 시너지 보유 여부"""
    for sp in _get_active_specials(user):
        if sp.get("first_strike"):
            return True
    return False


def get_extra_action_chance(user) -> float:
    """추가 행동 확률 반환 (0.0 ~ 1.0)"""
    total = 0.0
    for sp in _get_active_specials(user):
        total += sp.get("extra_action_pct", 0)
    return total / 100.0


def roll_extra_action(user) -> bool:
    """추가 행동 판정"""
    chance = get_extra_action_chance(user)
    if chance <= 0:
        return False
    return random.random() < chance


def get_hp_regen_per_turn_pct(user) -> float:
    """턴당 HP 자동 회복률 (%) 반환"""
    total = 0.0
    for sp in _get_active_specials(user):
        total += sp.get("hp_regen_per_turn_pct", 0)
    return total


def get_heal_bonus_pct(user) -> float:
    """회복량 보너스 (%) 반환"""
    total = 0.0
    for sp in _get_active_specials(user):
        total += sp.get("heal_bonus_pct", 0)
    return total


def get_status_resist_pct(user) -> float:
    """상태이상 저항 확률 (%) 반환"""
    total = 0.0
    for sp in _get_active_specials(user):
        total += sp.get("status_resist_pct", 0)
    return total


def get_buff_duration_bonus(user) -> int:
    """버프 지속시간 추가 턴 수 반환"""
    total = 0
    for sp in _get_active_specials(user):
        total += sp.get("buff_duration_bonus", 0)
    return total


def get_drop_rate_multiplier(user) -> float:
    """드롭률 배수 반환 (기본 1.0)"""
    mult = 1.0
    for sp in _get_active_specials(user):
        drop_mult = sp.get("drop_rate_mult", 0)
        if drop_mult > 0:
            mult *= drop_mult
    return mult


def get_phys_crit_dmg_bonus(user) -> float:
    """물리 치명타 추가 데미지 배율 반환 (0.0 기반, 예: 0.25 = +25%)"""
    total = 0.0
    for sp in _get_active_specials(user):
        total += sp.get("phys_crit_dmg_bonus_pct", 0)
    return total / 100.0


def get_attr_dmg_bonus(user) -> float:
    """속성 데미지 보너스 배율 반환 (0.0 기반, 예: 0.1 = +10%)"""
    total = 0.0
    for sp in _get_active_specials(user):
        total += sp.get("attr_dmg_bonus_pct", 0)
    return total / 100.0


def get_hp_conditional_bonuses(user) -> Dict[str, float]:
    """
    HP 조건부 보너스를 현재 HP 비율에 따라 계산

    Args:
        user: User 객체 (now_hp, get_stat() 필요)

    Returns:
        활성화된 보너스 dict (phys_dmg_pct, lifesteal_pct, def_mult 등)
    """
    from models import UserStatEnum

    max_hp = user.get_stat().get(UserStatEnum.HP, user.hp)
    if max_hp <= 0:
        return {}

    hp_ratio = user.now_hp / max_hp * 100

    bonuses: Dict[str, float] = {}
    for sp in _get_active_specials(user):
        conditions = sp.get("hp_conditional", [])
        for cond in conditions:
            threshold = cond.get("hp_below_pct", 0)
            if hp_ratio > threshold:
                continue
            for key, value in cond.items():
                if key == "hp_below_pct":
                    continue
                bonuses[key] = bonuses.get(key, 0) + value

    return bonuses
