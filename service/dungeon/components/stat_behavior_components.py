"""
스탯 행동 컴포넌트 (Stat Behavior Components)

PassiveBuffComponent를 행동별로 분리한 컴포넌트들입니다.
각 컴포넌트는 자신의 스탯 메타데이터를 소유하고, 해당 행동을 구현합니다.

컴포넌트 분류:
- BonusStatComponent (stat_bonus): 단순 표시 스탯 (drop_rate, exp_bonus)
- CombatStatComponent (stat_combat): 전투 스탯 (crit, lifesteal, armor_pen)
- DefenseStatComponent (stat_defense): 방어 스탯 (resists)
- AccuracyStatComponent (stat_accuracy): 명중/회피 스탯
"""
import random
from typing import TYPE_CHECKING

from service.dungeon.components.base import SkillComponent, register_skill_with_tag
from service.dungeon.combat_events import (
    DamageCalculationEvent,
    DamageDealtEvent,
    TakeDamageEvent,
    HitCalculationEvent,
)

if TYPE_CHECKING:
    from service.dungeon.entity import Entity


@register_skill_with_tag("stat_bonus")
class BonusStatComponent(SkillComponent):
    """
    보너스 스탯 컴포넌트 (단순 표시용)

    드롭률, 경험치 보너스 등 전투 중 특별한 행동이 필요 없는 스탯입니다.
    이 스탯들은 UI에 표시만 되고, 실제 행동은 해당 서비스 레이어에서 처리합니다.

    Config options:
        drop_rate (float): 드롭률 보너스
        exp_bonus (float): 경험치 보너스
        bonus_hp_pct (float): HP 퍼센트 보너스
        bonus_speed_pct (float): 속도 퍼센트 보너스
        bonus_all_stats_pct (float): 모든 스탯 퍼센트 보너스
    """

    STAT_METADATA = {
        "drop_rate": {"label": "드롭률", "suffix": "%", "prefix": "+", "is_ratio": True},
        "exp_bonus": {"label": "경험치", "suffix": "%", "prefix": "+", "is_ratio": False},
    }

    def __init__(self):
        super().__init__()
        self._raw_config = {}

    def apply_config(self, config, skill_name, priority=0):
        super().apply_config(config, skill_name, priority)
        self._raw_config = config

    def get_displayable_stats(self) -> dict:
        """UI에 표시할 스탯 정보 반환"""
        result = {}
        for stat_key, value in self._raw_config.items():
            if stat_key in self.STAT_METADATA and value > 0:
                result[stat_key] = {
                    "value": value,
                    "metadata": self.STAT_METADATA[stat_key]
                }
        return result


@register_skill_with_tag("stat_combat")
class CombatStatComponent(SkillComponent):
    """
    전투 스탯 컴포넌트 (데미지 계산 시 개입)

    치명타, 흡혈, 방어구 관통 등 데미지 계산 및 적용 시 행동하는 스탯입니다.

    Config options:
        crit_rate (float): 치명타 확률
        crit_damage (float): 치명타 배율
        lifesteal (float): 흡혈 비율
        armor_pen (float): 방어구 관통
        magic_pen (float): 마법 관통
    """

    STAT_METADATA = {
        "crit_rate": {"label": "치명타율", "suffix": "%", "prefix": "", "is_ratio": False},
        "crit_damage": {"label": "치명타배율", "suffix": "%", "prefix": "", "is_ratio": False},
        "lifesteal": {"label": "흡혈", "suffix": "%", "prefix": "", "is_ratio": True},
        "armor_pen": {"label": "방어 관통", "suffix": "%", "prefix": "", "is_ratio": False},
        "magic_pen": {"label": "마법 관통", "suffix": "%", "prefix": "", "is_ratio": False},
    }

    def __init__(self):
        super().__init__()
        self._raw_config = {}
        self.crit_rate = 0.0
        self.crit_damage = 0.0
        self.lifesteal = 0.0
        self.armor_pen = 0.0
        self.magic_pen = 0.0

    def apply_config(self, config, skill_name, priority=0):
        super().apply_config(config, skill_name, priority)
        self._raw_config = config
        self.crit_rate = config.get("crit_rate", 0.0)
        self.crit_damage = config.get("crit_damage", 0.0)
        self.lifesteal = config.get("lifesteal", 0.0)
        self.armor_pen = config.get("armor_pen", 0.0)
        self.magic_pen = config.get("magic_pen", 0.0)

    def get_displayable_stats(self) -> dict:
        """UI에 표시할 스탯 정보 반환"""
        result = {}
        for stat_key, value in self._raw_config.items():
            if stat_key in self.STAT_METADATA and value > 0:
                result[stat_key] = {
                    "value": value,
                    "metadata": self.STAT_METADATA[stat_key]
                }
        return result

    def on_damage_calculation(self, event: DamageCalculationEvent):
        """
        데미지 계산 시 호출

        - 치명타 판정 및 배율 적용
        - 방어구 관통 적용
        """
        # 치명타 판정
        if self.crit_rate > 0:
            if self._roll_critical():
                crit_mult = (100 + self.crit_damage) / 100  # 150% → 1.5
                event.apply_multiplier(crit_mult, f"⚡ 치명타! ({int(crit_mult * 100)}%)")

        # 방어구 관통
        if self.armor_pen > 0:
            event.ignore_defense(self.armor_pen / 100)

    def on_deal_damage(self, event: DamageDealtEvent):
        """
        데미지 적용 후 호출

        - 흡혈 효과 발동
        """
        if self.lifesteal > 0:
            heal = int(event.damage * self.lifesteal / 100)
            if heal > 0:
                event.attacker.heal(heal)
                event.add_log(f"💉 흡혈 {heal} HP 회복")

    def _roll_critical(self) -> bool:
        """치명타 판정"""
        return random.random() * 100 < self.crit_rate


@register_skill_with_tag("stat_defense")
class DefenseStatComponent(SkillComponent):
    """
    방어 스탯 컴포넌트 (피해 받을 때 개입)

    속성 저항 등 피해 경감 효과를 처리합니다.

    Config options:
        fire_resist (float): 화염 저항
        ice_resist (float): 냉기 저항
        lightning_resist (float): 번개 저항
        water_resist (float): 수속성 저항
        holy_resist (float): 신성 저항
        dark_resist (float): 암흑 저항
    """

    STAT_METADATA = {
        "fire_resist": {"label": "화염 저항", "suffix": "%", "prefix": "", "is_ratio": False},
        "ice_resist": {"label": "냉기 저항", "suffix": "%", "prefix": "", "is_ratio": False},
        "lightning_resist": {"label": "번개 저항", "suffix": "%", "prefix": "", "is_ratio": False},
        "water_resist": {"label": "수속성 저항", "suffix": "%", "prefix": "", "is_ratio": False},
        "holy_resist": {"label": "신성 저항", "suffix": "%", "prefix": "", "is_ratio": False},
        "dark_resist": {"label": "암흑 저항", "suffix": "%", "prefix": "", "is_ratio": False},
    }

    # 속성명 매핑 (한글 → 영문)
    ATTRIBUTE_MAP = {
        "화염": "fire",
        "냉기": "ice",
        "번개": "lightning",
        "물": "water",
        "신성": "holy",
        "암흑": "dark",
        "불": "fire",  # 별칭
    }

    def __init__(self):
        super().__init__()
        self._raw_config = {}
        self.fire_resist = 0.0
        self.ice_resist = 0.0
        self.lightning_resist = 0.0
        self.water_resist = 0.0
        self.holy_resist = 0.0
        self.dark_resist = 0.0

    def apply_config(self, config, skill_name, priority=0):
        super().apply_config(config, skill_name, priority)
        self._raw_config = config
        self.fire_resist = config.get("fire_resist", 0.0)
        self.ice_resist = config.get("ice_resist", 0.0)
        self.lightning_resist = config.get("lightning_resist", 0.0)
        self.water_resist = config.get("water_resist", 0.0)
        self.holy_resist = config.get("holy_resist", 0.0)
        self.dark_resist = config.get("dark_resist", 0.0)

    def get_displayable_stats(self) -> dict:
        """UI에 표시할 스탯 정보 반환"""
        result = {}
        for stat_key, value in self._raw_config.items():
            if stat_key in self.STAT_METADATA and value > 0:
                result[stat_key] = {
                    "value": value,
                    "metadata": self.STAT_METADATA[stat_key]
                }
        return result

    def on_take_damage(self, event: TakeDamageEvent):
        """
        피해 받을 때 호출

        - 속성 저항으로 데미지 경감
        """
        # 속성명을 영문으로 변환
        attr_eng = self.ATTRIBUTE_MAP.get(event.damage_attribute, "")
        if not attr_eng:
            return

        resist_key = f"{attr_eng}_resist"
        resist_value = getattr(self, resist_key, 0.0)

        if resist_value > 0:
            reduction = int(event.damage * resist_value / 100)
            if reduction > 0:
                event.reduce_damage(
                    reduction,
                    f"🛡️ {event.damage_attribute} 저항 -{reduction}"
                )


@register_skill_with_tag("stat_accuracy")
class AccuracyStatComponent(SkillComponent):
    """
    명중/회피 스탯 컴포넌트 (명중 판정 시 개입)

    명중률, 회피율, 블록률을 처리합니다.

    Config options:
        accuracy (float): 명중률
        evasion (float): 회피율
        block_rate (float): 블록률
    """

    STAT_METADATA = {
        "accuracy": {"label": "명중률", "suffix": "%", "prefix": "", "is_ratio": False},
        "evasion": {"label": "회피율", "suffix": "%", "prefix": "", "is_ratio": False},
        "block_rate": {"label": "블록률", "suffix": "%", "prefix": "", "is_ratio": False},
    }

    def __init__(self):
        super().__init__()
        self._raw_config = {}
        self.accuracy = 0.0
        self.evasion = 0.0
        self.block_rate = 0.0

    def apply_config(self, config, skill_name, priority=0):
        super().apply_config(config, skill_name, priority)
        self._raw_config = config
        self.accuracy = config.get("accuracy", 0.0)
        self.evasion = config.get("evasion", 0.0)
        self.block_rate = config.get("block_rate", 0.0)

    def get_displayable_stats(self) -> dict:
        """UI에 표시할 스탯 정보 반환"""
        result = {}
        for stat_key, value in self._raw_config.items():
            if stat_key in self.STAT_METADATA and value > 0:
                result[stat_key] = {
                    "value": value,
                    "metadata": self.STAT_METADATA[stat_key]
                }
        return result

    def on_hit_calculation(self, event: HitCalculationEvent):
        """
        명중 판정 시 호출

        - 공격자: 명중률 추가
        - 방어자: 회피율 추가
        """
        # 이 컴포넌트가 공격자 소속인지 방어자 소속인지 판단 필요
        # Entity에 passive_skills를 탐색하여 판단해야 함
        # 현재는 단순히 스탯만 제공하는 방식으로 구현
        pass


@register_skill_with_tag("stat_elemental_damage")
class ElementalDamageComponent(SkillComponent):
    """
    속성 데미지 증가 컴포넌트

    특정 속성 데미지를 증가시킵니다.

    Config options:
        fire_damage (float): 화염 데미지 증가
        ice_damage (float): 냉기 데미지 증가
        lightning_damage (float): 번개 데미지 증가
        water_damage (float): 수속성 데미지 증가
        holy_damage (float): 신성 데미지 증가
        dark_damage (float): 암흑 데미지 증가
    """

    STAT_METADATA = {
        "fire_damage": {"label": "화염 공격력", "suffix": "%", "prefix": "+", "is_ratio": False},
        "ice_damage": {"label": "냉기 공격력", "suffix": "%", "prefix": "+", "is_ratio": False},
        "lightning_damage": {"label": "번개 공격력", "suffix": "%", "prefix": "+", "is_ratio": False},
        "water_damage": {"label": "수속성 공격력", "suffix": "%", "prefix": "+", "is_ratio": False},
        "holy_damage": {"label": "신성 공격력", "suffix": "%", "prefix": "+", "is_ratio": False},
        "dark_damage": {"label": "암흑 공격력", "suffix": "%", "prefix": "+", "is_ratio": False},
    }

    # 속성명 매핑
    ATTRIBUTE_MAP = {
        "화염": "fire",
        "냉기": "ice",
        "번개": "lightning",
        "물": "water",
        "신성": "holy",
        "암흑": "dark",
        "불": "fire",
    }

    def __init__(self):
        super().__init__()
        self._raw_config = {}
        self.fire_damage = 0.0
        self.ice_damage = 0.0
        self.lightning_damage = 0.0
        self.water_damage = 0.0
        self.holy_damage = 0.0
        self.dark_damage = 0.0

    def apply_config(self, config, skill_name, priority=0):
        super().apply_config(config, skill_name, priority)
        self._raw_config = config
        self.fire_damage = config.get("fire_damage", 0.0)
        self.ice_damage = config.get("ice_damage", 0.0)
        self.lightning_damage = config.get("lightning_damage", 0.0)
        self.water_damage = config.get("water_damage", 0.0)
        self.holy_damage = config.get("holy_damage", 0.0)
        self.dark_damage = config.get("dark_damage", 0.0)

    def get_displayable_stats(self) -> dict:
        """UI에 표시할 스탯 정보 반환"""
        result = {}
        for stat_key, value in self._raw_config.items():
            if stat_key in self.STAT_METADATA and value > 0:
                result[stat_key] = {
                    "value": value,
                    "metadata": self.STAT_METADATA[stat_key]
                }
        return result

    def on_damage_calculation(self, event: DamageCalculationEvent):
        """
        데미지 계산 시 호출

        - 스킬 속성과 일치하는 속성 데미지 증가 적용
        """
        attr_eng = self.ATTRIBUTE_MAP.get(event.skill_attribute, "")
        if not attr_eng:
            return

        damage_key = f"{attr_eng}_damage"
        damage_bonus = getattr(self, damage_key, 0.0)

        if damage_bonus > 0:
            mult = 1.0 + (damage_bonus / 100)
            event.apply_multiplier(mult, f"🔥 {event.skill_attribute} 강화 (+{int(damage_bonus)}%)")
