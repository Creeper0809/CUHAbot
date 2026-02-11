"""
턴 기반 효과 컴포넌트

턴 수에 따라 발동하는 효과들입니다.
- TurnCountEmpowerComponent: 특정 턴마다 강화
- AccumulationComponent: 턴이 지날수록 누적 강화
"""
from service.dungeon.components.base import SkillComponent, register_skill_with_tag


@register_skill_with_tag("turn_count_empower")
class TurnCountEmpowerComponent(SkillComponent):
    """
    턴 카운트 강화 컴포넌트

    특정 턴마다 스킬 강화

    Config:
        trigger_interval: 발동 간격 (3 = 3턴마다)
        damage_multiplier: 데미지 배율 (2.0 = 200%)
    """

    def __init__(self):
        super().__init__()
        self.trigger_interval = 3
        self.damage_multiplier = 2.0
        self._turn_count = 0

    def apply_config(self, config: dict, skill_name: str = ""):
        """설정 적용"""
        self.trigger_interval = config.get("trigger_interval", 3)
        self.damage_multiplier = config.get("damage_multiplier", 2.0)

    def on_turn_start(self, user, target) -> str:
        """
        턴 카운트 증가

        Args:
            user: 유저
            target: 대상

        Returns:
            로그 메시지
        """
        self._turn_count += 1
        if self._turn_count % self.trigger_interval == 0:
            mult_percent = int(self.damage_multiplier * 100)
            return f"⏰ {self.trigger_interval}턴째! 다음 스킬 {mult_percent}% 데미지!"
        return ""

    def on_damage_calculation(self, event):
        """
        강화 턴에만 적용

        Args:
            event: DamageCalculationEvent
        """
        from service.dungeon.combat_events import DamageCalculationEvent

        if not isinstance(event, DamageCalculationEvent):
            return

        if self._turn_count % self.trigger_interval == 0:
            event.apply_multiplier(self.damage_multiplier, "⏰ 타이밍 공격!")


@register_skill_with_tag("accumulation")
class AccumulationComponent(SkillComponent):
    """
    누적 강화 컴포넌트

    턴이 지날수록 강해짐

    Config:
        growth_per_turn: 턴당 성장 비율 (2.0 = 2%씩 증가)
        max_growth: 최대 성장 (50.0 = 50%까지)
    """

    def __init__(self):
        super().__init__()
        self.growth_per_turn = 2.0
        self.max_growth = 50.0
        self._accumulated = 0.0

    def apply_config(self, config: dict, skill_name: str = ""):
        """설정 적용"""
        self.growth_per_turn = config.get("growth_per_turn", 2.0)
        self.max_growth = config.get("max_growth", 50.0)

    def on_turn_start(self, user, target) -> str:
        """
        누적 성장

        Args:
            user: 유저
            target: 대상

        Returns:
            로그 메시지
        """
        self._accumulated = min(self._accumulated + self.growth_per_turn, self.max_growth)
        return f"📈 누적 강화: +{int(self._accumulated)}%"

    def on_damage_calculation(self, event):
        """
        누적 데미지 적용

        Args:
            event: DamageCalculationEvent
        """
        from service.dungeon.combat_events import DamageCalculationEvent

        if not isinstance(event, DamageCalculationEvent):
            return

        if self._accumulated > 0:
            bonus = 1.0 + (self._accumulated / 100)
            event.apply_multiplier(bonus)
