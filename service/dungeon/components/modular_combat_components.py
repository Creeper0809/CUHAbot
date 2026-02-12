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
class AttackComponent(SkillComponent):
    """
    순수 공격 컴포넌트 (데미지 계산만)

    치명타, 방어구 관통, 명중 등은 별도 컴포넌트로 처리합니다.

    Config options:
        ad_ratio (float): 물리 공격력 계수 (예: 1.5 = 150% AD)
        ap_ratio (float): 마법 공격력 계수 (예: 1.0 = 100% AP)
        hit_count (int): 타격 횟수 (기본 1)
        is_physical (bool): 물리/마법 데미지 여부 (기본 True)
        aoe (bool): 전체 공격 여부 (기본 False)
    """

    def __init__(self):
        super().__init__()
        self.ad_ratio = 0.0
        self.ap_ratio = 0.0
        self.hit_count = 1
        self.is_physical = True
        self.is_aoe = False

    def apply_config(self, config, skill_name, priority=0):
        super().apply_config(config, skill_name, priority)
        self.ad_ratio = config.get("ad_ratio", 0.0)
        self.ap_ratio = config.get("ap_ratio", 0.0)
        self.hit_count = config.get("hit_count", 1)
        self.is_physical = config.get("is_physical", True)
        self.is_aoe = config.get("aoe", False)

        # 레거시 호환: ad_ratio/ap_ratio 둘 다 없으면 damage를 ad_ratio로 사용
        if self.ad_ratio == 0.0 and self.ap_ratio == 0.0:
            self.ad_ratio = config.get("damage", 1.0)

    def on_turn(self, attacker, target):
        """
        순수 데미지 계산 및 적용

        다른 컴포넌트들(crit, penetration 등)이 이벤트를 통해 개입합니다.
        """
        attacker_stat = attacker.get_stat()
        target_stat = target.get_stat() if hasattr(target, 'get_stat') else {}

        # 기본 공격력 계산
        base_attack = self._calculate_base_attack_power(attacker_stat)

        # 방어력
        defense = self._get_defense(target_stat, target)

        # 속성 배율
        target_attr = getattr(target, 'attribute', '무속성')
        attr_mult = get_attribute_multiplier(self.skill_attribute, target_attr)

        hit_logs = []
        for _ in range(self.hit_count):
            # 1. 명중 판정 이벤트
            hit_event = self._create_hit_event(attacker, target, attacker_stat, target_stat)
            self._fire_hit_calculation_events(attacker, target, hit_event)

            if not hit_event.force_hit:
                final_accuracy = hit_event.get_final_accuracy()
                final_evasion = hit_event.get_final_evasion()
                hit_rate = max(DAMAGE.MIN_HIT_RATE, min(DAMAGE.MAX_HIT_RATE, final_accuracy - final_evasion))

                if random.randint(1, 100) > hit_rate:
                    hit_logs.append(
                        f"⚔️ **{attacker.get_name()}** 「{self.skill_name}」 → "
                        f"**{target.get_name()}** **MISS!**"
                    )
                    continue

            # 2. 데미지 계산 이벤트
            calc_event = DamageCalculationEvent(
                attacker=attacker,
                defender=target,
                base_damage=base_attack,
                skill_name=self.skill_name,
                skill_attribute=self.skill_attribute,
            )

            # 스킬의 다른 컴포넌트들에게 이벤트 전달 (crit, penetration 등)
            self._fire_damage_calculation_events(attacker, target, calc_event)

            # 최종 데미지 계산
            final_damage = calc_event.get_final_damage()

            # 속성 배율 적용
            final_damage = int(final_damage * attr_mult)

            # 방어력 적용 (관통 반영)
            effective_defense = defense * (1 - calc_event.defense_ignore)
            defense_reduction = int(effective_defense * DAMAGE.PHYSICAL_DEFENSE_RATIO if self.is_physical else effective_defense * DAMAGE.MAGICAL_DEFENSE_RATIO)
            final_damage = max(1, final_damage - defense_reduction)

            # 데미지 변동
            final_damage = self._apply_variance(final_damage)

            # 3. 데미지 적용 (파이프라인)
            event = process_incoming_damage(
                target, final_damage, attacker=attacker,
                attribute=self.skill_attribute,
            )

            # 파이프라인 로그 (면역/저항)
            hit_logs.extend(event.extra_logs)

            # 4. 데미지 적용 후 이벤트 (흡혈 등)
            dealt_event = DamageDealtEvent(
                attacker=attacker,
                defender=target,
                damage=event.actual_damage,
                damage_attribute=self.skill_attribute,
                skill_name=self.skill_name,
            )
            self._fire_damage_dealt_events(attacker, dealt_event)

            # 흡혈 로그
            hit_logs.extend(dealt_event.logs)

            # 패시브 흡혈 (장비 + 패시브 스킬의 lifesteal 스탯)
            lifesteal_total = 0
            passive_lifesteal = self._get_passive_lifesteal(attacker)
            if passive_lifesteal > 0 and event.actual_damage > 0:
                max_hp = attacker_stat.get(UserStatEnum.HP, attacker.hp)
                heal = int(event.actual_damage * passive_lifesteal / 100)
                if has_curse_effect(attacker):
                    heal = heal // 2
                old_hp = attacker.now_hp
                attacker.now_hp = min(attacker.now_hp + heal, max_hp)
                actual = attacker.now_hp - old_hp
                if actual > 0:
                    lifesteal_total += actual

            # 공격 로그
            crit_text = " 💥" if calc_event.is_critical else ""
            attr_text = self._get_attribute_text(attr_mult)
            dmg_display = event.actual_damage if not event.was_immune else 0
            lifesteal_text = f" 💚흡혈 +{lifesteal_total}HP" if lifesteal_total > 0 else ""
            hit_logs.append(
                f"⚔️ **{attacker.get_name()}** 「{self.skill_name}」 → "
                f"**{target.get_name()}**에게 {dmg_display} 데미지! {crit_text}{attr_text}{lifesteal_text}"
            )

            # 반사 데미지
            if event.reflected_damage > 0:
                reflect_event = process_incoming_damage(
                    attacker, event.reflected_damage, is_reflected=True,
                )
                hit_logs.append(
                    f"   🔄 반사 데미지 → **{attacker.get_name()}** {reflect_event.actual_damage}"
                )

        return "\n".join(hit_logs)

    def _create_hit_event(self, attacker, target, attacker_stat, target_stat):
        """명중 판정 이벤트 생성"""
        accuracy = attacker_stat.get(UserStatEnum.ACCURACY, DAMAGE.DEFAULT_ACCURACY)
        evasion = target_stat.get(UserStatEnum.EVASION, DAMAGE.DEFAULT_EVASION)

        return HitCalculationEvent(
            attacker=attacker,
            defender=target,
            base_accuracy=accuracy,
            base_evasion=evasion,
        )

    def _fire_hit_calculation_events(self, attacker, target, event: HitCalculationEvent):
        """명중 판정 이벤트 발생 (accuracy_bonus 컴포넌트 등)"""
        # 스킬의 다른 컴포넌트들에게 이벤트 전달
        skill = self._get_current_skill(attacker)
        if skill:
            for comp in skill.components:
                if hasattr(comp, 'on_hit_calculation'):
                    comp.on_hit_calculation(event)

        # 패시브 스킬들에게도 전달
        for passive_skill in self._get_passive_skills(attacker):
            for comp in passive_skill.components:
                if hasattr(comp, 'on_hit_calculation'):
                    comp.on_hit_calculation(event)

    def _fire_damage_calculation_events(self, attacker, target, event: DamageCalculationEvent):
        """데미지 계산 이벤트 발생 (crit, penetration 컴포넌트 등)"""
        # 스킬의 다른 컴포넌트들에게 이벤트 전달
        skill = self._get_current_skill(attacker)
        if skill:
            for comp in skill.components:
                if hasattr(comp, 'on_damage_calculation') and comp != self:
                    comp.on_damage_calculation(event)

        # 패시브 스킬들에게도 전달
        for passive_skill in self._get_passive_skills(attacker):
            for comp in passive_skill.components:
                if hasattr(comp, 'on_damage_calculation'):
                    comp.on_damage_calculation(event)

    def _fire_damage_dealt_events(self, attacker, event: DamageDealtEvent):
        """데미지 적용 후 이벤트 발생 (lifesteal 컴포넌트 등)"""
        # 스킬의 다른 컴포넌트들에게 이벤트 전달
        skill = self._get_current_skill(attacker)
        if skill:
            for comp in skill.components:
                if hasattr(comp, 'on_deal_damage'):
                    comp.on_deal_damage(event)

        # 패시브 스킬들에게도 전달
        for passive_skill in self._get_passive_skills(attacker):
            for comp in passive_skill.components:
                if hasattr(comp, 'on_deal_damage'):
                    comp.on_deal_damage(event)

    def _get_current_skill(self, attacker):
        """현재 실행 중인 스킬 가져오기"""
        # 스킬 이름으로 매칭 (임시 방법)
        skill_ids = getattr(attacker, 'equipped_skill', None) or getattr(attacker, 'use_skill', [])
        if not skill_ids:
            return None

        from models.repos.skill_repo import get_skill_by_id
        for sid in skill_ids:
            skill = get_skill_by_id(sid)
            if skill and skill.name == self.skill_name:
                return skill
        return None

    def _get_passive_skills(self, attacker):
        """패시브 스킬 목록 가져오기"""
        from models.repos.skill_repo import get_skill_by_id

        skill_ids = getattr(attacker, 'equipped_skill', None) or getattr(attacker, 'use_skill', [])
        if not skill_ids:
            return []

        passives = []
        for sid in skill_ids:
            skill = get_skill_by_id(sid)
            if skill and skill.is_passive:
                passives.append(skill)
        return passives

    def _get_passive_lifesteal(self, attacker) -> float:
        """
        장비 + 패시브 스킬에서 흡혈 스탯 추출

        Returns:
            흡혈 비율 (예: 10.0 = 10%)
        """
        total_lifesteal = 0.0

        if hasattr(attacker, '_equipment_components_cache'):
            components = attacker._equipment_components_cache
            for comp in components:
                if getattr(comp, '_tag', '') != "passive_buff":
                    continue
                lifesteal = getattr(comp, 'lifesteal', 0.0)
                if lifesteal:
                    total_lifesteal += lifesteal

        if hasattr(attacker, 'equipped_skill'):
            from service.dungeon.skill import get_passive_stat_bonuses
            passive_bonuses = get_passive_stat_bonuses(attacker.equipped_skill)
            total_lifesteal += passive_bonuses.get('lifesteal', 0.0)

        return total_lifesteal

    def _get_defense(self, target_stat, target) -> int:
        """방어력 가져오기"""
        if self.is_physical:
            return target_stat.get(UserStatEnum.DEFENSE, 0) if target_stat else getattr(target, 'defense', 0)
        return target_stat.get(UserStatEnum.AP_DEFENSE, 0) if target_stat else getattr(target, 'ap_defense', 0)

    def _apply_variance(self, damage: int) -> int:
        """데미지 변동 적용"""
        variance = DAMAGE.DAMAGE_VARIANCE
        multiplier = 1 + random.uniform(-variance, variance)
        return int(damage * multiplier)

    def _get_attribute_text(self, multiplier: float) -> str:
        """속성 효과 텍스트"""
        if multiplier > 1.0:
            return " 🔥"
        elif multiplier < 1.0:
            return " 🌊"
        return ""


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
