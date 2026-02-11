"""
쿨다운 및 자원 소모 관련 컴포넌트 (장비 전용 패시브)

스킬 쿨다운, 마나 소모 등을 감소시키는 장비 효과들입니다.
"""
from service.dungeon.components.base import SkillComponent, register_skill_with_tag


@register_skill_with_tag("cooldown_reduction")
class CooldownReductionComponent(SkillComponent):
    """
    쿨다운 감소 컴포넌트 (장비 전용 패시브)

    스킬 쿨다운을 일정 비율만큼 감소시킵니다.

    Config options:
        cooldown_reduction (float): 쿨다운 감소 비율 (0.0~0.5, 예: 0.2 = 20% 감소, 최대 50%)
    """

    def __init__(self):
        super().__init__()
        self.cooldown_reduction = 0.0

    def apply_config(self, config, skill_name, priority=0):
        super().apply_config(config, skill_name, priority)
        self.cooldown_reduction = min(config.get("cooldown_reduction", 0.0), 0.5)  # 최대 50% 제한

    def on_turn(self, attacker, target):
        """패시브이므로 직접 호출되지 않음"""
        return ""

    def get_cooldown_multiplier(self) -> float:
        """
        쿨다운 배율 반환

        Returns:
            1.0 - cooldown_reduction (예: 0.8 = 20% 감소)
        """
        return 1.0 - self.cooldown_reduction


@register_skill_with_tag("mana_cost_reduction")
class ManaCostReductionComponent(SkillComponent):
    """
    마나 소모 감소 컴포넌트 (장비 전용 패시브)

    스킬 마나 소모를 일정 비율 또는 고정값만큼 감소시킵니다.

    Config options:
        mana_reduction_percent (float): 마나 소모 감소 비율 (0.0~0.5, 예: 0.05 = 5% 감소)
        mana_reduction_flat (int): 마나 소모 고정 감소 (예: 5 = -5 마나)
    """

    def __init__(self):
        super().__init__()
        self.mana_reduction_percent = 0.0
        self.mana_reduction_flat = 0

    def apply_config(self, config, skill_name, priority=0):
        super().apply_config(config, skill_name, priority)
        self.mana_reduction_percent = min(config.get("mana_reduction_percent", 0.0), 0.5)
        self.mana_reduction_flat = config.get("mana_reduction_flat", 0)

    def on_turn(self, attacker, target):
        """패시브이므로 직접 호출되지 않음"""
        return ""

    def get_mana_cost_multiplier(self) -> float:
        """마나 소모 비율 배율 반환"""
        return 1.0 - self.mana_reduction_percent

    def get_mana_cost_flat_reduction(self) -> int:
        """마나 소모 고정 감소량 반환"""
        return self.mana_reduction_flat


@register_skill_with_tag("buff_duration_extension")
class BuffDurationExtensionComponent(SkillComponent):
    """
    버프 지속시간 연장 컴포넌트 (장비 전용 패시브)

    버프 또는 디버프의 지속시간을 일정 비율만큼 연장합니다.

    Config options:
        duration_bonus (float): 지속시간 보너스 비율 (예: 0.5 = 50% 증가)
        affect_buffs (bool): 버프에 적용 여부 (기본 True)
        affect_debuffs (bool): 디버프에 적용 여부 (기본 False)
    """

    def __init__(self):
        super().__init__()
        self.duration_bonus = 0.0
        self.affect_buffs = True
        self.affect_debuffs = False

    def apply_config(self, config, skill_name, priority=0):
        super().apply_config(config, skill_name, priority)
        self.duration_bonus = config.get("duration_bonus", 0.0)
        self.affect_buffs = config.get("affect_buffs", True)
        self.affect_debuffs = config.get("affect_debuffs", False)

    def on_turn(self, attacker, target):
        """패시브이므로 직접 호출되지 않음"""
        return ""

    def get_duration_multiplier(self, is_buff: bool = True) -> float:
        """
        지속시간 배율 반환

        Args:
            is_buff: True면 버프, False면 디버프

        Returns:
            1.0 + duration_bonus if applicable, else 1.0
        """
        if is_buff and self.affect_buffs:
            return 1.0 + self.duration_bonus
        if not is_buff and self.affect_debuffs:
            return 1.0 + self.duration_bonus
        return 1.0


@register_skill_with_tag("skill_usage_limit")
class SkillUsageLimitComponent(SkillComponent):
    """
    스킬 사용 제한 컴포넌트 (장비 전용 패시브)

    특정 스킬의 사용 횟수를 제한하거나 증가시킵니다.

    Config options:
        usage_bonus (int): 사용 횟수 보너스 (양수 = 증가, 음수 = 감소)
        skill_type (str): 대상 스킬 타입 (예: "awakening", "ultimate")

    Note: 현재 스킬 시스템이 사용 횟수 제한을 지원하지 않으므로,
    향후 구현을 위한 placeholder 컴포넌트입니다.
    """

    def __init__(self):
        super().__init__()
        self.usage_bonus = 0
        self.skill_type = None

    def apply_config(self, config, skill_name, priority=0):
        super().apply_config(config, skill_name, priority)
        self.usage_bonus = config.get("usage_bonus", 0)
        self.skill_type = config.get("skill_type", None)

    def on_turn(self, attacker, target):
        """패시브이므로 직접 호출되지 않음"""
        return ""

    def get_usage_bonus(self) -> int:
        """사용 횟수 보너스 반환"""
        return self.usage_bonus
