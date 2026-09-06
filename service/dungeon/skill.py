PASSIVE_TAGS = {
    # Phase 1
    "passive_buff", "passive_regen", "conditional_passive",
    # Phase 2 - 방어
    "passive_element_immunity", "passive_element_resistance",
    "passive_damage_reflection", "passive_status_immunity",
    # Phase 2 - 특수
    "passive_revive", "passive_turn_scaling", "passive_debuff_reduction",
    "on_death_summon",  # 사망 시 소환
    # Phase 2 - 오라
    "passive_aura_buff", "passive_aura_debuff",
}

# Every key accepted by PassiveBuffComponent must have a named consumer.  The
# exhaustive audit imports this set and fails when authored data introduces an
# effect without extending the runtime deliberately.
PASSIVE_EFFECT_KEYS = {
    "attack_percent", "ap_attack_percent", "hp_percent", "defense_percent",
    "speed_percent", "evasion_percent", "evasion", "crit_rate", "crit_damage",
    "lifesteal", "drop_rate", "poison_chance", "poison_damage", "slow_chance",
    "paralyze_chance", "execute_bonus", "execute_threshold", "double_cast",
    "regen_percent", "status_resist", "low_hp_bonus", "low_hp_threshold",
    "weakness_bonus", "death_resist", "hit_stack_attack", "hit_stack_max",
    "all_element", "execute_crit_threshold", "rare_drop", "gold_bonus",
    "exp_bonus", "chest_find", "material_double", "grade_up_chance",
    "grade_up2_chance", "trap_detect", "trap_damage_reduce", "secret_find",
    "ambush_reduce", "foresight", "shop_discount", "sell_bonus", "shop_rare",
    "enhance_luck", "buff_duration", "debuff_duration", "heal_seal",
    "skill_bonus", "low_hp_skill_bonus", "all_resist", "all_stats", "cc_immune",
    "kill_heal", "holy_bonus", "revive", "damage_reduce", "condition",
    "attack_bonus", "damage_bonus", "invincible_turns",
}


def is_passive_skill(skill_id: int) -> bool:
    """스킬 ID로 패시브 여부 판별"""
    from models.repos.skill_repo import get_skill_by_id
    skill = get_skill_by_id(skill_id)
    if not skill:
        return False
    return skill.is_passive


def get_passive_stat_bonuses(skill_ids: list[int]) -> dict:
    """
    passive_buff 컴포넌트의 스탯 보너스 합산 반환

    Returns:
        {"attack_percent": 0.0, "defense_percent": 0.0, "speed_percent": 0.0,
         "hp_percent": 0.0, "evasion_percent": 0.0, "ap_attack_percent": 0.0,
         "crit_rate": 0.0}
    """
    from models.repos.skill_repo import get_skill_by_id

    totals = {
        "attack_percent": 0.0,
        "defense_percent": 0.0,
        "speed_percent": 0.0,
        "hp_percent": 0.0,
        "evasion_percent": 0.0,
        "ap_attack_percent": 0.0,
        "crit_rate": 0.0,
        "crit_damage": 0.0,
        "lifesteal": 0.0,
        "drop_rate": 0.0,
    }

    from config import BALANCE_V2

    seen = set()
    family_counts = {key: 0 for key in totals}
    for sid in skill_ids:
        if sid == 0 or sid in seen:
            continue
        seen.add(sid)

        skill = get_skill_by_id(sid)
        if not skill or not skill.is_passive:
            continue

        for comp in skill.components:
            tag = getattr(comp, '_tag', '')
            if tag != "passive_buff":
                continue
            for key in totals:
                value = getattr(comp, key, 0.0)
                if not value:
                    continue
                family_counts[key] += 1
                totals[key] += value * BALANCE_V2.passive_stack_efficiency(family_counts[key])

    return totals


def get_passive_effect_bonuses(entity_or_ids, *, target=None) -> dict[str, float]:
    """Return all authored passive values after duplicate/family diminishing.

    ``entity_or_ids`` may be an entity or a raw deck. Conditional passives are
    evaluated only when an entity is supplied, keeping stat previews stable and
    combat checks accurate.
    """
    from config import BALANCE_V2
    from models.repos.skill_repo import get_skill_by_id

    entity = None if isinstance(entity_or_ids, (list, tuple, set)) else entity_or_ids
    skill_ids = (
        list(entity_or_ids)
        if entity is None
        else list(getattr(entity, "equipped_skill", None) or getattr(entity, "use_skill", []) or [])
    )
    totals: dict[str, float] = {key: 0.0 for key in PASSIVE_EFFECT_KEYS if key != "condition"}
    family_counts: dict[str, int] = {key: 0 for key in totals}
    seen: set[int] = set()

    for skill_id in skill_ids:
        if not skill_id or skill_id in seen:
            continue
        seen.add(skill_id)
        skill = get_skill_by_id(skill_id)
        if not skill or not skill.is_passive:
            continue
        for component in skill.components:
            if getattr(component, "_tag", "") != "passive_buff":
                continue
            config = dict(getattr(component, "_raw_config", {}) or {})
            if not _passive_condition_matches(entity, target, str(config.get("condition", ""))):
                continue
            for key in totals:
                value = config.get(key, 0.0)
                if isinstance(value, bool):
                    value = float(value)
                if not isinstance(value, (int, float)) or not value:
                    continue
                family_counts[key] += 1
                totals[key] += float(value) * BALANCE_V2.passive_stack_efficiency(family_counts[key])
    return totals


def _passive_condition_matches(entity, target, condition: str) -> bool:
    if not condition or entity is None:
        return True
    maximum = max(1, int(getattr(entity, "hp", 1) or 1))
    ratio = float(getattr(entity, "now_hp", maximum)) / maximum
    if condition == "hp_full":
        return ratio >= 0.999
    if condition == "hp_below_30":
        return ratio <= 0.30
    if condition == "hp_below_10":
        return ratio <= 0.10
    if condition == "solo":
        return int(getattr(entity, "_party_size", 1) or 1) <= 1
    if condition == "vs_boss":
        raw_type = getattr(getattr(target, "type", None), "value", getattr(target, "type", ""))
        return raw_type in {"BossMob", "RadeMob"}
    return False


class Skill:
    def __init__(self, skill_model, components):
        self._skill_model = skill_model
        self._components = sorted(components, key=lambda x: x.priority)
        # 각 컴포넌트에 부모 스킬 참조 추가 (스킬 데미지 강화용)
        for comp in self._components:
            comp.skill = self

    @property
    def skill_model(self):
        """스킬 모델 반환"""
        return self._skill_model

    @property
    def name(self) -> str:
        """스킬 이름"""
        return self._skill_model.name

    @property
    def description(self) -> str:
        """스킬 설명"""
        return self._skill_model.description or ""

    @property
    def id(self) -> int:
        """스킬 ID"""
        return self._skill_model.id

    @property
    def attribute(self) -> str:
        """스킬 속성"""
        return getattr(self._skill_model, 'attribute', '무속성')

    @property
    def is_passive(self) -> bool:
        """패시브 스킬 여부 (모든 컴포넌트가 패시브 태그일 때)"""
        if not self._components:
            return False
        return all(
            getattr(c, '_tag', '') in PASSIVE_TAGS
            for c in self._components
        )

    @property
    def components(self) -> list:
        """스킬 컴포넌트 목록"""
        return self._components

    def on_turn(self, attacker, target):
        external_multiplier = float(getattr(attacker, "_roguelike_external_multiplier", 1.0) or 1.0)
        effect_multiplier = external_multiplier
        replaying = bool(getattr(attacker, "_roguelike_echo_replaying", False))

        passive_effects = get_passive_effect_bonuses(attacker, target=target)
        effect_multiplier *= 1.0 + max(0.0, passive_effects.get("skill_bonus", 0.0))
        maximum = max(1, int(getattr(attacker, "hp", 1) or 1))
        if getattr(attacker, "now_hp", maximum) / maximum <= 0.30:
            effect_multiplier *= 1.0 + max(0.0, passive_effects.get("low_hp_skill_bonus", 0.0))

        first_bonus = float(getattr(self, "roguelike_first_strike", 0.0) or 0.0)
        if first_bonus and not replaying:
            used = getattr(attacker, "_roguelike_first_uses", set())
            if self.id not in used:
                used.add(self.id)
                attacker._roguelike_first_uses = used
                effect_multiplier *= 1.0 + first_bonus

        overload = float(getattr(self, "roguelike_overload", 0.0) or 0.0)
        if overload and not replaying:
            from models import UserStatEnum
            effect_multiplier *= 1.0 + overload
            max_hp = attacker.get_stat().get(UserStatEnum.HP, getattr(attacker, "hp", 1))
            hp_cost = max(1, int(max_hp * float(getattr(self, "roguelike_overload_hp_cost", 0.05))))
            attacker.now_hp = max(1, attacker.now_hp - hp_cost)

        execution = float(getattr(self, "roguelike_execution_bonus", 0.0) or 0.0)
        if execution and hasattr(target, "get_stat"):
            from models import UserStatEnum
            target_max_hp = target.get_stat().get(UserStatEnum.HP, getattr(target, "hp", 1))
            if getattr(target, "now_hp", target_max_hp) <= target_max_hp * 0.30:
                effect_multiplier *= 1.0 + execution

        attacker._roguelike_effect_multiplier = effect_multiplier
        logs = []
        fallback_log = self._resolve_unmet_payoff_fallback(attacker, target)
        if fallback_log:
            logs.append(fallback_log)
        try:
            for component in self._components:
                log = component.on_turn(attacker, target)
                if log:
                    logs.append(log)
                    if "MISS" in log:
                        break
        finally:
            attacker._roguelike_effect_multiplier = 1.0

        echo_ratio = float(getattr(self, "roguelike_echo_ratio", 0.0) or 0.0)
        if echo_ratio and not replaying:
            queue = getattr(attacker, "_roguelike_echo_queue", [])
            queue.append((self, echo_ratio))
            attacker._roguelike_echo_queue = queue
        return "\n".join(logs)

    def _resolve_unmet_payoff_fallback(self, attacker, target) -> str:
        """Combo-only cards still deal ordinary damage when drawn too early."""
        config = getattr(self.skill_model, "config", {}) or {}
        design = config.get("design", {})
        payoff_tags = [str(value) for value in design.get("payoff_tags", [])]
        if not payoff_tags:
            return ""
        component_tags = {getattr(component, "_tag", "") for component in self._components}
        if "attack" in component_tags or not component_tags & {"combo", "consume"}:
            return ""

        from service.dungeon.status import has_status_effect

        if any(has_status_effect(target, tag) for tag in payoff_tags):
            return ""
        from service.combat.runtime_damage import deal_runtime_damage
        from models import UserStatEnum

        stat = attacker.get_stat()
        ad = int(stat.get(UserStatEnum.ATTACK, 0) or 0)
        ap = int(stat.get(UserStatEnum.AP_ATTACK, 0) or 0)
        is_physical = ad >= ap
        event = deal_runtime_damage(
            attacker, target, max(1, ad if is_physical else ap),
            is_physical=is_physical, attribute=self.attribute,
        ).event
        runtime = getattr(attacker, "combat_runtime_state", None)
        if runtime is not None:
            runtime.record(
                "skill_payoff_missed", skill_id=self.id,
                attacker_id=getattr(attacker, "id", None), payoff_tags=payoff_tags,
            )
        return (
            f"⚪ **{attacker.get_name()}**의 {self.name}: 조건이 없어 특수효과 없이 "
            f"**{target.get_name()}**에게 {event.actual_damage} 일반 피해"
        )

    def on_turn_end(self, attacker, target):
        logs = []
        for component in self._components:
            logs.append(component.on_turn_end(attacker, target))
        return "\n".join(logs)

    def on_turn_start(self, attacker, target):
        logs = []
        for component in self._components:
            logs.append(component.on_turn_start(attacker, target))
        return "\n".join(logs)

    def on_death(self, dying_entity, killer, context):
        logs = []
        for component in self._components:
            log = component.on_death(dying_entity, killer, context)
            if log:
                logs.append(log)
        return "\n".join(logs)


