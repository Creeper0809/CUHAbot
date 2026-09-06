"""
모듈화된 전투 컴포넌트

기존 DamageComponent를 극도로 모듈화하여 재사용 가능한 컴포넌트로 분리:
- AttackComponent: 순수 데미지 계산
- CriticalComponent: 치명타 판정 및 적용
- PenetrationComponent: 방어구/마법 관통
- AccuracyBonusComponent: 명중률 보너스

이렇게 분리하면 스킬과 패시브가 동일한 컴포넌트를 재사용할 수 있습니다.
"""
import random
from typing import TYPE_CHECKING, Optional

from config import DAMAGE, get_attribute_multiplier
from models import UserStatEnum
from service.dungeon.components.base import SkillComponent, register_skill_with_tag
from service.dungeon.components.attack_components import DamageComponent
from service.dungeon.combat_events import (
    DamageCalculationEvent,
    DamageDealtEvent,
    HitCalculationEvent,
)
from service.dungeon.damage_pipeline import process_incoming_damage
from service.dungeon.status import has_curse_effect

if TYPE_CHECKING:
    from service.dungeon.combat_context import CombatContext


@register_skill_with_tag("attack")
class AttackComponent(DamageComponent):
    """Registered attack path: the shared V2 formula plus authored event hooks.

    The former duplicate implementation subtracted defense per hit, ignored
    natural crit and run augments, and silently replaced DamageComponent during
    registry import. Keeping one formula prevents tests and live CSV skills from
    exercising different combat engines.
    """

    def _call_equipment_event_hooks(self, attacker, event_method_name, event):
        super()._call_equipment_event_hooks(attacker, event_method_name, event)
        from models.repos.skill_repo import get_skill_by_id
        skill = getattr(self, "skill", None)
        skills = [skill] if skill is not None else []
        ids = getattr(attacker, "equipped_skill", None) or getattr(attacker, "use_skill", [])
        for skill_id in set(ids):
            passive = get_skill_by_id(skill_id)
            if passive and passive.is_passive and passive not in skills:
                skills.append(passive)
        for current in skills:
            for component in current.components:
                if component is self:
                    continue
                hook = getattr(component, event_method_name, None)
                if hook:
                    hook(event)


@register_skill_with_tag("crit")
class CriticalComponent(SkillComponent):
    """
    치명타 컴포넌트

    Config options:
        rate (float): 스탯에 영구 추가할 치명타율 (패시브용)
        rate_bonus (float): 이 스킬에서만 추가 판정 (스킬용)
        damage (float): 치명타 배율 보너스 (기본 150% + 보너스)
        force (bool): 확정 치명타
        condition (str): 조건부 확정 치명타 (hp_below_30, target_hp_above_50 등)
    """

    def __init__(self):
        super().__init__()
        self.rate = 0.0  # 스탯 영구 추가 (패시브)
        self.rate_bonus = 0.0  # 스킬 추가 판정
        self.damage = 0.0  # 배율 보너스
        self.force = False  # 확정 치명타
        self.condition = None  # 조건부

    def apply_config(self, config, skill_name, priority=0):
        super().apply_config(config, skill_name, priority)
        self.rate = config.get("rate", 0.0)
        self.rate_bonus = config.get("rate_bonus", 0.0)
        self.damage = config.get("damage", 0.0)
        self.force = config.get("force", False)
        self.condition = config.get("condition", None)

    def on_damage_calculation(self, event: DamageCalculationEvent):
        """
        치명타 판정 (2단계)

        1단계: 스탯 치명타 (이미 외부에서 판정됨)
        2단계: 스킬 자체 치명타 (스탯 실패 시에만)
        """
        # 1단계에서 이미 치명타가 났으면 배율만 추가
        if event.is_critical:
            if self.damage > 0:
                # 현재 배율에 추가 (중복 적용 방지)
                pass
            return

        # 2단계: 스킬 자체 치명타 판정
        if self.force:
            # 확정 치명타 (조건 체크)
            if self._check_condition(event.attacker, event.defender):
                event.is_critical = True
                crit_mult = (150 + self.damage) / 100
                event.apply_multiplier(crit_mult, f"⚡ 확정 치명타! ({int(crit_mult * 100)}%)")
        elif self.rate_bonus > 0:
            # 추가 판정
            if random.random() * 100 < self.rate_bonus:
                event.is_critical = True
                crit_mult = (150 + self.damage) / 100
                event.apply_multiplier(crit_mult, f"⚡ 치명타! ({int(crit_mult * 100)}%)")

    def _check_condition(self, attacker, defender) -> bool:
        """조건부 확정 치명타 체크"""
        if not self.condition:
            return True

        if self.condition == "hp_below_30":
            return attacker.now_hp / attacker.get_stat().get("hp", attacker.hp) < 0.3
        elif self.condition == "hp_below_50":
            return attacker.now_hp / attacker.get_stat().get("hp", attacker.hp) < 0.5
        elif self.condition == "target_hp_above_50":
            target_hp = defender.now_hp / defender.get_stat().get("hp", defender.hp) if hasattr(defender, 'get_stat') else defender.now_hp / defender.hp
            return target_hp > 0.5

        return False


@register_skill_with_tag("penetration")
class PenetrationComponent(SkillComponent):
    """
    방어구/마법 관통 컴포넌트

    Config options:
        armor_pen (float): 물리 방어구 관통 (%)
        magic_pen (float): 마법 관통 (%)
    """

    def __init__(self):
        super().__init__()
        self.armor_pen = 0.0
        self.magic_pen = 0.0

    def apply_config(self, config, skill_name, priority=0):
        super().apply_config(config, skill_name, priority)
        self.armor_pen = config.get("armor_pen", 0.0)
        self.magic_pen = config.get("magic_pen", 0.0)

    def on_damage_calculation(self, event: DamageCalculationEvent):
        """방어구 관통 적용"""
        if self.armor_pen > 0:
            event.ignore_defense(self.armor_pen / 100)
        # magic_pen도 동일하게 처리 (is_physical 체크 필요 시 추가)


@register_skill_with_tag("accuracy_bonus")
class AccuracyBonusComponent(SkillComponent):
    """
    명중률 보너스 컴포넌트

    Config options:
        bonus (float): 명중률 보너스 (%)
        force_hit (bool): 필중
    """

    def __init__(self):
        super().__init__()
        self.bonus = 0.0
        self.force_hit = False

    def apply_config(self, config, skill_name, priority=0):
        super().apply_config(config, skill_name, priority)
        self.bonus = config.get("bonus", 0.0)
        self.force_hit = config.get("force_hit", False)

    def on_hit_calculation(self, event: HitCalculationEvent):
        """명중률 보너스 적용"""
        if self.force_hit:
            event.set_force_hit()
        elif self.bonus > 0:
            event.add_accuracy(self.bonus)
