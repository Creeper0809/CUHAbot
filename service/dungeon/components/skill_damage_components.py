"""
스킬 데미지 강화 컴포넌트 (장비 전용 패시브)

스킬 사용 시 데미지를 증폭시키는 장비 효과들입니다.
"""
from service.dungeon.components.base import SkillComponent, register_skill_with_tag


@register_skill_with_tag("skill_damage_boost")
class SkillDamageBoostComponent(SkillComponent):
    """
    스킬 데미지 증폭 컴포넌트 (장비 전용 패시브)

    모든 스킬의 데미지를 일정 비율만큼 증가시킵니다.

    Config options:
        damage_bonus (float): 데미지 보너스 비율 (예: 0.25 = 25% 증가)
    """

    def __init__(self):
        super().__init__()
        self.damage_bonus = 0.0

    def apply_config(self, config, skill_name, priority=0):
        super().apply_config(config, skill_name, priority)
        self.damage_bonus = config.get("damage_bonus", 0.0)

    def on_turn(self, attacker, target):
        """
        스킬 실행 시 호출되지 않음 (패시브)

        Note: 이 컴포넌트는 get_skill_damage_multiplier()를 통해
        데미지 계산 시점에 반영됩니다.
        """
        return ""

    def get_skill_damage_multiplier(self) -> float:
        """
        스킬 데미지 배율 반환

        Returns:
            1.0 + damage_bonus (예: 1.25 = 25% 증가)
        """
        return 1.0 + self.damage_bonus


@register_skill_with_tag("skill_type_damage_boost")
class SkillTypeDamageBoostComponent(SkillComponent):
    """
    특정 스킬 타입 데미지 증폭 컴포넌트 (장비 전용 패시브)

    특정 타입의 스킬에만 데미지 보너스를 적용합니다.

    Config options:
        skill_type (str): 대상 스킬 타입
            - "awakening": 각성 스킬
            - "healing": 회복 스킬
            - "physical": 물리 공격 스킬
            - "magical": 마법 공격 스킬
            - "buff": 버프 스킬
            - "debuff": 디버프 스킬
        damage_bonus (float): 데미지 보너스 비율 (예: 0.5 = 50% 증가)
    """

    def __init__(self):
        super().__init__()
        self.skill_type = None
        self.damage_bonus = 0.0

    def apply_config(self, config, skill_name, priority=0):
        super().apply_config(config, skill_name, priority)
        self.skill_type = config.get("skill_type", None)
        self.damage_bonus = config.get("damage_bonus", 0.0)

    def on_turn(self, attacker, target):
        return ""

    def get_skill_damage_multiplier(self, skill=None) -> float:
        """
        스킬 타입에 따른 데미지 배율 반환

        Args:
            skill: 현재 사용 중인 스킬 객체

        Returns:
            1.0 + damage_bonus if type matches, else 1.0
        """
        if not self.skill_type or not skill:
            return 1.0

        # 스킬 타입 매칭
        skill_category = getattr(skill, 'skill_model', None)
        if not skill_category:
            return 1.0

        category = getattr(skill_category, 'category', '')
        skill_type_lower = self.skill_type.lower()

        # 각성 스킬
        if skill_type_lower == "awakening":
            if "각성" in category or "ultimate" in category.lower():
                return 1.0 + self.damage_bonus

        # 회복 스킬
        if skill_type_lower == "healing":
            if "회복" in category or "heal" in category.lower():
                return 1.0 + self.damage_bonus

        # 물리/마법 공격 (컴포넌트로 판별)
        if skill_type_lower == "physical":
            for comp in skill.components:
                tag = getattr(comp, '_tag', '')
                if tag == "attack" and getattr(comp, 'is_physical', True):
                    return 1.0 + self.damage_bonus

        if skill_type_lower == "magical":
            for comp in skill.components:
                tag = getattr(comp, '_tag', '')
                if tag == "attack" and not getattr(comp, 'is_physical', True):
                    return 1.0 + self.damage_bonus

        # 버프/디버프
        if skill_type_lower == "buff":
            for comp in skill.components:
                if getattr(comp, '_tag', '') == "buff":
                    return 1.0 + self.damage_bonus

        if skill_type_lower == "debuff":
            for comp in skill.components:
                if getattr(comp, '_tag', '') == "debuff":
                    return 1.0 + self.damage_bonus

        return 1.0


@register_skill_with_tag("attribute_damage_boost")
class AttributeDamageBoostComponent(SkillComponent):
    """
    속성 데미지 증폭 컴포넌트 (장비 전용 패시브)

    특정 속성의 스킬 데미지를 증가시킵니다.

    Config options:
        attribute (str): 대상 속성 (예: "화염", "냉기", "번개", "신성", "암흑", "수속성")
        damage_bonus (float): 데미지 보너스 비율 (예: 0.3 = 30% 증가)
    """

    def __init__(self):
        super().__init__()
        self.attribute = None
        self.damage_bonus = 0.0

    def apply_config(self, config, skill_name, priority=0):
        super().apply_config(config, skill_name, priority)
        self.attribute = config.get("attribute", None)
        self.damage_bonus = config.get("damage_bonus", 0.0)

    def on_turn(self, attacker, target):
        return ""

    def get_skill_damage_multiplier(self, skill=None) -> float:
        """
        속성에 따른 데미지 배율 반환

        Args:
            skill: 현재 사용 중인 스킬 객체

        Returns:
            1.0 + damage_bonus if attribute matches, else 1.0
        """
        if not self.attribute or not skill:
            return 1.0

        skill_attr = getattr(skill, 'attribute', '무속성')

        # 속성 매칭
        attribute_aliases = {
            "화염": ["화염", "fire", "불"],
            "냉기": ["냉기", "ice", "얼음"],
            "번개": ["번개", "lightning", "전기", "뇌전"],
            "수속성": ["수속성", "water", "물"],
            "신성": ["신성", "holy", "빛"],
            "암흑": ["암흑", "dark", "어둠"],
        }

        for attr_key, aliases in attribute_aliases.items():
            if self.attribute in aliases and skill_attr in aliases:
                return 1.0 + self.damage_bonus

        return 1.0


@register_skill_with_tag("conditional_damage_boost")
class ConditionalDamageBoostComponent(SkillComponent):
    """
    조건부 데미지 증폭 컴포넌트 (장비 전용 패시브)

    특정 조건을 만족하는 대상에게 추가 데미지를 줍니다.

    Config options:
        condition (str): 조건 타입
            - "low_hp": HP가 특정 비율 이하인 적
            - "high_hp": HP가 특정 비율 이상인 적
            - "status": 특정 상태이상에 걸린 적
        threshold (float): HP 조건 임계값 (0.0~1.0, 예: 0.3 = 30% 이하)
        status_effect (str): 상태이상 조건 (condition="status"일 때)
        damage_bonus (float): 데미지 보너스 비율 (예: 1.0 = 100% 증가)
    """

    def __init__(self):
        super().__init__()
        self.condition = None
        self.threshold = 0.0
        self.status_effect = None
        self.damage_bonus = 0.0

    def apply_config(self, config, skill_name, priority=0):
        super().apply_config(config, skill_name, priority)
        self.condition = config.get("condition", None)
        self.threshold = config.get("threshold", 0.0)
        self.status_effect = config.get("status_effect", None)
        self.damage_bonus = config.get("damage_bonus", 0.0)

    def on_turn(self, attacker, target):
        return ""

    def get_conditional_damage_multiplier(self, target) -> float:
        """
        조건에 따른 데미지 배율 반환

        Args:
            target: 공격 대상 엔티티

        Returns:
            1.0 + damage_bonus if condition met, else 1.0
        """
        if not self.condition:
            return 1.0

        # HP 조건 체크
        if self.condition == "low_hp":
            max_hp = getattr(target, 'hp', 1)
            now_hp = getattr(target, 'now_hp', max_hp)
            hp_ratio = now_hp / max_hp if max_hp > 0 else 1.0

            if hp_ratio <= self.threshold:
                return 1.0 + self.damage_bonus

        elif self.condition == "high_hp":
            max_hp = getattr(target, 'hp', 1)
            now_hp = getattr(target, 'now_hp', max_hp)
            hp_ratio = now_hp / max_hp if max_hp > 0 else 1.0

            if hp_ratio >= self.threshold:
                return 1.0 + self.damage_bonus

        # 상태이상 조건 체크
        elif self.condition == "status":
            if not self.status_effect:
                return 1.0

            from service.dungeon.status import has_status_effect
            if has_status_effect(target, self.status_effect):
                return 1.0 + self.damage_bonus

        return 1.0
