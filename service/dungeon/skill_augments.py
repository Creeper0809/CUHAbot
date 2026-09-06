"""Run-only skill augments applied to copies of cached skills."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from enum import Enum
import random

from service.dungeon.skill import Skill


class AugmentId(str, Enum):
    POWER = "power"
    MULTIHIT = "multihit"
    PENETRATION = "penetration"
    EXECUTION = "execution"
    SPREAD = "spread"
    STATUS_CATALYST = "status_catalyst"
    EFFECT_BOOST = "effect_boost"
    ECHO = "echo"
    OVERHEAL = "overheal"
    EXTEND = "extend"
    CLEANSE = "cleanse"
    FIRST_STRIKE = "first_strike"
    OVERLOAD = "overload"
    ULTIMATE_HASTE = "ultimate_haste"


@dataclass(frozen=True)
class AugmentDefinition:
    augment_id: AugmentId
    label: str
    description: str
    tags: frozenset[str] = frozenset()
    exclusive_group: str | None = None
    ultimate_only: bool = False
    universal: bool = False


AUGMENTS = {
    AugmentId.POWER: AugmentDefinition(AugmentId.POWER, "위력 증폭", "공격 계수 +25%", frozenset({"damage"})),
    AugmentId.MULTIHIT: AugmentDefinition(AugmentId.MULTIHIT, "연격", "타격 +1, 총 기대 피해 +20%", frozenset({"attack"}), "delivery"),
    AugmentId.PENETRATION: AugmentDefinition(AugmentId.PENETRATION, "관통", "방어 관통 +25%p", frozenset({"attack"})),
    AugmentId.EXECUTION: AugmentDefinition(AugmentId.EXECUTION, "처형", "HP 30% 이하 대상 피해 +50%", frozenset({"damage"})),
    AugmentId.SPREAD: AugmentDefinition(AugmentId.SPREAD, "확산", "단일 공격을 65% 전체 공격으로 변경", frozenset({"attack"}), "delivery"),
    AugmentId.STATUS_CATALYST: AugmentDefinition(AugmentId.STATUS_CATALYST, "상태 촉매", "상태이상 확률 +15%p, 지속 +1턴", frozenset({"status", "dot"})),
    AugmentId.EFFECT_BOOST: AugmentDefinition(AugmentId.EFFECT_BOOST, "효과 증폭", "회복·보호막·버프·디버프 +30%", frozenset({"heal", "shield", "buff", "debuff"})),
    AugmentId.ECHO: AugmentDefinition(AugmentId.ECHO, "잔향", "다음 행동 전에 효과의 40% 재발동", frozenset({"heal", "buff", "cleanse"}), "delivery"),
    AugmentId.OVERHEAL: AugmentDefinition(AugmentId.OVERHEAL, "과회복", "초과 회복 60%를 최대 HP 20% 보호막으로 전환", frozenset({"heal"})),
    AugmentId.EXTEND: AugmentDefinition(AugmentId.EXTEND, "연장", "지속시간 +1턴", frozenset({"status", "dot", "shield", "buff", "debuff"})),
    AugmentId.CLEANSE: AugmentDefinition(AugmentId.CLEANSE, "정화", "회복 시 디버프 1개 제거", frozenset({"heal"})),
    AugmentId.FIRST_STRIKE: AugmentDefinition(AugmentId.FIRST_STRIKE, "선제 강화", "전투마다 첫 사용 효과 +35%", universal=True),
    AugmentId.OVERLOAD: AugmentDefinition(AugmentId.OVERLOAD, "과부하", "효과 +45%, 사용 시 최대 HP 5% 소모", universal=True),
    AugmentId.ULTIMATE_HASTE: AugmentDefinition(AugmentId.ULTIMATE_HASTE, "궁극 가속", "궁극기 재사용 대기시간 -1", ultimate_only=True),
}


def component_tags(skill: Skill) -> set[str]:
    tags = {str(getattr(component, "_tag", "")) for component in skill.components}
    if tags.intersection({"attack", "lifesteal", "combo"}):
        tags.add("damage")
    if "lifesteal" in tags:
        tags.update({"attack", "heal"})
    for component in skill.components:
        if getattr(component, "_tag", "") == "combo" and getattr(component, "apply_status", None):
            tags.add("status")
    return tags


def available_augments(skill: Skill, existing=(), *, is_ultimate: bool = False) -> list[AugmentDefinition]:
    tags = component_tags(skill)
    existing_ids = {AugmentId(value) for value in existing}
    existing_groups = {
        AUGMENTS[value].exclusive_group for value in existing_ids
        if AUGMENTS[value].exclusive_group
    }
    candidates = []
    for definition in AUGMENTS.values():
        if definition.augment_id in existing_ids:
            continue
        if definition.ultimate_only and not is_ultimate:
            continue
        if definition.exclusive_group and definition.exclusive_group in existing_groups:
            continue
        if definition.universal or definition.ultimate_only or definition.tags.intersection(tags):
            candidates.append(definition)
    return candidates


def generate_augment_offers(skill: Skill, existing, rng: random.Random, *, is_ultimate: bool = False) -> list[AugmentDefinition]:
    candidates = available_augments(skill, existing, is_ultimate=is_ultimate)
    if len(candidates) <= 3:
        return candidates
    universal = [candidate for candidate in candidates if candidate.universal]
    specific = [candidate for candidate in candidates if not candidate.universal]
    picked = [rng.choice(universal)] if universal else []
    pool = specific + [candidate for candidate in universal if candidate not in picked]
    picked.extend(rng.sample(pool, k=3 - len(picked)))
    return picked


def _scale_numeric_components(components: list, multiplier: float, tags: set[str]) -> None:
    attributes = ("ad_ratio", "ap_ratio", "percent", "flat", "attack_mod", "defense_mod", "speed_mod", "stat_value")
    for component in components:
        if getattr(component, "_tag", "") not in tags:
            continue
        for attribute in attributes:
            value = getattr(component, attribute, None)
            if isinstance(value, (int, float)) and value != 0:
                setattr(component, attribute, value * multiplier)


def clone_with_augments(skill: Skill, augment_ids: list[str], *, is_ultimate: bool = False) -> Skill:
    components = copy.deepcopy(skill.components)
    clone = Skill(skill.skill_model, components)
    scale = 0.70 if is_ultimate else 1.0

    for raw_id in augment_ids:
        augment_id = AugmentId(raw_id)
        if augment_id == AugmentId.POWER:
            _scale_numeric_components(components, 1.0 + 0.25 * scale, {"attack", "lifesteal", "combo"})
        elif augment_id == AugmentId.MULTIHIT:
            for component in components:
                if getattr(component, "_tag", "") == "attack":
                    old_hits = max(1, int(getattr(component, "hit_count", 1)))
                    new_hits = old_hits + 1
                    ratio_scale = (old_hits * (1.0 + 0.20 * scale)) / new_hits
                    component.ad_ratio *= ratio_scale
                    component.ap_ratio *= ratio_scale
                    component.hit_count = new_hits
        elif augment_id == AugmentId.PENETRATION:
            for component in components:
                if getattr(component, "_tag", "") == "attack":
                    component.armor_penetration = min(0.70, component.armor_penetration + 0.25 * scale)
        elif augment_id == AugmentId.EXECUTION:
            clone.roguelike_execution_bonus = 0.50 * scale
        elif augment_id == AugmentId.SPREAD:
            for component in components:
                if getattr(component, "_tag", "") == "attack" and not getattr(component, "is_aoe", False):
                    component.ad_ratio *= 0.65
                    component.ap_ratio *= 0.65
                    component.is_aoe = True
                    component.target_type = "all_enemies"
        elif augment_id == AugmentId.STATUS_CATALYST:
            for component in components:
                if getattr(component, "_tag", "") in {"status", "dot"}:
                    if hasattr(component, "chance"):
                        component.chance = min(1.0, component.chance + 0.15 * scale)
                    if hasattr(component, "duration"):
                        component.duration += 1
        elif augment_id == AugmentId.EFFECT_BOOST:
            _scale_numeric_components(components, 1.0 + 0.30 * scale, {"heal", "shield", "buff", "debuff"})
        elif augment_id == AugmentId.ECHO:
            clone.roguelike_echo_ratio = 0.40 * scale
        elif augment_id == AugmentId.OVERHEAL:
            for component in components:
                if getattr(component, "_tag", "") == "heal":
                    component.roguelike_overheal = True
        elif augment_id == AugmentId.EXTEND:
            for component in components:
                if getattr(component, "_tag", "") in {"status", "dot", "shield", "buff", "debuff"}:
                    if hasattr(component, "duration"):
                        component.duration += 1
                    if hasattr(component, "shield_duration"):
                        component.shield_duration += 1
        elif augment_id == AugmentId.CLEANSE:
            for component in components:
                if getattr(component, "_tag", "") == "heal":
                    component.roguelike_cleanse = True
        elif augment_id == AugmentId.FIRST_STRIKE:
            clone.roguelike_first_strike = 0.35 * scale
        elif augment_id == AugmentId.OVERLOAD:
            clone.roguelike_overload = 0.45 * scale
            clone.roguelike_overload_hp_cost = 0.05
    clone.roguelike_augment_ids = list(augment_ids)
    return clone


def apply_session_augments(user, skill: Skill | None) -> Skill | None:
    if skill is None:
        return None
    from service.session import get_session
    from service.skill.ultimate_service import is_ultimate_skill

    session = get_session(getattr(user, "discord_id", 0))
    if not session or not session.roguelike_enabled:
        return skill
    augment_ids = session.skill_augments.get(skill.id, [])
    if not augment_ids:
        return skill
    return clone_with_augments(skill, augment_ids, is_ultimate=is_ultimate_skill(skill.id))


def ultimate_cooldown_reduction(user, skill_id: int) -> int:
    from service.session import get_session

    session = get_session(getattr(user, "discord_id", 0))
    if not session or not session.roguelike_enabled:
        return 0
    return 1 if AugmentId.ULTIMATE_HASTE.value in session.skill_augments.get(skill_id, []) else 0
