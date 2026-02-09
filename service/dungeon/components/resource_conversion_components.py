"""
자원 변환 컴포넌트

HP, 방어력 등을 소모/전환하여 강력한 효과를 얻습니다.
- HPCostEmpowerComponent: HP 소모로 데미지 증폭
- DefenseToAttackComponent: 방어력을 공격력으로 전환
"""
from service.dungeon.components.base import SkillComponent, register_skill_with_tag


@register_skill_with_tag("hp_cost_empower")
class HPCostEmpowerComponent(SkillComponent):
    """
    HP 소모 강화 컴포넌트

    HP를 소모하여 스킬 데미지 증폭

    Config:
        hp_cost_percent: HP 소모 비율 (5.0 = 5%)
        damage_boost_percent: 데미지 증가 비율 (30.0 = 30% 증가)
        min_hp_threshold: 최소 HP (이하로는 발동 안함, 10.0 = 10%)
    """

    def __init__(self):
        super().__init__()
        self.hp_cost_percent = 5.0
        self.damage_boost_percent = 30.0
        self.min_hp_threshold = 10.0

    def apply_config(self, config: dict, skill_name: str = ""):
        """설정 적용"""
        self.hp_cost_percent = config.get("hp_cost_percent", 5.0)
        self.damage_boost_percent = config.get("damage_boost_percent", 30.0)
        self.min_hp_threshold = config.get("min_hp_threshold", 10.0)

    def on_damage_calculation(self, event):
        """
        데미지 계산 시 HP 소모하고 증폭

        Args:
            event: DamageCalculationEvent
        """
        from service.dungeon.combat_events import DamageCalculationEvent

        if not isinstance(event, DamageCalculationEvent):
            return

        attacker = event.attacker
        max_hp = getattr(attacker, 'hp', 1000)
        current_hp_percent = (attacker.now_hp / max_hp) * 100

        # HP 너무 낮으면 발동 안함
        if current_hp_percent <= self.min_hp_threshold:
            return

        # HP 소모
        hp_cost = int(max_hp * self.hp_cost_percent / 100)
        attacker.now_hp = max(1, attacker.now_hp - hp_cost)

        # 데미지 증폭
        boost_mult = 1.0 + (self.damage_boost_percent / 100)
        event.apply_multiplier(
            boost_mult,
            f"🩸 생명력 희생 (HP -{hp_cost}): 데미지 +{int(self.damage_boost_percent)}%"
        )


@register_skill_with_tag("defense_to_attack")
class DefenseToAttackComponent(SkillComponent):
    """
    방어력 → 공격력 전환 컴포넌트

    방어력을 희생하여 공격력 증가

    Config:
        conversion_ratio: 전환 비율 (0.5 = 방어력 50% → 공격력 추가)
        duration: 지속 턴 수 (0 = 영구, 전투 중)
    """

    def __init__(self):
        super().__init__()
        self.conversion_ratio = 0.5
        self.duration = 0
        self._converted_attack = 0
        self._converted_defense = 0
        self._is_applied = False

    def apply_config(self, config: dict, skill_name: str = ""):
        """설정 적용"""
        self.conversion_ratio = config.get("conversion_ratio", 0.5)
        self.duration = config.get("duration", 0)

    def on_combat_start(self, user, target) -> str:
        """
        전투 시작 시 전환 적용

        Args:
            user: 유저
            target: 대상 (사용 안함)

        Returns:
            로그 메시지
        """
        if self._is_applied:
            return ""

        defense = getattr(user, 'defense', 0)
        converted_def = int(defense * self.conversion_ratio)
        converted_atk = converted_def  # 1:1 전환

        user.defense = max(0, user.defense - converted_def)
        user.attack += converted_atk

        self._converted_attack = converted_atk
        self._converted_defense = converted_def
        self._is_applied = True

        return f"⚔️🛡️ 방어력 {converted_def} → 공격력 {converted_atk} 전환!"

    def on_combat_end(self, user) -> str:
        """
        전투 종료 시 복구

        Args:
            user: 유저

        Returns:
            로그 메시지
        """
        if not self._is_applied:
            return ""

        user.attack -= self._converted_attack
        user.defense += self._converted_defense

        self._is_applied = False
        return ""
