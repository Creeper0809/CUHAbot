"""
공격 컴포넌트: DamageComponent, LifestealComponent, ConsumeComponent
"""
import random

from config import DAMAGE, get_attribute_multiplier
from models import UserStatEnum
from service.combat.damage_calculator import DamageCalculator
from service.combat.runtime_damage import deal_runtime_damage
from service.dungeon.components.base import SkillComponent, register_skill_with_tag
from service.dungeon.damage_pipeline import process_incoming_damage
from service.dungeon.status import (
    get_status_stacks, get_damage_taken_multiplier, has_curse_effect,
    remove_status_effects,
)
from service.player.stat_synergy_combat import (
    get_hp_conditional_bonuses, get_phys_crit_dmg_bonus, get_attr_dmg_bonus,
)


class DamageComponent(SkillComponent):
    """
    공격 데미지 컴포넌트

    DamageCalculator를 사용하여 방어력, 치명타, 데미지 변동을 적용합니다.
    속성 상성 배율도 자동 적용됩니다.

    Config options:
        ad_ratio (float): 물리 공격력 계수 (예: 1.4 = 140% AD)
        ap_ratio (float): 마법 공격력 계수 (예: 1.0 = 100% AP)
        hit_count (int): 타격 횟수 (기본 1)
        crit_bonus (float): 추가 치명타 확률 (기본 0)
        armor_pen (float): 방어력 무시 비율 (기본 0, 최대 0.7)
        is_physical (bool): 물리/마법 데미지 여부 (기본 True=물리)
        aoe (bool): 전체 공격 여부 (기본 False)
    """

    def __init__(self):
        super().__init__()
        self.damage_multiplier = 1.0
        self.ad_ratio = 0.0
        self.ap_ratio = 0.0
        self.hit_count = 1
        self.crit_bonus = 0.0
        self.armor_penetration = 0.0
        self.is_physical = True
        self.is_aoe = False
        self.target_type = "single"
        self.ignore_defense = False
        self.cannot_evade = False
        self.damage_type = ""
        self.damage_value = 0.0
        self.element = ""
        self.ratio_multiplier = 1.0
        self.bonus_per_debuff = 0.0
        self.guaranteed_crit = False
        self.bonus_vs_dark = 0.0
        self.bonus_vs_holy = 0.0
        self.hp_threshold = None
        self.once_per_battle = False
        self.ignore_all_resistance = False
        self.bonus_type = ""
        self.bonus_ratio = 0.0
        self.ad_ratio_max = None
        self.ap_ratio_max = None
        self.random_ratio = False
        self.self_damage = 0.0
        self.hp_cost = 0.0
        self.charge_turns = 0
        self.interruptible = False
        self._used_entities: set[int] = set()
        self._used_action_serial: dict[int, int] = {}

    def apply_config(self, config, skill_name, priority=0):
        super().apply_config(config, skill_name, priority)
        self.hit_count = config.get("hit_count", 1)
        self.crit_bonus = config.get("crit_bonus", 0.0)
        self.armor_penetration = config.get("armor_pen", 0.0)
        self.is_physical = config.get("is_physical", True)
        self.target_type = str(config.get("target", "single")).lower()
        self.is_aoe = bool(config.get("aoe", False)) or self.target_type in {
            "all",
            "all_enemies",
            "all_enemy",
            "enemies",
        }

        self.ad_ratio = config.get("ad_ratio", 0.0)
        self.ap_ratio = config.get("ap_ratio", 0.0)
        self.ignore_defense = bool(config.get("ignore_defense", False))
        self.cannot_evade = bool(config.get("cannot_evade", False))
        self.damage_type = str(config.get("damage_type", ""))
        self.damage_value = float(config.get("value", 0.0) or 0.0)
        self.element = str(config.get("element", ""))
        self.ratio_multiplier = float(config.get("multiplier", 1.0) or 1.0)
        self.bonus_per_debuff = float(config.get("bonus_per_debuff", 0.0) or 0.0)
        self.guaranteed_crit = bool(config.get("guaranteed_crit", False))
        self.bonus_vs_dark = float(config.get("bonus_vs_dark", 0.0) or 0.0)
        self.bonus_vs_holy = float(config.get("bonus_vs_holy", 0.0) or 0.0)
        self.hp_threshold = config.get("hp_threshold")
        self.once_per_battle = bool(config.get("once_per_battle", False))
        self.ignore_all_resistance = bool(config.get("ignore_all_resistance", False))
        self.bonus_type = str(config.get("bonus_type", ""))
        self.bonus_ratio = float(config.get("bonus_ratio", 0.0) or 0.0)
        self.ad_ratio_max = config.get("ad_ratio_max")
        self.ap_ratio_max = config.get("ap_ratio_max")
        self.random_ratio = bool(config.get("random", False))
        self.self_damage = float(config.get("self_damage", 0.0) or 0.0)
        self.hp_cost = float(config.get("hp_cost", 0.0) or 0.0)
        self.charge_turns = int(config.get("charge_turns", 0) or 0)
        self.interruptible = bool(config.get("interruptible", False))

        # 레거시 호환: ad_ratio/ap_ratio 둘 다 없으면 damage를 ad_ratio로 사용
        if self.ad_ratio == 0.0 and self.ap_ratio == 0.0:
            self.ad_ratio = config.get("damage", 1.0)

    def on_turn(self, attacker, target):
        if self.is_aoe:
            from service.dungeon.components.targeting_utils import resolve_targets

            targets = resolve_targets(attacker, target, self.target_type)
            return "\n".join(
                log for each in targets
                if (log := self._on_target(attacker, each))
            )
        return self._on_target(attacker, target)

    def _on_target(self, attacker, target):
        maximum_hp = attacker.get_stat().get(UserStatEnum.HP, getattr(attacker, "hp", 1))
        if self.hp_threshold is not None and getattr(attacker, "now_hp", maximum_hp) / max(1, maximum_hp) > float(self.hp_threshold):
            return f"⚪ **{attacker.get_name()}** 「{self.skill_name}」 발동 조건 미충족"
        entity_key = id(attacker)
        action_serial = int(getattr(attacker, "_skill_action_serial", 0) or 0)
        if (
            self.once_per_battle
            and entity_key in self._used_entities
            and self._used_action_serial.get(entity_key) != action_serial
        ):
            return f"⚪ **{attacker.get_name()}** 「{self.skill_name}」 전투당 1회 사용 완료"
        if self.once_per_battle:
            self._used_entities.add(entity_key)
            self._used_action_serial[entity_key] = action_serial

        if self.hp_cost > 0 or self.self_damage > 0:
            cost = max(self.hp_cost, self.self_damage)
            attacker.now_hp = max(1, attacker.now_hp - max(1, int(maximum_hp * cost)))

        skill_attribute = self._resolve_attribute()
        if self.damage_type:
            return self._apply_fixed_damage(attacker, target, skill_attribute)

        attacker_stat = attacker.get_stat()
        attack_power = self._calculate_base_attack_power(attacker_stat)
        from service.dungeon.skill import get_passive_effect_bonuses

        passive_effects = get_passive_effect_bonuses(attacker, target=target)
        passive_hit_bonus = max(0.0, float(getattr(attacker, "_passive_hit_bonus", 0.0) or 0.0))
        attack_power = max(1, int(attack_power * (1.0 + passive_hit_bonus)))
        if self.random_ratio:
            ad_ratio = random.uniform(self.ad_ratio, float(self.ad_ratio_max or self.ad_ratio))
            ap_ratio = random.uniform(self.ap_ratio, float(self.ap_ratio_max or self.ap_ratio))
            attack_power = max(
                1,
                int(
                    attacker_stat.get(UserStatEnum.ATTACK, 0) * ad_ratio
                    + attacker_stat.get(UserStatEnum.AP_ATTACK, 0) * ap_ratio
                ),
            )
        attack_power = max(1, int(attack_power * self.ratio_multiplier))

        if self.bonus_per_debuff:
            from service.dungeon.status.base import StatusEffect

            debuffs = sum(
                1 for status in getattr(target, "status", [])
                if isinstance(status, StatusEffect) or getattr(status, "is_debuff", False)
            )
            attack_power = max(1, int(attack_power * (1.0 + self.bonus_per_debuff * debuffs)))
        if self.bonus_type == "target_current_hp":
            attack_power += max(0, int(getattr(target, "now_hp", 0) * self.bonus_ratio))

        target_stat = target.get_stat() if hasattr(target, 'get_stat') else {}
        defense = 0 if self.ignore_defense else self._get_defense(target_stat, target)
        crit_rate = attacker_stat.get(UserStatEnum.CRITICAL_RATE, 5) / 100.0 + self.crit_bonus
        if self.guaranteed_crit:
            crit_rate = 1.0
        target_maximum = max(1, int(target_stat.get(UserStatEnum.HP, getattr(target, "hp", 1))))
        target_ratio = getattr(target, "now_hp", target_maximum) / target_maximum
        execute_crit = passive_effects.get("execute_crit_threshold", 0.0)
        if execute_crit and target_ratio <= execute_crit:
            crit_rate = 1.0
        from service.dungeon.damage_pipeline import has_critical_immunity
        if has_critical_immunity(target):
            crit_rate = 0.0

        # 속성 상성 배율
        target_attr = getattr(target, 'attribute', '무속성')
        attr_mult = get_attribute_multiplier(skill_attribute, target_attr)
        if target_attr == "암흑" and self.bonus_vs_dark:
            attr_mult *= self.bonus_vs_dark
        if target_attr == "신성" and self.bonus_vs_holy:
            attr_mult *= self.bonus_vs_holy
        if passive_effects.get("all_element", 0.0) and skill_attribute not in {"", "무속성", "없음"}:
            attr_mult *= 1.0 + passive_effects["all_element"]
        if skill_attribute == "신성" and passive_effects.get("holy_bonus", 0.0):
            attr_mult *= 1.0 + passive_effects["holy_bonus"]
        if attr_mult > 1.0 and passive_effects.get("weakness_bonus", 0.0):
            attr_mult *= 1.0 + passive_effects["weakness_bonus"]

        # 스탯 시너지: 속성 데미지 보너스 (원소 지배자 등)
        attr_bonus = get_attr_dmg_bonus(attacker)
        if attr_bonus > 0 and attr_mult > 1.0:
            attr_mult += attr_bonus

        # 시너지 배율 (덱 기반)
        synergy_mult = self._get_synergy_multiplier(attacker)

        # 받는 피해 배율 (동결, 표식 등)
        damage_taken_mult = get_damage_taken_multiplier(target)
        synergy_taken_mult = self._get_target_synergy_damage_taken_multiplier(target)
        damage_taken_mult *= synergy_taken_mult

        # 스탯 시너지: HP 조건부 보너스 (광전사 등)
        hp_bonuses = get_hp_conditional_bonuses(attacker)
        hp_dmg_bonus = 1.0 + hp_bonuses.get("phys_dmg_pct", 0) / 100

        # 스탯 시너지: 불멸의 요새 (대상의 HP 조건부 방어력 배수)
        if hasattr(target, 'bonus_str'):
            target_hp_bonuses = get_hp_conditional_bonuses(target)
            target_def_mult = target_hp_bonuses.get("def_mult", 0)
            if target_def_mult > 0:
                defense = int(defense * target_def_mult)

        # 장비: 스킬 데미지 증폭 (장비 패시브)
        from service.dungeon.equipment_skill_modifier import get_equipment_skill_damage_multiplier_sync
        equipment_skill_mult = get_equipment_skill_damage_multiplier_sync(attacker, skill=self.skill, target=target)

        combined_mult = attr_mult * synergy_mult * damage_taken_mult * hp_dmg_bonus * equipment_skill_mult
        combined_mult *= 1.0 + max(0.0, passive_effects.get("damage_bonus", 0.0))
        maximum_hp = max(1, int(attacker_stat.get(UserStatEnum.HP, getattr(attacker, "hp", 1))))
        actor_ratio = getattr(attacker, "now_hp", maximum_hp) / maximum_hp
        low_threshold = passive_effects.get("low_hp_threshold", 0.0) or 0.20
        if actor_ratio <= low_threshold:
            combined_mult *= 1.0 + max(0.0, passive_effects.get("low_hp_bonus", 0.0))
        execute_threshold = passive_effects.get("execute_threshold", 0.0)
        if execute_threshold and target_ratio <= execute_threshold:
            combined_mult *= 1.0 + max(0.0, passive_effects.get("execute_bonus", 0.0))
        runtime_modifier = getattr(attacker, "modifier_bundle", None)
        runtime_penetration = 0.0
        if runtime_modifier is not None:
            combined_mult *= 1.0 + (
                runtime_modifier.physical_damage_pct
                if self.is_physical else runtime_modifier.magical_damage_pct
            )
            attribute_bonus = {
                "화염": runtime_modifier.fire_damage_pct,
                "냉기": runtime_modifier.ice_damage_pct,
                "물": runtime_modifier.water_damage_pct,
                "번개": runtime_modifier.lightning_damage_pct,
                "신성": runtime_modifier.holy_damage_pct,
                "암흑": runtime_modifier.dark_damage_pct,
            }.get(skill_attribute, 0.0)
            combined_mult *= 1.0 + attribute_bonus
            runtime_penetration = (
                runtime_modifier.armor_penetration
                if self.is_physical else runtime_modifier.magic_penetration
            )
        combined_mult *= float(getattr(attacker, "_roguelike_effect_multiplier", 1.0) or 1.0)
        # 궁극기 자동 발동 페널티(수동 대비 약화) 적용
        ultimate_scale = float(getattr(attacker, "_ultimate_damage_scale", 1.0) or 1.0)
        combined_mult *= ultimate_scale

        # 스탯 시너지: 물리 치명타 데미지 보너스 (파괴자)
        crit_mult = attacker_stat.get(UserStatEnum.CRITICAL_DAMAGE, 150) / 100.0
        if self.is_physical:
            crit_mult += get_phys_crit_dmg_bonus(attacker)

        hit_logs = []
        for _ in range(self.hit_count):
            lifesteal_total = 0
            # 명중 판정 전: 이벤트 기반 컴포넌트 적용
            from service.dungeon.combat_events import HitCalculationEvent

            base_accuracy = attacker_stat.get(UserStatEnum.ACCURACY, DAMAGE.DEFAULT_ACCURACY)
            base_evasion = target_stat.get(UserStatEnum.EVASION, DAMAGE.DEFAULT_EVASION)

            hit_calc_event = HitCalculationEvent(
                attacker=attacker,
                defender=target,
                base_accuracy=base_accuracy,
                base_evasion=base_evasion,
            )

            # 장비 컴포넌트의 on_hit_calculation() 호출
            self._call_equipment_event_hooks(attacker, 'on_hit_calculation', hit_calc_event)
            for component in getattr(target, '_equipment_components_cache', []) or []:
                if getattr(component, '_tag', '') == 'action_prediction':
                    hit_calc_event.add_evasion(component.get_evasion_bonus() * 100.0)

            # 명중 판정 (이벤트에서 수정된 값 사용)
            final_accuracy = hit_calc_event.get_final_accuracy()
            final_evasion = hit_calc_event.get_final_evasion()

            from service.combat.damage_calculator import DamageCalculator
            hit_success = self.cannot_evade or DamageCalculator.roll_hit(final_accuracy, final_evasion) or hit_calc_event.force_hit

            if not hit_success:
                hit_logs.append(
                    f"⚔️ **{attacker.get_name()}** 「{self.skill_name}」 → "
                    f"**{target.get_name()}** **MISS!**"
                )
                continue

            # 데미지 계산 전: 이벤트 기반 컴포넌트 적용
            from service.dungeon.combat_events import DamageCalculationEvent, DamageDealtEvent

            base_damage = attack_power  # 기본 공격력을 기준으로
            damage_calc_event = DamageCalculationEvent(
                attacker=attacker,
                defender=target,
                base_damage=base_damage,
                skill_name=self.skill_name,
                skill_attribute=skill_attribute,
            )

            # 장비 컴포넌트의 on_damage_calculation() 호출
            self._call_equipment_event_hooks(attacker, 'on_damage_calculation', damage_calc_event)

            event_multiplier = damage_calc_event.get_final_damage() / max(1, damage_calc_event.base_damage)
            final_combined_mult = combined_mult * event_multiplier
            total_penetration = min(
                DAMAGE.MAX_ARMOR_PENETRATION,
                self.armor_penetration + runtime_penetration + damage_calc_event.defense_ignore,
            )

            # 기존 데미지 계산 (DamageCalculator 사용)
            result = self._calculate_hit(
                attack_power, defense, crit_rate, final_combined_mult, crit_mult,
                penetration=total_penetration,
            )
            hit_logs.extend(damage_calc_event.logs)

            was_alive = getattr(target, "now_hp", 0) > 0
            event = process_incoming_damage(
                target, result.damage, attacker=attacker,
                attribute=skill_attribute,
                ignore_resistance=self.ignore_all_resistance,
            )

            if was_alive and getattr(target, "now_hp", 1) <= 0 and passive_effects.get("kill_heal", 0.0):
                before = attacker.now_hp
                attacker.now_hp = min(
                    maximum_hp,
                    attacker.now_hp + int(maximum_hp * passive_effects["kill_heal"]),
                )
                if attacker.now_hp > before:
                    hit_logs.append(f"💚 **{attacker.get_name()}** 처치 회복 +{attacker.now_hp - before} HP")

            if event.actual_damage > 0:
                for status in getattr(attacker, "status", []):
                    record_hit = getattr(status, "record_hit", None)
                    if callable(record_hit):
                        record_hit()
                per_hit = max(0.0, passive_effects.get("hit_stack_attack", 0.0))
                if per_hit:
                    maximum_stack = max(per_hit, passive_effects.get("hit_stack_max", 0.0) or per_hit * 10)
                    attacker._passive_hit_bonus = min(
                        maximum_stack,
                        float(getattr(attacker, "_passive_hit_bonus", 0.0) or 0.0) + per_hit,
                    )

                from service.dungeon.status import apply_status_effect
                for effect_type, chance_key in (
                    ("poison", "poison_chance"),
                    ("slow", "slow_chance"),
                    ("paralyze", "paralyze_chance"),
                ):
                    chance = max(0.0, min(1.0, passive_effects.get(chance_key, 0.0)))
                    if chance and random.random() < chance:
                        payload = None
                        if effect_type == "poison" and passive_effects.get("poison_damage", 0.0):
                            payload = {"damage_bonus": passive_effects["poison_damage"]}
                        proc_log = apply_status_effect(
                            target,
                            effect_type,
                            duration=3 if effect_type != "paralyze" else 1,
                            source=attacker,
                            effect_config=payload,
                        )
                        if proc_log:
                            hit_logs.append(proc_log)

            # 파이프라인 추가 로그 (면역/보호막/저항)
            hit_logs.extend(event.extra_logs)

            # 데미지 적용 후: on_deal_damage 이벤트 호출
            deal_damage_event = DamageDealtEvent(
                attacker=attacker,
                defender=target,
                damage=event.actual_damage,
                damage_attribute=skill_attribute,
                skill_name=self.skill_name,
            )
            self._call_equipment_event_hooks(attacker, 'on_deal_damage', deal_damage_event)
            hit_logs.extend(deal_damage_event.logs)

            # 스탯 시너지: HP 조건부 흡혈 (광전사)
            lifesteal_pct = hp_bonuses.get("lifesteal_pct", 0)
            if lifesteal_pct > 0 and event.actual_damage > 0:
                max_hp = attacker_stat.get(UserStatEnum.HP, attacker.hp)
                heal = int(event.actual_damage * lifesteal_pct / 100)
                old_hp = attacker.now_hp
                attacker.now_hp = min(attacker.now_hp + heal, max_hp)
                actual = attacker.now_hp - old_hp
                if actual > 0:
                    lifesteal_total += actual

            # 패시브 흡혈 (장비 + 패시브 스킬의 lifesteal 스탯)
            passive_lifesteal = self._get_passive_lifesteal(attacker)
            if passive_lifesteal > 0 and event.actual_damage > 0:
                max_hp = attacker_stat.get(UserStatEnum.HP, attacker.hp)
                heal = int(event.actual_damage * passive_lifesteal)
                old_hp = attacker.now_hp
                attacker.now_hp = min(attacker.now_hp + heal, max_hp)
                actual = attacker.now_hp - old_hp
                if actual > 0:
                    lifesteal_total += actual

            crit_text = " 💥" if result.is_critical else ""
            attr_text = _get_attribute_effectiveness_text(attr_mult)
            dmg_type_text = _get_damage_type_text(self.is_physical, self.skill_attribute)
            dmg_display = event.actual_damage if not event.was_immune else 0
            lifesteal_text = f" 💚흡혈 +{lifesteal_total}HP" if lifesteal_total > 0 else ""
            hit_logs.append(
                f"⚔️ **{attacker.get_name()}** 「{self.skill_name}」 → "
                f"**{target.get_name()}** {dmg_display}💥{crit_text}{attr_text}{dmg_type_text}{lifesteal_text}"
            )

            # 반사 데미지 처리
            if event.reflected_damage > 0 and attacker:
                reflect_event = process_incoming_damage(
                    attacker, event.reflected_damage, is_reflected=True,
                )
                hit_logs.append(
                    f"   🔄 반사 데미지 → **{attacker.get_name()}** {reflect_event.actual_damage}"
                )

        return "\n".join(hit_logs)

    def _resolve_attribute(self) -> str:
        mapping = {
            "fire": "화염", "ice": "냉기", "lightning": "번개", "water": "수속성",
            "holy": "신성", "dark": "암흑",
        }
        if self.element == "random_fire_lightning":
            return random.choice(["화염", "번개"])
        if self.element == "random":
            return random.choice(["화염", "냉기", "번개", "수속성", "신성", "암흑"])
        return mapping.get(self.element, self.skill_attribute)

    def _apply_fixed_damage(self, attacker, target, attribute: str) -> str:
        if not self.cannot_evade:
            attacker_stat = attacker.get_stat()
            target_stat = target.get_stat()
            if not DamageCalculator.roll_hit(
                attacker_stat.get(UserStatEnum.ACCURACY, DAMAGE.DEFAULT_ACCURACY),
                target_stat.get(UserStatEnum.EVASION, DAMAGE.DEFAULT_EVASION),
            ):
                return f"⚔️ **{attacker.get_name()}** 「{self.skill_name}」 → **{target.get_name()}** **MISS!**"

        target_stats = target.get_stat()
        maximum = max(1, int(target_stats.get(UserStatEnum.HP, getattr(target, "hp", 1))))
        if self.damage_type == "instant_kill":
            raw = max(1, getattr(target, "now_hp", 1))
        elif self.damage_type == "current_hp_percent":
            raw = max(1, int(max(1, getattr(target, "now_hp", 1)) * self.damage_value))
        elif self.damage_type == "max_hp_percent":
            raw = max(1, int(maximum * self.damage_value))
        else:
            raw = max(1, int(self.damage_value))
        event = process_incoming_damage(
            target,
            raw,
            attacker=attacker,
            attribute=attribute,
            ignore_resistance=True,
            ignore_mitigation=True,
        )
        return (
            f"⚔️ **{attacker.get_name()}** 「{self.skill_name}」 → "
            f"**{target.get_name()}** {event.actual_damage} 고정 피해"
        )

    def _get_passive_lifesteal(self, attacker) -> float:
        """
        장비 + 패시브 스킬에서 흡혈 스탯 추출

        Returns:
            흡혈 비율 (예: 10.0 = 10%)
        """
        total_lifesteal = 0.0

        # 1. 장비 컴포넌트에서 흡혈
        if hasattr(attacker, '_equipment_components_cache'):
            components = attacker._equipment_components_cache
            for comp in components:
                tag = getattr(comp, '_tag', '')
                if tag == "passive_buff":
                    lifesteal = getattr(comp, 'lifesteal', 0.0)
                    total_lifesteal += lifesteal / 100.0 if abs(lifesteal) > 1 else lifesteal

        # 2. 패시브 스킬에서 흡혈
        if hasattr(attacker, 'equipped_skill'):
            from service.dungeon.skill import get_passive_stat_bonuses
            from service.skill.synergy_service import SynergyService
            passive_bonuses = get_passive_stat_bonuses(attacker.equipped_skill)
            total_lifesteal += passive_bonuses.get('lifesteal', 0.0)
            total_lifesteal += SynergyService.calculate_lifesteal_bonus(attacker.equipped_skill)

        return min(1.0, max(0.0, total_lifesteal))

    def _call_equipment_event_hooks(self, attacker, event_method_name: str, event):
        """
        장비 컴포넌트의 이벤트 훅 호출

        Args:
            attacker: 공격자
            event_method_name: 호출할 메서드 이름 (예: "on_damage_calculation")
            event: 이벤트 객체
        """
        if not hasattr(attacker, '_equipment_components_cache'):
            return

        components = attacker._equipment_components_cache
        for comp in components:
            if hasattr(comp, event_method_name):
                method = getattr(comp, event_method_name)
                try:
                    method(event)
                except Exception as e:
                    # 에러 발생 시 로깅만 하고 계속 진행
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Error calling {event_method_name} on {comp.__class__.__name__}: {e}", exc_info=True)

    def _get_defense(self, target_stat, target) -> int:
        if self.is_physical:
            return target_stat.get(UserStatEnum.DEFENSE, 0) if target_stat else getattr(target, 'defense', 0)
        return target_stat.get(UserStatEnum.AP_DEFENSE, 0) if target_stat else getattr(target, 'ap_defense', 0)

    def _get_synergy_multiplier(self, attacker) -> float:
        if not hasattr(attacker, 'equipped_skill'):
            return 1.0
        from service.skill.synergy_service import SynergyService
        return SynergyService.calculate_damage_multiplier(
            attacker.equipped_skill, self.skill_attribute, actor=attacker, current_skill=self.skill
        )

    def _get_target_synergy_damage_taken_multiplier(self, target) -> float:
        if not hasattr(target, 'equipped_skill'):
            return 1.0
        from service.skill.synergy_service import SynergyService
        return SynergyService.calculate_damage_taken_multiplier(target.equipped_skill)

    def _calculate_hit(
        self, attack_power, defense, crit_rate, attribute_multiplier,
        critical_multiplier=None, penetration=None,
    ):
        crit_mult = critical_multiplier or DAMAGE.CRITICAL_MULTIPLIER
        actual_penetration = self.armor_penetration if penetration is None else penetration
        if self.is_physical:
            return DamageCalculator.calculate_physical_damage(
                attack=attack_power, defense=defense,
                skill_multiplier=1.0, armor_penetration=actual_penetration,
                critical_rate=crit_rate, attribute_multiplier=attribute_multiplier,
                critical_multiplier=crit_mult,
            )
        return DamageCalculator.calculate_magical_damage(
            ap_attack=attack_power, ap_defense=defense,
            skill_multiplier=1.0, magic_penetration=actual_penetration,
            critical_rate=crit_rate, attribute_multiplier=attribute_multiplier,
            critical_multiplier=crit_mult,
        )


@register_skill_with_tag("lifesteal")
class LifestealComponent(SkillComponent):
    """생명력 흡수 컴포넌트 - 데미지 + 흡혈"""

    def __init__(self):
        super().__init__()
        self.ad_ratio = 1.0
        self.ap_ratio = 0.0
        self.lifesteal = 0.3
        self.hit_count = 1
        self.crit_bonus = 0.0
        self.armor_penetration = 0.0
        self.is_physical = True

    def apply_config(self, config, skill_name, priority=0):
        super().apply_config(config, skill_name, priority)
        self.ad_ratio = config.get("ad_ratio", 0.0)
        self.ap_ratio = config.get("ap_ratio", 0.0)
        self.lifesteal = config.get("lifesteal", config.get("ratio", 0.3))
        self.hit_count = config.get("hit_count", 1)
        self.crit_bonus = config.get("crit_bonus", 0.0)
        self.armor_penetration = config.get("armor_pen", 0.0)
        self.is_physical = config.get("is_physical", True)

        if self.ad_ratio == 0.0 and self.ap_ratio == 0.0:
            self.ad_ratio = config.get("damage", 1.0)

    def on_turn(self, attacker, target):
        attacker_stat = attacker.get_stat()
        from service.dungeon.skill import get_passive_effect_bonuses

        passive_effects = get_passive_effect_bonuses(attacker, target=target)
        attack_power = self._calculate_base_attack_power(attacker_stat)
        attack_power *= float(getattr(attacker, "_roguelike_effect_multiplier", 1.0) or 1.0)
        max_hp = attacker_stat.get(UserStatEnum.HP, attacker.hp)

        target_stat = target.get_stat() if hasattr(target, 'get_stat') else {}
        defense = self._get_defense(target_stat, target)
        crit_rate = attacker_stat.get(UserStatEnum.CRITICAL_RATE, 5) / 100.0 + self.crit_bonus

        # 속성 배율
        target_attr = getattr(target, 'attribute', '무속성')
        attr_mult = get_attribute_multiplier(self.skill_attribute, target_attr)
        damage_taken_mult = get_damage_taken_multiplier(target)

        hit_logs = []
        total_damage = 0

        for _ in range(self.hit_count):
            # 명중 판정
            if not self._roll_hit(attacker_stat, target_stat):
                hit_logs.append(
                    f"🩸 **{attacker.get_name()}** 「{self.skill_name}」 → "
                    f"**{target.get_name()}** **MISS!**"
                )
                continue

            result = self._calculate_hit(
                attack_power,
                defense,
                crit_rate,
                attr_mult * damage_taken_mult,
                attacker_stat.get(UserStatEnum.CRITICAL_DAMAGE, 150) / 100.0,
            )

            was_alive = getattr(target, "now_hp", 0) > 0
            event = process_incoming_damage(
                target, result.damage, attacker=attacker,
                attribute=self.skill_attribute,
            )
            total_damage += event.actual_damage

            if was_alive and getattr(target, "now_hp", 1) <= 0 and passive_effects.get("kill_heal", 0.0):
                maximum = attacker_stat.get(UserStatEnum.HP, getattr(attacker, "hp", 1))
                before = attacker.now_hp
                attacker.now_hp = min(maximum, attacker.now_hp + int(maximum * passive_effects["kill_heal"]))
                if attacker.now_hp > before:
                    hit_logs.append(f"💚 **{attacker.get_name()}** 처치 회복 +{attacker.now_hp - before} HP")

            hit_logs.extend(event.extra_logs)

            crit_text = " 💥" if result.is_critical else ""
            dmg_type_text = _get_damage_type_text(self.is_physical, self.skill_attribute)
            dmg_display = event.actual_damage if not event.was_immune else 0
            hit_logs.append(
                f"🩸 **{attacker.get_name()}** 「{self.skill_name}」 → "
                f"**{target.get_name()}** {dmg_display}💥{crit_text}{dmg_type_text}"
            )

            if event.reflected_damage > 0 and attacker:
                reflect_event = process_incoming_damage(
                    attacker, event.reflected_damage, is_reflected=True,
                )
                hit_logs.append(
                    f"   🔄 반사 데미지 → **{attacker.get_name()}** {reflect_event.actual_damage}"
                )

        actual_heal = self._apply_lifesteal(attacker, total_damage, max_hp)
        if actual_heal > 0:
            if hit_logs:
                hit_logs[-1] += f" 💚흡혈 +{actual_heal}HP"
            else:
                hit_logs.append(f"💚 흡혈 회복: **+{actual_heal}** HP")

        return "\n".join(hit_logs)

    def _get_defense(self, target_stat, target) -> int:
        if self.is_physical:
            return target_stat.get(UserStatEnum.DEFENSE, 0) if target_stat else getattr(target, 'defense', 0)
        return target_stat.get(UserStatEnum.AP_DEFENSE, 0) if target_stat else getattr(target, 'ap_defense', 0)

    def _calculate_hit(self, attack_power, defense, crit_rate, attribute_multiplier, critical_multiplier):
        if self.is_physical:
            return DamageCalculator.calculate_physical_damage(
                attack=attack_power, defense=defense,
                skill_multiplier=1.0, armor_penetration=self.armor_penetration,
                critical_rate=crit_rate, attribute_multiplier=attribute_multiplier,
                critical_multiplier=critical_multiplier,
            )
        return DamageCalculator.calculate_magical_damage(
            ap_attack=attack_power, ap_defense=defense,
            skill_multiplier=1.0, magic_penetration=self.armor_penetration,
            critical_rate=crit_rate, attribute_multiplier=attribute_multiplier,
            critical_multiplier=critical_multiplier,
        )

    def _apply_lifesteal(self, attacker, total_damage: int, max_hp: int) -> int:
        heal_amount = int(total_damage * self.lifesteal)
        if has_curse_effect(attacker):
            heal_amount = heal_amount // 2

        old_hp = attacker.now_hp
        attacker.now_hp = min(attacker.now_hp + heal_amount, max_hp)
        return attacker.now_hp - old_hp


@register_skill_with_tag("consume")
class ConsumeComponent(SkillComponent):
    """
    상태이상 소모 컴포넌트 - 스택 소모 후 추가 데미지

    Config options:
        consume_type (str): 소모할 상태이상 타입
        per_stack_ratio (float): 레거시 - 스택당 추가 데미지 비율
        ad_ratio (float): 스택당 물리 공격력 계수
        ap_ratio (float): 스택당 마법 공격력 계수
        base_damage (int): 스택과 관계없는 기본 고정 데미지
        is_physical (bool): 물리/마법 데미지 여부 (방어력 적용)
    """

    def __init__(self):
        super().__init__()
        self.consume_type = ""
        self.per_stack_ratio = 0.0
        self.ad_ratio = 0.0
        self.ap_ratio = 0.0
        self.base_damage = 0
        self.is_physical = True
        self.bonus_per_turn = 0.0

    def apply_config(self, config, skill_name, priority=0):
        super().apply_config(config, skill_name, priority)
        self.consume_type = config.get("consume_type", "")
        self.per_stack_ratio = config.get("per_stack_ratio", 0.0)
        self.ad_ratio = config.get("ad_ratio", 0.0)
        self.ap_ratio = config.get("ap_ratio", 0.0)
        self.base_damage = config.get("base_damage", 0)
        self.is_physical = config.get("is_physical", True)
        self.bonus_per_turn = float(config.get("bonus_per_turn", 0.0) or 0.0)

    def on_turn(self, attacker, target):
        if not self.consume_type:
            return ""

        if self.consume_type == "buff_duration":
            consumable = [
                status for status in getattr(target, "status", [])
                if not getattr(status, "is_debuff", False) and getattr(status, "duration", 0) > 0
            ]
            stacks = sum(int(status.duration) for status in consumable)
            for status in consumable:
                target.status.remove(status)
        elif self.consume_type == "shield":
            consumable = [
                status for status in getattr(target, "status", [])
                if getattr(status, "buff_type", "") == "shield"
            ]
            stacks = len(consumable)
            for status in consumable:
                target.status.remove(status)
        else:
            stacks = get_status_stacks(target, self.consume_type)
        if stacks == 0:
            return ""

        # 스택 소모
        if self.consume_type not in {"buff_duration", "shield"}:
            remove_status_effects(target, count=99, filter_type=self.consume_type)

        bonus_damage = self._calculate_consume_damage(attacker, stacks)
        event = deal_runtime_damage(
            attacker, target, bonus_damage,
            is_physical=self.is_physical,
            attribute=self.skill_attribute,
        ).event
        dmg_type_text = _get_damage_type_text(self.is_physical, self.skill_attribute)
        logs = list(event.extra_logs)
        from utils.game_text import status_label
        logs.append(
            f"💥 **{attacker.get_name()}** 「{self.skill_name}」 → **{target.get_name()}** "
            f"{status_label(self.consume_type)} x{stacks} 소모 {event.actual_damage} 추가 데미지!{dmg_type_text}"
        )
        return "\n".join(logs)

    def _calculate_consume_damage(self, attacker, stacks: int) -> int:
        attacker_stat = attacker.get_stat()
        ad = attacker_stat.get(UserStatEnum.ATTACK, 0)
        ap = attacker_stat.get(UserStatEnum.AP_ATTACK, 0)

        # 새 방식: ad_ratio + ap_ratio 별도 계산
        if self.ad_ratio > 0 or self.ap_ratio > 0:
            bonus = self.base_damage
            bonus += int(stacks * self.ad_ratio * ad)
            bonus += int(stacks * self.ap_ratio * ap)
        # 레거시 방식: per_stack_ratio
        else:
            bonus = int(stacks * self.per_stack_ratio * max(ap, ad))

        if self.bonus_per_turn > 0:
            bonus += int(stacks * self.bonus_per_turn * max(ap, ad))

        return max(1, bonus)

def _get_attribute_effectiveness_text(attr_mult: float) -> str:
    if attr_mult > 1.0:
        return " 🔺효과적!"
    if attr_mult < 1.0:
        return " 🔻비효과적..."
    return ""


@register_skill_with_tag("self_damage")
class SelfDamageComponent(SkillComponent):
    """
    자해 컴포넌트 - 자신의 HP를 소모

    공격이나 버프와 함께 사용되어 자신의 HP를 소모하는 효과입니다.
    주로 강력한 효과의 대가로 HP를 지불합니다.

    Config options:
        hp_cost (float): 소모할 HP 비율 (예: 0.2 = 최대 HP의 20%)
        fixed_cost (int): 고정 HP 소모량 (hp_cost와 중복 사용 가능)
    """

    def __init__(self):
        super().__init__()
        self.hp_cost = 0.0
        self.fixed_cost = 0

    def apply_config(self, config, skill_name, priority=0):
        super().apply_config(config, skill_name, priority)
        self.hp_cost = config.get("hp_cost", 0.0)
        self.fixed_cost = config.get("fixed_cost", 0)

    def on_turn(self, attacker, target):
        max_hp = attacker.get_stat().get(UserStatEnum.HP, attacker.hp)

        # HP 소모량 계산
        hp_loss = self.fixed_cost
        if self.hp_cost > 0:
            hp_loss += int(max_hp * self.hp_cost)

        if hp_loss == 0:
            return ""

        # HP 소모 (최소 1 HP는 남김)
        old_hp = attacker.now_hp
        attacker.now_hp = max(1, attacker.now_hp - hp_loss)
        actual_loss = old_hp - attacker.now_hp

        if actual_loss == 0:
            return ""

        return (
            f"💔 **{attacker.get_name()}** 「{self.skill_name}」 HP 소모: "
            f"-{actual_loss} (남은 HP: {attacker.now_hp}/{max_hp})"
        )


def _get_attribute_effectiveness_text(attr_mult: float) -> str:
    if attr_mult > 1.0:
        return " 🔺효과적!"
    if attr_mult < 1.0:
        return " 🔻비효과적..."
    return ""


def _get_damage_type_text(is_physical: bool, skill_attribute: str) -> str:
    dmg_kind = "물리" if is_physical else "마법"
    attr = skill_attribute or ""
    if attr and attr != "무속성":
        return f" ({dmg_kind}/{attr})"
    return f" ({dmg_kind})"
