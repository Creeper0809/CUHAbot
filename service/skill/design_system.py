"""Skill identity and ecosystem contracts for Balance V2.

The combat components describe *how* a skill works. This module records why it
belongs in a deck: its role, archetype, setup/payoff links, and intended slot.
The metadata is deterministic and stored inside the skill JSON config so the
runtime, audit tools, and Discord UI all read the same design contract.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping


STATUS_ARCHETYPES = {
    "burn": "pyromancer", "ignite": "pyromancer",
    "slow": "frost_shatter", "freeze": "frost_shatter",
    "shock": "storm_overload", "paralyze": "storm_overload",
    "erode": "tide_control", "submerge": "tide_control",
    "curse": "shadow_decay", "poison": "shadow_decay", "infection": "shadow_decay",
    "bleed": "blood_hunt", "stun": "vanguard", "mark": "execution",
}

ATTRIBUTE_ARCHETYPES = {
    "화염": "pyromancer", "냉기": "frost_shatter", "빙결": "frost_shatter",
    "번개": "storm_overload", "수속성": "tide_control", "물": "tide_control",
    "신성": "radiance", "암흑": "shadow_decay", "물리": "vanguard",
}

ARCHETYPE_LABELS = {
    "pyromancer": "화상 누적·연소", "frost_shatter": "둔화·빙결·파쇄",
    "storm_overload": "감전·마비·과부하", "tide_control": "침식·침수·회복",
    "radiance": "보호·정화·신성", "shadow_decay": "저주·독·흡혈",
    "blood_hunt": "출혈·처형", "vanguard": "물리 연계·제압",
    "execution": "표식·마무리", "commander": "소환·전장 확장",
    "guardian": "보호막·피해 억제", "sustain": "회복·유지력",
    "engine": "패시브 엔진", "explorer": "탐험·경제", "neutral_combo": "범용 연계",
    "enemy_pattern": "적 전투 패턴",
}

ARCHETYPE_KEYWORDS = {
    "pyromancer": "화염", "frost_shatter": "냉기",
    "storm_overload": "번개", "tide_control": "수속성",
    "radiance": "신성", "shadow_decay": "암흑",
    "blood_hunt": "출혈", "vanguard": "물리", "execution": "처형",
    "commander": "소환", "guardian": "보호막", "sustain": "회복",
    "engine": "패시브", "explorer": "탐험", "neutral_combo": "무속성",
    "enemy_pattern": "몬스터",
}

ROLE_LABELS = {
    "striker": "주력 공격", "setup": "연계 준비", "payoff": "조건부 폭발",
    "finisher": "마무리", "sustain": "회복", "guardian": "보호",
    "control": "행동 제어", "engine": "지속 엔진", "summoner": "소환",
    "recovery": "전선 복구", "utility": "탐험 보조", "enemy_pattern": "적 패턴",
}

STATUS_KEYWORDS = {
    "burn": "화상", "slow": "둔화", "freeze": "빙결", "shock": "감전",
    "paralyze": "마비", "erode": "침식", "submerge": "침수", "curse": "저주",
    "poison": "중독", "infection": "감염", "bleed": "출혈", "stun": "기절",
    "mark": "표식",
}


@dataclass(frozen=True)
class SkillIdentity:
    role: str
    archetype: str
    deck_slot: str
    intent: str
    setup_tags: tuple[str, ...] = ()
    payoff_tags: tuple[str, ...] = ()
    secondary_roles: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["setup_tags"] = list(self.setup_tags)
        value["payoff_tags"] = list(self.payoff_tags)
        value["secondary_roles"] = list(self.secondary_roles)
        return value


def _components(config: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return [value for value in config.get("components", []) if isinstance(value, Mapping)]


def _status_links(components: Iterable[Mapping[str, Any]]) -> tuple[set[str], set[str]]:
    setup: set[str] = set()
    payoff: set[str] = set()
    for component in components:
        tag = component.get("tag")
        if tag == "shield":
            setup.add("shield")
        if tag == "buff":
            # Time/dispelling skills consume remaining buff duration rather
            # than a literal status row. Any actual buff is its producer.
            setup.add("buff_duration")
        if tag == "status" and component.get("type"):
            setup.add(str(component["type"]))
        if tag == "combo" and component.get("prerequisite"):
            payoff.add(str(component["prerequisite"]))
        if tag == "consume" and component.get("consume_type"):
            payoff.add(str(component["consume_type"]))
        applied = component.get("apply_status")
        if isinstance(applied, str) and applied:
            setup.add(applied)
        elif isinstance(applied, Mapping) and applied.get("type"):
            setup.add(str(applied["type"]))
    return setup, payoff


def _archetype(attribute: str, tags: set[str], setup: set[str], payoff: set[str], passive: bool) -> str:
    for status in sorted(payoff | setup):
        if status in STATUS_ARCHETYPES:
            return STATUS_ARCHETYPES[status]
    if "summon" in tags or "revive" in tags:
        return "commander"
    if "shield" in tags:
        return "guardian"
    if "heal" in tags or "cleanse" in tags:
        return "sustain"
    if passive:
        return "engine"
    return ATTRIBUTE_ARCHETYPES.get(attribute, "neutral_combo")


def infer_skill_identity(row: Mapping[str, str], config: Mapping[str, Any]) -> SkillIdentity:
    components = _components(config)
    tags = {str(component.get("tag", "")) for component in components}
    passive = row.get("타입") == "passive"
    category = row.get("카테고리", "")
    obtainable = row.get("플레이어_획득가능", "Y").upper() == "Y"
    setup, payoff = _status_links(components)

    roles: list[str] = []
    if passive:
        roles.append("engine")
    if "revive" in tags:
        roles.append("recovery")
    if "summon" in tags:
        roles.append("summoner")
    if tags & {"heal", "cleanse"}:
        roles.append("sustain")
    if tags & {"shield", "buff"}:
        roles.append("guardian")
    if payoff or tags & {"combo", "consume"}:
        roles.append("payoff")
    if setup or tags & {"status", "debuff"}:
        roles.append("setup")
    if tags & {"attack", "lifesteal", "dot"}:
        roles.append("finisher" if category == "ultimate" else "striker")
    if category in {"exploration", "farming", "social"}:
        roles.append("utility")
    if not roles:
        roles.append("enemy_pattern" if not obtainable else "utility")

    role = roles[0]
    if payoff:
        role = "payoff"
    elif setup and role not in {"sustain", "guardian"}:
        role = "setup"
    elif category == "ultimate":
        role = "finisher"
    archetype = _archetype(row.get("속성", "무속성"), tags, setup, payoff, passive)
    if not obtainable and archetype == "neutral_combo":
        archetype = "enemy_pattern"

    deck_slot = (
        "passive" if passive else
        "defense" if role in {"sustain", "guardian", "recovery"} else
        "utility" if role in {"setup", "control", "utility", "summoner"} else
        "offense"
    )
    setup_text = ", ".join(STATUS_KEYWORDS.get(value, value) for value in sorted(setup))
    payoff_text = ", ".join(STATUS_KEYWORDS.get(value, value) for value in sorted(payoff))
    if payoff_text:
        purpose = f"{payoff_text}을 준비한 뒤 소비하거나 증폭해 큰 보상을 얻는다."
    elif setup_text:
        purpose = f"{setup_text}을 부여해 같은 계열의 조건부 스킬을 준비한다."
    elif role == "striker":
        purpose = "조건 없이 안정적인 피해를 제공해 연계 사이의 공백을 메운다."
    elif role == "finisher":
        purpose = "긴 전투의 결정적인 타이밍에 높은 행동가치를 집중한다."
    elif role == "sustain":
        purpose = "공격 슬롯을 일부 포기하는 대신 장기전 생존력을 제공한다."
    elif role == "guardian":
        purpose = "예고된 큰 피해와 상태 압박을 받아낼 안전 구간을 만든다."
    elif role == "engine":
        purpose = "덱 전체의 반복 행동을 강화하되 중첩 감쇠로 과투자를 제한한다."
    elif role == "summoner":
        purpose = "전투원을 늘려 단일 대상 압박과 행동 순서를 변화시킨다."
    elif role == "recovery":
        purpose = "무너진 전선을 복구하지만 즉시 피해 기회를 포기한다."
    else:
        purpose = "전투 또는 탐험의 선택지를 넓히는 보조 기능을 제공한다."

    return SkillIdentity(
        role=role,
        archetype=archetype,
        deck_slot=deck_slot,
        intent=f"[{ARCHETYPE_LABELS[archetype]} / {ROLE_LABELS[role]}] {purpose}",
        setup_tags=tuple(sorted(setup)),
        payoff_tags=tuple(sorted(payoff)),
        secondary_roles=tuple(value for value in dict.fromkeys(roles) if value != role),
    )


def apply_skill_identity(row: Mapping[str, str], config: dict[str, Any]) -> dict[str, Any]:
    config["design"] = infer_skill_identity(row, config).to_dict()
    return config


def keywords_for_identity(identity: SkillIdentity) -> set[str]:
    keywords = {ARCHETYPE_KEYWORDS[identity.archetype]}
    keywords.update(STATUS_KEYWORDS.get(value, value) for value in identity.setup_tags)
    keywords.update(STATUS_KEYWORDS.get(value, value) for value in identity.payoff_tags)
    if identity.role == "setup":
        keywords.add("셋업")
    if identity.role in {"payoff", "finisher"}:
        keywords.add("피니셔")
    if identity.role == "sustain":
        keywords.add("회복")
    if identity.role == "guardian":
        keywords.add("보호")
    return keywords


def audit_skill_ecosystem(rows: Iterable[Mapping[str, str]]) -> dict[str, Any]:
    """Compatibility facade backed by the explicit V3 authored manifests."""
    from service.skill.design_v3 import audit_authored_contracts, load_design_contracts

    rows = list(rows)
    authored = audit_authored_contracts(rows)
    contracts = load_design_contracts()
    roles = Counter((value.get("scope"), value.get("role")) for value in contracts.values())
    families = Counter((value.get("scope"), value.get("family")) for value in contracts.values())
    return {
        "skills_designed": authored["contracts"],
        "player_skills_designed": authored["player_contracts"],
        "missing_design": [],
        "orphan_payoffs": [],
        "roles": {f"{scope}:{role}": count for (scope, role), count in sorted(roles.items())},
        "archetypes": {f"{scope}:{family}": count for (scope, family), count in sorted(families.items())},
        "duplicate_structure_groups": authored["duplicate_structure_groups"],
        "errors": authored["errors"],
        "passed": authored["passed"],
    }


def _legacy_audit_skill_ecosystem(rows: Iterable[Mapping[str, str]]) -> dict[str, Any]:
    missing: list[int] = []
    setup_by_scope: dict[str, set[str]] = defaultdict(set)
    payoff_rows: list[tuple[int, str, str]] = []
    roles = Counter()
    archetypes = Counter()
    designed = 0
    player_designed = 0

    parsed = []
    for row in rows:
        import json

        config = json.loads(row.get("config") or "{}")
        design = config.get("design") or {}
        parsed.append((row, design))
        if not {"role", "archetype", "deck_slot", "intent"}.issubset(design):
            missing.append(int(row["ID"]))
            continue
        designed += 1
        obtainable = row.get("플레이어_획득가능", "Y").upper() == "Y"
        scope = "player" if obtainable else "monster"
        if obtainable:
            player_designed += 1
        roles[(scope, design["role"])] += 1
        archetypes[(scope, design["archetype"])] += 1
        setup_by_scope[scope].update(design.get("setup_tags", []))
        for tag in design.get("payoff_tags", []):
            payoff_rows.append((int(row["ID"]), scope, tag))

    orphan_payoffs = [
        {"skill_id": skill_id, "scope": scope, "tag": tag}
        for skill_id, scope, tag in payoff_rows
        if tag not in setup_by_scope[scope]
    ]
    return {
        "skills_designed": designed,
        "player_skills_designed": player_designed,
        "missing_design": missing,
        "orphan_payoffs": orphan_payoffs,
        "roles": {f"{scope}:{role}": count for (scope, role), count in sorted(roles.items())},
        "archetypes": {
            f"{scope}:{archetype}": count
            for (scope, archetype), count in sorted(archetypes.items())
        },
        "passed": not missing and not orphan_payoffs,
    }
