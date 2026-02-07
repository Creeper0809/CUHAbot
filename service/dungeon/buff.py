"""
버프/디버프/상태이상 시스템

전투 중 엔티티에 적용되는 모든 효과를 관리합니다.
- Buff: 스탯 버프 (공격력, 방어력, 속도 등)
- StatusEffect: 상태이상 (화상, 독, 동결, 기절 등)

사용법:
    from service.dungeon.buff import apply_status_effect, can_entity_act, process_status_ticks
"""
import logging
from typing import Optional

from config import STATUS_EFFECT
from models import UserStatEnum
from service.dungeon.turn_config import TurnConfig

logger = logging.getLogger(__name__)

# =============================================================================
# 버프 등록 시스템
# =============================================================================

buff_register: dict[str, type] = {}
status_effect_register: dict[str, type] = {}


def register_buff_with_tag(tag: str):
    def decorator(cls):
        buff_register[tag] = cls
        return cls
    return decorator


def register_status_effect(effect_type: str):
    def decorator(cls):
        status_effect_register[effect_type] = cls
        return cls
    return decorator


def get_buff_by_tag(tag: str) -> "Buff":
    return buff_register[tag]()


def get_status_effect_by_type(effect_type: str) -> "StatusEffect":
    return status_effect_register[effect_type]()


# =============================================================================
# Buff 기본 클래스
# =============================================================================


class Buff(TurnConfig):
    """버프/디버프 기본 클래스"""

    def __init__(self):
        self.amount: int = 0
        self.duration: int = 0
        self.buff_type: str = ""
        self.is_debuff: bool = False

    def apply_config(self, config: dict) -> None:
        self.amount = config.get("amount", 0)
        self.duration = config.get("duration", 0)

    def apply_stat(self, stats: dict) -> None:
        """스탯 딕셔너리에 버프 효과 적용"""
        pass

    def tick(self, entity) -> str:
        """매 턴 효과 처리 (DOT 등). 로그 반환."""
        return ""

    def is_expired(self) -> bool:
        return self.duration <= 0

    def decrement_duration(self) -> None:
        self.duration -= 1

    def get_description(self) -> str:
        return "버프"

    def get_emoji(self) -> str:
        return "✨"


# =============================================================================
# 스탯 버프 클래스들
# =============================================================================


@register_buff_with_tag("attack")
class AttackBuff(Buff):
    def __init__(self):
        super().__init__()
        self.buff_type = "attack"

    def apply_stat(self, stats: dict) -> None:
        stats[UserStatEnum.ATTACK] += self.amount

    def get_description(self) -> str:
        sign = "+" if self.amount > 0 else ""
        return f"⚔️ 공격력 {sign}{self.amount} ({self.duration}턴)"

    def get_emoji(self) -> str:
        return "⚔️"


@register_buff_with_tag("defense")
class DefenseBuff(Buff):
    def __init__(self):
        super().__init__()
        self.buff_type = "defense"

    def apply_stat(self, stats: dict) -> None:
        stats[UserStatEnum.DEFENSE] += self.amount

    def get_description(self) -> str:
        sign = "+" if self.amount > 0 else ""
        return f"🛡️ 방어력 {sign}{self.amount} ({self.duration}턴)"

    def get_emoji(self) -> str:
        return "🛡️"


@register_buff_with_tag("speed")
class SpeedBuff(Buff):
    def __init__(self):
        super().__init__()
        self.buff_type = "speed"

    def apply_stat(self, stats: dict) -> None:
        stats[UserStatEnum.SPEED] += self.amount

    def get_description(self) -> str:
        sign = "+" if self.amount > 0 else ""
        return f"💨 속도 {sign}{self.amount} ({self.duration}턴)"

    def get_emoji(self) -> str:
        return "💨"


@register_buff_with_tag("ap_attack")
class ApAttackBuff(Buff):
    def __init__(self):
        super().__init__()
        self.buff_type = "ap_attack"

    def apply_stat(self, stats: dict) -> None:
        stats[UserStatEnum.AP_ATTACK] += self.amount

    def get_description(self) -> str:
        sign = "+" if self.amount > 0 else ""
        return f"🔮 마공 {sign}{self.amount} ({self.duration}턴)"

    def get_emoji(self) -> str:
        return "🔮"


@register_buff_with_tag("ap_defense")
class ApDefenseBuff(Buff):
    def __init__(self):
        super().__init__()
        self.buff_type = "ap_defense"

    def apply_stat(self, stats: dict) -> None:
        stats[UserStatEnum.AP_DEFENSE] += self.amount

    def get_description(self) -> str:
        sign = "+" if self.amount > 0 else ""
        return f"🌀 마방 {sign}{self.amount} ({self.duration}턴)"

    def get_emoji(self) -> str:
        return "🌀"


# =============================================================================
# 보호막 (Shield)
# =============================================================================


@register_buff_with_tag("shield")
class ShieldBuff(Buff):
    """보호막: 데미지를 흡수"""

    def __init__(self):
        super().__init__()
        self.buff_type = "shield"
        self.shield_hp: int = 0

    def apply_config(self, config: dict) -> None:
        super().apply_config(config)
        self.shield_hp = config.get("shield_hp", 0)

    def absorb_damage(self, damage: int) -> tuple[int, int]:
        """
        보호막으로 데미지 흡수

        Returns:
            (실제 피해, 흡수된 피해)
        """
        absorbed = min(damage, self.shield_hp)
        self.shield_hp -= absorbed
        remaining = damage - absorbed
        if self.shield_hp <= 0:
            self.duration = 0
        return remaining, absorbed

    def get_description(self) -> str:
        return f"🛡️ 보호막 {self.shield_hp} ({self.duration}턴)"

    def get_emoji(self) -> str:
        return "🛡️"


# =============================================================================
# StatusEffect 기본 클래스
# =============================================================================


class StatusEffect(Buff):
    """상태이상 기본 클래스"""

    def __init__(self):
        super().__init__()
        self.effect_type: str = ""
        self.stacks: int = 1
        self.max_stacks: int = 99
        self.is_debuff = True

    def can_act(self) -> bool:
        """행동 가능 여부 (CC 체크)"""
        return True

    def add_stacks(self, count: int) -> None:
        """스택 추가 (최대 제한)"""
        self.stacks = min(self.stacks + count, self.max_stacks)

    def get_description(self) -> str:
        stack_text = f" x{self.stacks}" if self.stacks > 1 else ""
        return f"{self.get_emoji()} {self.effect_type}{stack_text} ({self.duration}턴)"


# =============================================================================
# DOT 상태이상 (Damage over Time)
# =============================================================================


@register_status_effect("burn")
class BurnEffect(StatusEffect):
    """화상: 매 턴 최대 HP의 3% × 스택 데미지"""

    def __init__(self):
        super().__init__()
        self.effect_type = "burn"
        self.max_stacks = STATUS_EFFECT.BURN_MAX_STACKS

    def tick(self, entity) -> str:
        max_hp = entity.hp
        damage = int(max_hp * STATUS_EFFECT.BURN_DAMAGE_PERCENT * self.stacks)
        damage = max(1, damage)
        entity.take_damage(damage)
        return f"🔥 **{entity.get_name()}** 화상! **-{damage}** HP"

    def get_emoji(self) -> str:
        return "🔥"


@register_status_effect("poison")
class PoisonEffect(StatusEffect):
    """독: 매 턴 최대 HP의 2% × 스택 데미지"""

    def __init__(self):
        super().__init__()
        self.effect_type = "poison"
        self.max_stacks = STATUS_EFFECT.POISON_MAX_STACKS

    def tick(self, entity) -> str:
        max_hp = entity.hp
        damage = int(max_hp * STATUS_EFFECT.POISON_DAMAGE_PERCENT * self.stacks)
        damage = max(1, damage)
        entity.take_damage(damage)
        return f"☠️ **{entity.get_name()}** 중독! **-{damage}** HP"

    def get_emoji(self) -> str:
        return "☠️"


@register_status_effect("bleed")
class BleedEffect(StatusEffect):
    """출혈: 매 턴 최대 HP의 4% 데미지"""

    def __init__(self):
        super().__init__()
        self.effect_type = "bleed"
        self.max_stacks = 1

    def tick(self, entity) -> str:
        max_hp = entity.hp
        damage = int(max_hp * STATUS_EFFECT.BLEED_DAMAGE_PERCENT)
        damage = max(1, damage)
        entity.take_damage(damage)
        return f"🩸 **{entity.get_name()}** 출혈! **-{damage}** HP"

    def get_emoji(self) -> str:
        return "🩸"


@register_status_effect("erode")
class ErodeEffect(StatusEffect):
    """잠식: 스택당 방어력 감소"""

    DEFENSE_REDUCTION_PER_STACK: int = 5

    def __init__(self):
        super().__init__()
        self.effect_type = "erode"
        self.max_stacks = 10

    def apply_stat(self, stats: dict) -> None:
        reduction = self.DEFENSE_REDUCTION_PER_STACK * self.stacks
        stats[UserStatEnum.DEFENSE] = max(0, stats[UserStatEnum.DEFENSE] - reduction)
        stats[UserStatEnum.AP_DEFENSE] = max(0, stats[UserStatEnum.AP_DEFENSE] - reduction)

    def tick(self, entity) -> str:
        return f"💀 **{entity.get_name()}** 잠식! 방어력 -{self.DEFENSE_REDUCTION_PER_STACK * self.stacks}"

    def get_emoji(self) -> str:
        return "💀"


# =============================================================================
# CC 상태이상 (Crowd Control)
# =============================================================================


@register_status_effect("slow")
class SlowEffect(StatusEffect):
    """둔화: 속도 30% 감소"""

    def __init__(self):
        super().__init__()
        self.effect_type = "slow"
        self.max_stacks = 1

    def apply_stat(self, stats: dict) -> None:
        reduction = int(stats[UserStatEnum.SPEED] * STATUS_EFFECT.SLOW_SPEED_REDUCTION)
        stats[UserStatEnum.SPEED] = max(1, stats[UserStatEnum.SPEED] - reduction)

    def get_emoji(self) -> str:
        return "🐌"


@register_status_effect("freeze")
class FreezeEffect(StatusEffect):
    """동결: 행동 불가 + 받는 피해 20% 증가"""

    def __init__(self):
        super().__init__()
        self.effect_type = "freeze"
        self.max_stacks = 1

    def can_act(self) -> bool:
        return False

    def get_emoji(self) -> str:
        return "❄️"


@register_status_effect("stun")
class StunEffect(StatusEffect):
    """기절: 행동 불가"""

    def __init__(self):
        super().__init__()
        self.effect_type = "stun"
        self.max_stacks = 1

    def can_act(self) -> bool:
        return False

    def get_emoji(self) -> str:
        return "💫"


@register_status_effect("paralyze")
class ParalyzeEffect(StatusEffect):
    """마비: 행동 불가"""

    def __init__(self):
        super().__init__()
        self.effect_type = "paralyze"
        self.max_stacks = 1

    def can_act(self) -> bool:
        return False

    def get_emoji(self) -> str:
        return "⚡"


# =============================================================================
# 디버프 상태이상
# =============================================================================


@register_status_effect("curse")
class CurseEffect(StatusEffect):
    """저주: 회복량 -50%, 방어력 -20%"""

    def __init__(self):
        super().__init__()
        self.effect_type = "curse"
        self.max_stacks = 1

    def apply_stat(self, stats: dict) -> None:
        reduction = int(stats[UserStatEnum.DEFENSE] * 0.2)
        stats[UserStatEnum.DEFENSE] = max(0, stats[UserStatEnum.DEFENSE] - reduction)

    def get_emoji(self) -> str:
        return "👿"


@register_status_effect("mark")
class MarkEffect(StatusEffect):
    """표식: 받는 피해 증가"""

    def __init__(self):
        super().__init__()
        self.effect_type = "mark"
        self.max_stacks = 1

    def get_emoji(self) -> str:
        return "🎯"


@register_status_effect("submerge")
class SubmergeEffect(StatusEffect):
    """침수: 번개 피해 2배"""

    def __init__(self):
        super().__init__()
        self.effect_type = "submerge"
        self.max_stacks = 1

    def get_emoji(self) -> str:
        return "🌊"


@register_status_effect("shock")
class ShockEffect(StatusEffect):
    """감전: 번개 체인용"""

    def __init__(self):
        super().__init__()
        self.effect_type = "shock"
        self.max_stacks = 1

    def get_emoji(self) -> str:
        return "⚡"


@register_status_effect("infection")
class InfectionEffect(StatusEffect):
    """감염: 디버프 전파"""

    def __init__(self):
        super().__init__()
        self.effect_type = "infection"
        self.max_stacks = 1

    def get_emoji(self) -> str:
        return "🦠"


@register_status_effect("combo")
class ComboEffect(StatusEffect):
    """콤보: 콤보 카운터 스택"""

    def __init__(self):
        super().__init__()
        self.effect_type = "combo"
        self.max_stacks = 10

    def get_emoji(self) -> str:
        return "💥"


# =============================================================================
# 헬퍼 함수
# =============================================================================


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

    # 기존 동일 효과 찾기
    existing = _find_status_effect(entity, effect_type)
    if existing:
        existing.add_stacks(stacks)
        if duration > 0:
            existing.duration = max(existing.duration, duration)
        emoji = existing.get_emoji()
        stack_text = f" x{existing.stacks}" if existing.stacks > 1 else ""
        return f"{emoji} **{entity.get_name()}** {effect_type}{stack_text}!"

    # 새 효과 생성
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
    """
    모든 상태이상 tick 처리 (DOT 데미지 등)

    Returns:
        로그 문자열 리스트
    """
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
    """
    모든 버프/상태이상 지속시간 감소 + 만료 제거

    Returns:
        만료 로그 리스트
    """
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
