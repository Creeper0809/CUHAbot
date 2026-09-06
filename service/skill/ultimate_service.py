"""
궁극기 슬롯/발동 모드 관리 서비스
"""
from __future__ import annotations

from typing import Iterable, Literal

from tortoise.exceptions import OperationalError

from config import ULTIMATE_SKILL_IDS
from models import User, UserStatEnum, UserUltimateDeck
from models.repos.skill_repo import get_skill_by_id
from service.dungeon.status import get_status_stacks

UltimateMode = Literal["manual", "auto"]
DEFAULT_ULTIMATE_MODE: UltimateMode = "manual"
DEFAULT_ULTIMATE_COOLDOWN = 3

ULTIMATE_GAUGE_MAX = 100
ULTIMATE_GAUGE_PER_ACTION = 8
ULTIMATE_GAUGE_DEAL_RATIO = 0.05
ULTIMATE_GAUGE_TAKE_RATIO = 0.08
ULTIMATE_GAUGE_DAMAGE_CAP = 25


def is_ultimate_skill(skill_id: int) -> bool:
    return skill_id in ULTIMATE_SKILL_IDS


def _normalize_mode(mode: str) -> UltimateMode:
    return "auto" if mode == "auto" else "manual"


def _get_ultimate_meta(skill_id: int) -> dict:
    if not skill_id or not is_ultimate_skill(skill_id):
        return {}
    skill = get_skill_by_id(skill_id)
    if not skill:
        return {}
    raw_config = getattr(skill.skill_model, "config", None)
    if not isinstance(raw_config, dict):
        return {}
    meta = raw_config.get("ultimate", {})
    return meta if isinstance(meta, dict) else {}


def _ensure_runtime_fields(user: User) -> None:
    if not hasattr(user, "equipped_ultimate_skill"):
        user.equipped_ultimate_skill = 0
    if not hasattr(user, "ultimate_mode"):
        user.ultimate_mode = "manual"
    if not hasattr(user, "ultimate_gauge"):
        user.ultimate_gauge = 0
    if not hasattr(user, "ultimate_cooldown_remaining"):
        user.ultimate_cooldown_remaining = 0
    if not hasattr(user, "manual_ultimate_requested"):
        user.manual_ultimate_requested = False


async def get_or_create_user_ultimate(user: User) -> UserUltimateDeck | None:
    try:
        setting, _ = await UserUltimateDeck.get_or_create(
            user=user,
            defaults={"skill_id": 0, "mode": "manual"},
        )
        return setting
    except OperationalError:
        return None


async def load_ultimate_to_user(user: User) -> None:
    _ensure_runtime_fields(user)
    setting = await get_or_create_user_ultimate(user)
    if not setting:
        user.equipped_ultimate_skill = 0
        user.ultimate_mode = "manual"
        return

    user.equipped_ultimate_skill = setting.skill_id if is_ultimate_skill(setting.skill_id) else 0
    # 모드는 스킬 고정 정책을 사용한다.
    user.ultimate_mode = get_ultimate_mode_for_skill(user.equipped_ultimate_skill)


async def set_ultimate_skill(user: User, skill_id: int) -> bool:
    if skill_id != 0 and not is_ultimate_skill(skill_id):
        return False

    setting = await get_or_create_user_ultimate(user)
    if not setting:
        return False

    setting.skill_id = skill_id
    await setting.save(update_fields=["skill_id"])
    user.equipped_ultimate_skill = skill_id
    return True


async def set_ultimate_mode(user: User, mode: UltimateMode) -> bool:
    setting = await get_or_create_user_ultimate(user)
    if not setting:
        return False

    normalized = _normalize_mode(mode)
    setting.mode = normalized
    await setting.save(update_fields=["mode"])
    user.ultimate_mode = normalized
    return True


def request_manual_ultimate(user: User) -> None:
    _ensure_runtime_fields(user)
    user.manual_ultimate_requested = True


def reset_ultimate_combat_state(user: User) -> None:
    _ensure_runtime_fields(user)
    user.ultimate_gauge = 0
    user.ultimate_cooldown_remaining = 0
    user.manual_ultimate_requested = False
    user.ultimate_mode = get_ultimate_mode_for_skill(user.equipped_ultimate_skill)


def get_ultimate_mode_for_skill(skill_id: int) -> UltimateMode:
    if not skill_id:
        return DEFAULT_ULTIMATE_MODE
    meta = _get_ultimate_meta(skill_id)
    return _normalize_mode(str(meta.get("mode", DEFAULT_ULTIMATE_MODE)))


def select_skill_for_user_turn(user: User, alive_monsters: Iterable) -> tuple[object | None, str | None, float]:
    """
    유저 턴에 사용할 스킬 선택

    Returns:
        (선택 스킬, 추가 로그, 궁극기 데미지 스케일)
    """
    _ensure_runtime_fields(user)

    ultimate_skill = _get_equipped_ultimate(user)
    if not ultimate_skill:
        return user.next_skill(), None, 1.0
    if is_ultimate_on_cooldown(user):
        return user.next_skill(), None, 1.0

    mode = get_ultimate_mode_for_skill(ultimate_skill.id)
    user.ultimate_mode = mode
    if mode == "manual":
        if user.manual_ultimate_requested and can_cast_ultimate(user):
            user.manual_ultimate_requested = False
            spend_ultimate_gauge(user)
            start_ultimate_cooldown(user, ultimate_skill.id)
            return ultimate_skill, "🔥 수동 궁극기 발동!", 1.0
        return user.next_skill(), None, 1.0

    should_cast, reason = _should_cast_auto_ultimate(ultimate_skill, user, alive_monsters)
    if should_cast:
        user.manual_ultimate_requested = False
        start_ultimate_cooldown(user, ultimate_skill.id)
        return ultimate_skill, f"⚙️ 자동 궁극기 발동 ({reason})", 0.8

    return user.next_skill(), None, 1.0


def _get_equipped_ultimate(user: User):
    skill_id = getattr(user, "equipped_ultimate_skill", 0)
    if not skill_id or not is_ultimate_skill(skill_id):
        return None
    from service.dungeon.skill_augments import apply_session_augments
    return apply_session_augments(user, get_skill_by_id(skill_id))


def _should_cast_auto_ultimate(ultimate_skill, user: User, alive_monsters: Iterable) -> tuple[bool, str]:
    monsters = list(alive_monsters)
    if not monsters:
        return False, "대상 없음"

    skill_id = getattr(ultimate_skill, "id", 0)
    skill_specific = _check_skill_specific_auto_condition(skill_id, user, monsters)
    if skill_specific:
        return True, skill_specific

    # 궁극기 속성/키워드 기반 컨디션
    attr = getattr(ultimate_skill, "attribute", "무속성") or "무속성"
    keyword = (getattr(ultimate_skill.skill_model, "keyword", "") or "")

    if "화염" in attr or "화염" in keyword:
        if any(get_status_stacks(m, "burn") >= 5 for m in monsters):
            return True, "적 화상 5스택"
    if "냉기" in attr or "냉기" in keyword:
        if any(get_status_stacks(m, "freeze") >= 1 or get_status_stacks(m, "slow") >= 1 for m in monsters):
            return True, "적 둔화/빙결"
    if "번개" in attr or "번개" in keyword:
        if any(get_status_stacks(m, "shock") >= 1 or get_status_stacks(m, "paralyze") >= 1 for m in monsters):
            return True, "적 감전/마비"
    if "암흑" in attr or "암흑" in keyword:
        if any(
            get_status_stacks(m, "curse") >= 1
            or get_status_stacks(m, "poison") >= 3
            or get_status_stacks(m, "infection") >= 1
            for m in monsters
        ):
            return True, "적 저주/중독/감염"
    if "수속성" in attr or "수속성" in keyword:
        if any(get_status_stacks(m, "submerge") >= 1 or get_status_stacks(m, "erode") >= 3 for m in monsters):
            return True, "적 침수/잠식"

    # 공통 fallback 조건
    user_stat = user.get_stat()
    my_max_hp = user_stat.get(UserStatEnum.HP, user.hp)
    my_hp_ratio = _safe_hp_ratio(user.now_hp, my_max_hp)
    if my_hp_ratio <= 0.30:
        return True, "자신 HP 30% 이하"

    for monster in monsters:
        hp_ratio = _safe_hp_ratio(monster.now_hp, getattr(monster, "hp", 1))
        if hp_ratio <= 0.35:
            return True, "적 HP 35% 이하"

    return False, "조건 미충족"


def _safe_hp_ratio(now_hp: int, max_hp: int) -> float:
    if max_hp <= 0:
        return 1.0
    return now_hp / max_hp


def _check_skill_specific_auto_condition(skill_id: int, user: User, monsters: list) -> str | None:
    if skill_id == 5004:
        if any(get_status_stacks(m, "burn") >= 5 for m in monsters):
            return "적 화상 5스택"
    elif skill_id == 5003:
        if any(get_status_stacks(m, "freeze") >= 1 or get_status_stacks(m, "slow") >= 1 for m in monsters):
            return "적 둔화/빙결"
    elif skill_id == 5008:
        if any(get_status_stacks(m, "shock") >= 1 or get_status_stacks(m, "paralyze") >= 1 for m in monsters):
            return "적 감전/마비"
    elif skill_id == 5007:
        if any(get_status_stacks(m, "submerge") >= 1 or get_status_stacks(m, "erode") >= 3 for m in monsters):
            return "적 침수/잠식"
    elif skill_id in (5001, 5002):
        if any(_safe_hp_ratio(m.now_hp, getattr(m, "hp", 1)) <= 0.35 for m in monsters):
            return "적 HP 35% 이하"
    elif skill_id in (5005, 5006):
        user_stat = user.get_stat()
        my_max_hp = user_stat.get(UserStatEnum.HP, user.hp)
        if _safe_hp_ratio(user.now_hp, my_max_hp) <= 0.30:
            return "자신 HP 30% 이하"
    return None


def add_ultimate_gauge(user: User, dealt_damage: int = 0, taken_damage: int = 0, acted: bool = False) -> int:
    _ensure_runtime_fields(user)
    # 게이지는 수동형 궁극기에서만 사용
    skill_id = getattr(user, "equipped_ultimate_skill", 0)
    if get_ultimate_mode_for_skill(skill_id) != "manual":
        return user.ultimate_gauge

    gain = 0
    if acted:
        gain += ULTIMATE_GAUGE_PER_ACTION
    if dealt_damage > 0:
        gain += min(int(dealt_damage * ULTIMATE_GAUGE_DEAL_RATIO), ULTIMATE_GAUGE_DAMAGE_CAP)
    if taken_damage > 0:
        gain += min(int(taken_damage * ULTIMATE_GAUGE_TAKE_RATIO), ULTIMATE_GAUGE_DAMAGE_CAP)
    if gain <= 0:
        return user.ultimate_gauge

    user.ultimate_gauge = min(ULTIMATE_GAUGE_MAX, user.ultimate_gauge + gain)
    return user.ultimate_gauge


def can_cast_ultimate(user: User) -> bool:
    _ensure_runtime_fields(user)
    return user.ultimate_gauge >= ULTIMATE_GAUGE_MAX


def spend_ultimate_gauge(user: User) -> None:
    _ensure_runtime_fields(user)
    user.ultimate_gauge = max(0, user.ultimate_gauge - ULTIMATE_GAUGE_MAX)


def get_ultimate_cooldown(skill_id: int) -> int:
    if not skill_id:
        return 0
    meta = _get_ultimate_meta(skill_id)
    raw_value = meta.get("cooldown", DEFAULT_ULTIMATE_COOLDOWN)
    try:
        cooldown = int(raw_value)
    except (TypeError, ValueError):
        cooldown = DEFAULT_ULTIMATE_COOLDOWN
    return max(0, cooldown)


def start_ultimate_cooldown(user: User, skill_id: int) -> None:
    _ensure_runtime_fields(user)
    from service.dungeon.skill_augments import ultimate_cooldown_reduction
    from service.dungeon.equipment_skill_modifier import get_equipment_cooldown_multiplier_sync
    equipment_multiplier = get_equipment_cooldown_multiplier_sync(user)
    user.ultimate_cooldown_remaining = max(
        0,
        round(get_ultimate_cooldown(skill_id) * equipment_multiplier)
        - ultimate_cooldown_reduction(user, skill_id),
    )


def tick_ultimate_cooldown(user: User) -> int:
    _ensure_runtime_fields(user)
    if user.ultimate_cooldown_remaining > 0:
        user.ultimate_cooldown_remaining -= 1
    return user.ultimate_cooldown_remaining


def is_ultimate_on_cooldown(user: User) -> bool:
    _ensure_runtime_fields(user)
    return user.ultimate_cooldown_remaining > 0
