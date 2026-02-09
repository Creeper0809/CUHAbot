"""
스킬 체인 & 콤보 컴포넌트

스킬 사용 패턴에 따라 보너스를 제공합니다.
- ConsecutiveSkillBonusComponent: 같은 타입 연속 사용 보너스
- SkillVarietyBonusComponent: 다양한 스킬 사용 보너스
"""
from service.dungeon.components.base import SkillComponent, register_skill_with_tag


@register_skill_with_tag("consecutive_skill_bonus")
class ConsecutiveSkillBonusComponent(SkillComponent):
    """
    연속 스킬 보너스 컴포넌트

    같은 타입의 스킬을 연속으로 사용하면 보너스 증가

    Config:
        target_skill_type: 대상 스킬 타입 ("attack", "heal", "fire" 등)
        bonus_per_stack: 스택당 보너스 (10.0 = 10% 증가)
        max_stacks: 최대 스택 수
    """

    def __init__(self):
        super().__init__()
        self.target_skill_type = "attack"
        self.bonus_per_stack = 10.0
        self.max_stacks = 5
        self._current_stacks = 0
        self._last_skill_id = None

    def apply_config(self, config: dict, skill_name: str = ""):
        """설정 적용"""
        self.target_skill_type = config.get("target_skill_type", "attack")
        self.bonus_per_stack = config.get("bonus_per_stack", 10.0)
        self.max_stacks = config.get("max_stacks", 5)

    def on_skill_used(self, user, skill) -> str:
        """
        스킬 사용 시 스택 추적 (장비 전용)

        Args:
            user: 유저
            skill: 사용한 스킬

        Returns:
            로그 메시지
        """
        skill_type = self._get_skill_type(skill)

        if skill_type == self.target_skill_type:
            if skill.id == self._last_skill_id:
                # 같은 스킬 연속 사용
                self._current_stacks = min(self._current_stacks + 1, self.max_stacks)
            else:
                # 다른 스킬이지만 같은 타입
                self._current_stacks = 1
            self._last_skill_id = skill.id
        else:
            # 다른 타입 스킬 사용 → 리셋
            self._current_stacks = 0
            self._last_skill_id = None

        if self._current_stacks > 0:
            bonus_total = int(self.bonus_per_stack * self._current_stacks)
            return f"🔗 연속 {self._current_stacks}회! (데미지 +{bonus_total}%)"

        return ""

    def on_damage_calculation(self, event):
        """
        데미지 계산 시 보너스 적용

        Args:
            event: DamageCalculationEvent
        """
        from service.dungeon.combat_events import DamageCalculationEvent

        if not isinstance(event, DamageCalculationEvent):
            return

        if self._current_stacks > 0:
            bonus = 1.0 + (self.bonus_per_stack * self._current_stacks / 100)
            event.apply_multiplier(bonus)

    def _get_skill_type(self, skill) -> str:
        """스킬 타입 추출"""
        if not skill:
            return ""

        # 속성 확인
        attribute = getattr(skill, 'attribute', '').lower()
        if attribute in ['화염', 'fire']:
            return 'fire'
        if attribute in ['냉기', 'ice']:
            return 'ice'
        if attribute in ['번개', 'lightning']:
            return 'lightning'
        if attribute in ['수속성', 'water']:
            return 'water'
        if attribute in ['신성', 'holy']:
            return 'holy'
        if attribute in ['암흑', 'dark']:
            return 'dark'

        # 컴포넌트 태그 확인
        if hasattr(skill, 'components'):
            for comp in skill.components:
                tag = getattr(comp, '_tag', '')
                if tag == 'attack':
                    return 'attack'
                if tag == 'heal':
                    return 'heal'

        return ''


@register_skill_with_tag("skill_variety_bonus")
class SkillVarietyBonusComponent(SkillComponent):
    """
    스킬 다양성 보너스 컴포넌트

    다양한 타입의 스킬을 사용하면 보너스 증가

    Config:
        bonus_per_unique: 고유 스킬당 보너스 (5.0 = 5%)
        max_unique_count: 최대 카운트
        reset_on_repeat: 중복 사용 시 리셋 여부
    """

    def __init__(self):
        super().__init__()
        self.bonus_per_unique = 5.0
        self.max_unique_count = 5
        self.reset_on_repeat = True
        self._used_skills = set()

    def apply_config(self, config: dict, skill_name: str = ""):
        """설정 적용"""
        self.bonus_per_unique = config.get("bonus_per_unique", 5.0)
        self.max_unique_count = config.get("max_unique_count", 5)
        self.reset_on_repeat = config.get("reset_on_repeat", True)

    def on_skill_used(self, user, skill) -> str:
        """
        스킬 사용 추적 (장비 전용)

        Args:
            user: 유저
            skill: 사용한 스킬

        Returns:
            로그 메시지
        """
        if skill.id in self._used_skills and self.reset_on_repeat:
            # 중복 사용 → 리셋
            self._used_skills.clear()
            return "❌ 중복 사용! 다양성 보너스 리셋"

        self._used_skills.add(skill.id)
        unique_count = min(len(self._used_skills), self.max_unique_count)
        bonus = int(self.bonus_per_unique * unique_count)
        return f"🌈 다양성 보너스 {unique_count}종! (데미지 +{bonus}%)"

    def on_damage_calculation(self, event):
        """
        데미지 계산 시 보너스 적용

        Args:
            event: DamageCalculationEvent
        """
        from service.dungeon.combat_events import DamageCalculationEvent

        if not isinstance(event, DamageCalculationEvent):
            return

        unique_count = min(len(self._used_skills), self.max_unique_count)
        if unique_count > 0:
            bonus = 1.0 + (self.bonus_per_unique * unique_count / 100)
            event.apply_multiplier(bonus)
