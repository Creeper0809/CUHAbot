"""
방어 패시브 컴포넌트: 속성 면역, 속성 저항, 데미지 반사, 상태이상 면역
"""
from service.dungeon.components.base import SkillComponent, register_skill_with_tag


@register_skill_with_tag("passive_element_immunity")
class ElementImmunityComponent(SkillComponent):
    """
    속성 면역 패시브 - 특정 속성 데미지를 완전 무효화

    damage_pipeline.py의 get_passive_immunities()에서 스캔됩니다.

    Config options:
        immune_to (list[str]): 면역 속성 목록 (예: ["번개"], ["냉기", "수속성"])
    """

    def __init__(self):
        super().__init__()
        self.immune_to: list[str] = []
        self._applied_entities: set[int] = set()

    def apply_config(self, config, skill_name, priority=0):
        super().apply_config(config, skill_name, priority)
        self.immune_to = config.get("immune_to", [])

    def on_turn_start(self, attacker, target):
        entity_id = id(attacker)
        if entity_id in self._applied_entities:
            return ""
        self._applied_entities.add(entity_id)

        if not self.immune_to:
            return ""
        attrs = ", ".join(self.immune_to)
        return f"🌟 **{attacker.get_name()}** 패시브 「{self.skill_name}」 → {attrs} 면역"


@register_skill_with_tag("passive_element_resistance")
class ElementResistanceComponent(SkillComponent):
    """
    속성 저항 패시브 - 특정 속성 데미지를 비율 감소

    damage_pipeline.py의 get_passive_resistances()에서 스캔됩니다.
    MAX_RESISTANCE(0.75) 캡 적용.

    Config options:
        resist_type (str): 저항 속성 (예: "화염")
        resist_percent (float): 저항 비율 (예: 0.5 = 50%)
    """

    def __init__(self):
        super().__init__()
        self.resist_type: str = ""
        self.resist_percent: float = 0.0
        self._applied_entities: set[int] = set()

    def apply_config(self, config, skill_name, priority=0):
        super().apply_config(config, skill_name, priority)
        self.resist_type = config.get("resist_type", "")
        self.resist_percent = config.get("resist_percent", 0.0)

    def on_turn_start(self, attacker, target):
        entity_id = id(attacker)
        if entity_id in self._applied_entities:
            return ""
        self._applied_entities.add(entity_id)

        if not self.resist_type or self.resist_percent <= 0:
            return ""
        return (
            f"🌟 **{attacker.get_name()}** 패시브 「{self.skill_name}」 → "
            f"{self.resist_type} 저항 {int(self.resist_percent * 100)}%"
        )


@register_skill_with_tag("passive_damage_reflection")
class DamageReflectionComponent(SkillComponent):
    """
    데미지 반사 패시브 - 받은 데미지의 일부를 공격자에게 반환

    damage_pipeline.py의 get_passive_reflection()에서 스캔됩니다.
    반사 데미지는 다시 반사되지 않음 (is_reflected=True).

    Config options:
        reflect_percent (float): 반사 비율 (예: 0.1 = 10%)
    """

    def __init__(self):
        super().__init__()
        self.reflect_percent: float = 0.0
        self._applied_entities: set[int] = set()

    def apply_config(self, config, skill_name, priority=0):
        super().apply_config(config, skill_name, priority)
        self.reflect_percent = config.get("reflect_percent", 0.0)

    def on_turn_start(self, attacker, target):
        entity_id = id(attacker)
        if entity_id in self._applied_entities:
            return ""
        self._applied_entities.add(entity_id)

        if self.reflect_percent <= 0:
            return ""
        return (
            f"🌟 **{attacker.get_name()}** 패시브 「{self.skill_name}」 → "
            f"받는 피해 {int(self.reflect_percent * 100)}% 반사"
        )


@register_skill_with_tag("passive_status_immunity")
class StatusImmunityComponent(SkillComponent):
    """
    상태이상 면역 패시브 - 특정/모든 상태이상 면역

    damage_pipeline.py의 get_status_immunities()에서 스캔됩니다.
    helpers.py의 apply_status_effect()에서 면역 체크.

    Config options:
        immune_all (bool): 모든 상태이상 면역 (기본 False)
        immune_types (list[str]): 면역 상태이상 목록 (예: ["freeze", "stun"])
    """

    def __init__(self):
        super().__init__()
        self.immune_all: bool = False
        self.immune_types: list[str] = []
        self._applied_entities: set[int] = set()

    def apply_config(self, config, skill_name, priority=0):
        super().apply_config(config, skill_name, priority)
        self.immune_all = config.get("immune_all", False)
        self.immune_types = config.get("immune_types", [])

    def on_turn_start(self, attacker, target):
        entity_id = id(attacker)
        if entity_id in self._applied_entities:
            return ""
        self._applied_entities.add(entity_id)

        if self.immune_all:
            return f"🌟 **{attacker.get_name()}** 패시브 「{self.skill_name}」 → 상태이상 면역"
        if self.immune_types:
            types = ", ".join(self.immune_types)
            return f"🌟 **{attacker.get_name()}** 패시브 「{self.skill_name}」 → {types} 면역"
        return ""
