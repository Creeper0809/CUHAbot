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

    seen = set()
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
                totals[key] += getattr(comp, key, 0.0)

    return totals


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
        logs = []
        for component in self._components:
            logs.append(component.on_turn(attacker, target))
        return "\n".join(logs)

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


