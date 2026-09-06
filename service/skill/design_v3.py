"""Authored Skill Ecosystem V3 contracts and mechanical descriptions.

V2 inferred a broad role from component tags.  V3 deliberately separates the
authored reason a skill exists from the executable component configuration.
The JSON files under ``data/skill_design`` are the only source of authored
identity; heuristics may audit them but never overwrite them.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from functools import lru_cache
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from utils.game_text import (
    percent_text, stat_label, status_label, target_label, turns_text,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_DIR = PROJECT_ROOT / "data" / "skill_design"
MECHANIC_PATCHES = MANIFEST_DIR / "_mechanic_overrides.json"
MANUAL_REVISION = "V3-manual"

REQUIRED_FIELDS = {
    "id", "scope", "name", "fantasy", "purpose", "family", "role",
    "decision", "strengths", "tradeoffs", "setup_tags", "payoff_tags",
    "partner_skill_ids", "variant_of", "distinctive_reason",
    "expected_trigger_rate", "manual_revision",
    "fallback", "record", "mechanics",
}

PLAYER_ROLES = {
    "basic", "primer", "stacker", "maintainer", "converter", "payoff",
    "defender", "sustain", "engine", "bridge", "finisher", "utility",
}
MONSTER_ROLES = {
    "pressure", "tell", "setup", "punish", "recovery", "summon",
    "phase_capstone", "passive",
}


def _json_files() -> list[Path]:
    return sorted(path for path in MANIFEST_DIR.glob("*.json") if not path.name.startswith("_"))


@lru_cache(maxsize=1)
def load_mechanic_patches() -> dict[int, dict[str, Any]]:
    if not MECHANIC_PATCHES.exists():
        return {}
    values = json.loads(MECHANIC_PATCHES.read_text(encoding="utf-8"))
    patches = {int(value["id"]): value for value in values}
    if len(patches) != len(values):
        raise ValueError("duplicate skill id in V3 mechanic overrides")
    return patches


@lru_cache(maxsize=1)
def load_design_contracts() -> dict[int, dict[str, Any]]:
    contracts: dict[int, dict[str, Any]] = {}
    for path in _json_files():
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError(f"{path.name}: manifest root must be a list")
        for raw in payload:
            if not isinstance(raw, dict):
                raise ValueError(f"{path.name}: every contract must be an object")
            skill_id = int(raw.get("id", 0))
            if skill_id <= 0:
                raise ValueError(f"{path.name}: invalid skill id {skill_id}")
            if skill_id in contracts:
                raise ValueError(f"duplicate authored skill id {skill_id}")
            contracts[skill_id] = raw
    for skill_id, patch in load_mechanic_patches().items():
        if skill_id not in contracts:
            raise ValueError(f"mechanic override references unknown skill {skill_id}")
        contracts[skill_id].update(patch.get("contract", {}))
    return contracts


def clear_design_cache() -> None:
    load_design_contracts.cache_clear()
    load_mechanic_patches.cache_clear()


def apply_authored_design(skill_id: int, config: dict[str, Any]) -> dict[str, Any]:
    contract = load_design_contracts().get(int(skill_id))
    if contract is None:
        raise ValueError(f"skill {skill_id} has no V3 authored contract")
    config["design"] = {
        key: value for key, value in contract.items()
        if key not in {"id", "scope", "name", "baseline"}
    }
    return config


def build_authored_config(skill_id: int) -> dict[str, Any]:
    """Build executable config solely from the checked-in authored manifest."""
    contract = load_design_contracts().get(int(skill_id))
    if contract is None:
        raise ValueError(f"skill {skill_id} has no V3 authored contract")
    mechanics = json.loads(json.dumps(contract["mechanics"], ensure_ascii=False))
    if not isinstance(mechanics, dict):
        raise ValueError(f"skill {skill_id}: mechanics must be an object")
    patch = load_mechanic_patches().get(int(skill_id), {})
    mechanics.setdefault("components", []).extend(
        json.loads(json.dumps(patch.get("append_components", []), ensure_ascii=False))
    )
    return apply_authored_design(skill_id, mechanics)


def _pct(value: Any) -> str:
    try:
        return percent_text(value)
    except (TypeError, ValueError):
        return str(value)


def _ratio_text(component: Mapping[str, Any]) -> str:
    parts: list[str] = []
    if component.get("ad_ratio"):
        parts.append(f"AD {_pct(component['ad_ratio'])}")
    if component.get("ap_ratio"):
        parts.append(f"AP {_pct(component['ap_ratio'])}")
    if component.get("damage_multiplier") and not parts:
        parts.append(f"위력 {_pct(component['damage_multiplier'])}")
    return " + ".join(parts) or "고정 위력"


def _duration_suffix(component: Mapping[str, Any]) -> str:
    return f", {turns_text(component.get('duration', 0))}" if component.get("duration") else ""


def _signed_effect(key: str, value: Any) -> str:
    number = float(value or 0)
    label = stat_label(key)
    if key in {"buff_duration", "invincible_turns"}:
        return f"{label} {number:+g}턴"
    if key in {"death_resist", "foresight", "shop_rare", "heal_seal", "cc_immune"}:
        return {
            "death_resist": "치명적 피해를 1회 버팀",
            "foresight": "다음 위험 경로의 결과를 미리 확인",
            "shop_rare": "상점에 희귀 상품 1개 추가",
            "heal_seal": "공격한 대상의 회복을 차단",
            "cc_immune": "행동 불가 상태이상에 면역",
        }[key]
    if key == "material_double":
        return "재료 획득량 2배"
    if key == "revive":
        return "쓰러질 때 부활" if number == 1 else f"쓰러질 때 최대 {int(number)}회 부활"
    if key == "double_cast":
        return f"{percent_text(number)} 확률로 스킬을 한 번 더 사용"
    return f"{label} {percent_text(number, signed=True)}"


def _stat_component_text(component: Mapping[str, Any], *, beneficial: bool) -> str:
    changes: list[str] = []
    stat_key = str(component.get("stat") or "")
    if stat_key:
        value = component.get("value", component.get("power_scale", 0))
        if stat_key in {"invincible", "invulnerability"}:
            changes.append("무적")
        elif stat_key == "random_all":
            changes.append(f"공격력·방어력·속도를 각각 ±{percent_text(abs(float(value or 0)))} 무작위 변화")
        elif stat_key == "random_redistribute":
            changes.append("공격력·방어력·속도를 무작위로 재분배")
        elif stat_key == "random":
            changes.append(f"공격력·방어력·속도 중 하나를 {percent_text(value, signed=True)} 변화")
        elif stat_key in {"effect_reverse", "buff_reverse"}:
            changes.append("강화 효과의 방향을 반전")
        elif stat_key == "all_debuffs":
            changes.append(f"공격력·방어력·속도 {percent_text(value, signed=True)}")
        elif stat_key in {"skill_seal", "heal_block", "death_mark", "self_destruct", "taunt"}:
            changes.append(f"{stat_label(stat_key)} 부여")
        else:
            changes.append(f"{stat_label(stat_key)} {percent_text(value, signed=True)}")
    for key in ("attack", "defense", "speed", "crit_rate"):
        if component.get(key):
            changes.append(f"{stat_label(key)} {percent_text(component[key], signed=True)}")
    if not changes:
        changes.append("강화" if beneficial else "약화")
    return f"{target_label(component.get('target', 'self' if beneficial else 'single'))} " + ", ".join(changes) + _duration_suffix(component)


def describe_component(component: Mapping[str, Any]) -> str:
    """Render the executable part of a component without duplicating flavor."""
    tag = str(component.get("tag") or "")
    target = target_label(component.get("target", "single"))
    if tag == "attack":
        hits = max(1, int(component.get("hit_count", 1) or 1))
        damage_type = str(component.get("damage_type") or "")
        if damage_type == "max_hp_percent":
            power = f"대상 최대 HP의 {_pct(component.get('value', 0))}"
        elif damage_type == "current_hp_percent":
            power = f"대상 현재 HP의 {_pct(component.get('value', 0))}"
        elif damage_type == "instant_kill":
            power = "대상을 즉사시키는"
        else:
            power = _ratio_text(component)
        details = f"{target}에게 {power} 피해"
        if hits > 1:
            details += f" × {hits}타"
        if component.get("armor_pen"):
            details += f", 관통 {_pct(component['armor_pen'])}"
        if component.get("cannot_evade"):
            details += ", 회피 불가"
        if component.get("guaranteed_crit"):
            details += ", 확정 치명타"
        if component.get("ignore_defense"):
            details += ", 방어 무시"
        if component.get("crit_bonus"):
            details += f", 치명타 확률 +{_pct(component['crit_bonus'])}"
        if component.get("hp_cost") or component.get("self_damage"):
            details += f", 사용 시 최대 HP의 {_pct(component.get('hp_cost', component.get('self_damage')))} 소모"
        if component.get("hp_threshold") is not None:
            details += f", 사용자 HP {_pct(component['hp_threshold'])} 이하에서만 발동"
        if component.get("charge_turns"):
            details += f", {int(component['charge_turns'])}회 행동 충전"
        if component.get("once_per_battle"):
            details += ", 전투당 1회"
        return details
    if tag == "status":
        chance = _pct(component.get("chance", 1.0))
        stacks = int(component.get("stacks", 1) or 1)
        text = f"{target_label(component.get('target', 'single'))}에게 {status_label(component.get('type'))} {stacks}스택 부여 ({chance}{_duration_suffix(component)})"
        if component.get("cannot_cleanse"):
            text += ", 해제 불가"
        return text
    if tag == "combo":
        requirement = status_label(component.get("prerequisite", "조건"))
        minimum = int(component.get("min_stacks", 1) or 1)
        consume = ", 조건 스택 소비" if component.get("consume_stacks") else ""
        return f"{requirement} {minimum}스택 이상이면 {_ratio_text(component)} 추가 효과{consume}"
    if tag == "consume":
        return f"{status_label(component.get('consume_type'))} 전부 소비 후 스택 비례 {_ratio_text(component)} 추가 피해"
    if tag == "combat_resource":
        return (
            f"전투 자원 {status_label(component.get('resource', '자원'))} "
            f"{int(component.get('amount', 1) or 1)} 획득"
            f" (최대 {int(component.get('maximum', 0) or 0)})"
        )
    if tag == "resource_payoff":
        effect = (
            f"최대 HP의 {_pct(component.get('heal_percent'))} 추가 회복"
            if component.get("heal_percent") else f"{_ratio_text(component)} 추가 피해"
        )
        return (
            f"{status_label(component.get('resource', '자원'))} "
            f"{int(component.get('cost', 1) or 1)} 소비 시 {effect}"
        )
    if tag == "status_transform":
        return (
            f"{status_label(component.get('from_status', '상태'))} "
            f"{int(component.get('minimum', 1) or 1)}스택을 "
            f"{status_label(component.get('to_status', '상태'))}로 변환"
        )
    if tag == "heal":
        value = component.get("percent", component.get("heal_percent", 0))
        pieces = []
        if value:
            pieces.append(f"최대 HP의 {_pct(value)}")
        if component.get("ad_ratio"):
            pieces.append(f"AD {_pct(component['ad_ratio'])}")
        if component.get("ap_ratio"):
            pieces.append(f"AP {_pct(component['ap_ratio'])}")
        if component.get("base_amount"):
            pieces.append(f"고정 {int(component['base_amount'])}")
        return f"{target_label(component.get('target', 'self'))}의 " + " + ".join(pieces or ["최대 HP의 15%"]) + " 회복"
    if tag == "shield":
        return f"{target_label(component.get('target', 'self'))}에게 최대 HP의 {_pct(component.get('percent', 0))} 보호막{_duration_suffix(component)}"
    if tag == "buff":
        return _stat_component_text(component, beneficial=True)
    if tag == "debuff":
        return _stat_component_text(component, beneficial=False)
    if tag == "cleanse":
        count = int(component.get("count", 1) or 1)
        what = "강화 효과" if component.get("target") in {"enemy", "all", "all_enemies"} else "해로운 효과"
        return f"{target_label(component.get('target', 'self'))}의 {what} {'모두' if count >= 99 else f'{count}개'} 제거"
    if tag == "lifesteal":
        return f"{_ratio_text(component)} 피해 및 피해의 {_pct(component.get('lifesteal', component.get('ratio', 0)))} 회복"
    if tag == "dot":
        return f"{target_label(component.get('target', 'single'))}에게 {_ratio_text(component)} 지속 피해{_duration_suffix(component)}"
    if tag == "summon":
        return f"지원체 {int(component.get('count', 1) or 1)}기 소환"
    if tag in {"revive", "passive_revive"}:
        return f"쓰러질 때 HP {_pct(component.get('hp_percent', 0.5))}로 최대 {int(component.get('max_uses', component.get('count', 1)) or 1)}회 부활"
    if tag == "passive_buff":
        fields = [_signed_effect(key, value) for key, value in component.items() if key not in {"tag", "condition"} and value]
        condition = {
            "hp_full": "HP가 가득 찼을 때", "hp_below_30": "HP 30% 이하일 때",
            "hp_below_10": "HP 10% 이하일 때", "solo": "혼자 싸울 때", "vs_boss": "보스와 싸울 때",
        }.get(str(component.get("condition") or ""))
        prefix = f"{condition} " if condition else "전투 내내 "
        return prefix + ", ".join(fields or ["고유 효과 적용"])
    if tag == "passive_regen":
        return f"매 턴 최대 HP의 {_pct(component.get('percent', 0))} 재생"
    if tag == "conditional_passive":
        fields = [_signed_effect(key, value) for key, value in component.items() if key not in {"tag", "hp_threshold"} and value]
        return f"HP {_pct(component.get('hp_threshold', 0))} 이하에서 " + ", ".join(fields or ["고유 강화"])
    if tag == "self_damage":
        return f"사용 시 최대 HP의 {_pct(component.get('hp_cost', 0))} 소모"
    if tag == "self_destruct":
        return f"{int(component.get('charge_turns', 1) or 1)}턴 예고 후 {_ratio_text(component)} 폭발"
    if tag == "passive_aura_debuff":
        fields = [_signed_effect(key, value) for key, value in component.items() if key not in {"tag", "target"} and value]
        return "전투 시작 시 모든 적의 " + ", ".join(fields)
    if tag == "passive_debuff_reduction":
        return f"받는 해로운 효과의 수치를 {_pct(component.get('reduction_percent', 0))} 감소"
    if tag == "on_death_summon":
        return f"쓰러질 때 {_pct(component.get('chance', 1))} 확률로 지원체 {int(component.get('count', 1) or 1)}기 소환"
    return "고유 전투 효과"


def describe_skill_config(config: Mapping[str, Any]) -> str:
    components = [value for value in config.get("components", []) if isinstance(value, Mapping)]
    if not components:
        return "실행 효과 없음"
    return " / ".join(describe_component(component) for component in components)


def _structural_signature(config: Mapping[str, Any]) -> str:
    def normalize(value: Any, key: str = "") -> Any:
        if isinstance(value, Mapping):
            return {
                name: normalize(child, name)
                for name, child in sorted(value.items())
                if name != "design"
            }
        if isinstance(value, list):
            return [normalize(child, key) for child in value]
        if isinstance(value, (int, float)) and key not in {"skill_id", "monster_ids"}:
            return "#"
        return value
    return json.dumps(normalize(config), ensure_ascii=False, sort_keys=True)


def audit_authored_contracts(rows: Iterable[Mapping[str, str]]) -> dict[str, Any]:
    rows = list(rows)
    contracts = load_design_contracts()
    row_by_id = {int(row["ID"]): row for row in rows}
    errors: list[str] = []
    warnings: list[str] = []
    producer_ids: dict[str, set[int]] = defaultdict(set)
    payoff_ids: dict[str, set[int]] = defaultdict(set)
    signatures: dict[tuple[str, str], list[int]] = defaultdict(list)
    distinctive = Counter()

    missing = sorted(set(row_by_id) - set(contracts))
    extra = sorted(set(contracts) - set(row_by_id))
    if missing:
        errors.append(f"missing authored contracts: {missing}")
    if extra:
        errors.append(f"orphan authored contracts: {extra}")

    for skill_id, row in row_by_id.items():
        contract = contracts.get(skill_id)
        if not contract:
            continue
        absent = sorted(REQUIRED_FIELDS - set(contract))
        if absent:
            errors.append(f"skill {skill_id}: missing fields {absent}")
            continue
        expected_scope = "player" if row.get("플레이어_획득가능", "Y").upper() == "Y" else "monster"
        if contract["scope"] != expected_scope:
            errors.append(f"skill {skill_id}: scope {contract['scope']} != {expected_scope}")
        if contract["name"] != row.get("이름"):
            errors.append(f"skill {skill_id}: manifest name drift")
        record = contract.get("record") or {}
        if record.get("name") != contract["name"]:
            errors.append(f"skill {skill_id}: authored record/name drift")
        if not isinstance(contract.get("mechanics"), dict):
            errors.append(f"skill {skill_id}: authored mechanics missing")
        elif not isinstance(contract["mechanics"].get("components", []), list):
            errors.append(f"skill {skill_id}: mechanics.components must be a list")
        if contract["manual_revision"] != MANUAL_REVISION:
            errors.append(f"skill {skill_id}: not manually approved for V3")
        role_pool = PLAYER_ROLES if expected_scope == "player" else MONSTER_ROLES
        if contract["role"] not in role_pool:
            errors.append(f"skill {skill_id}: invalid {expected_scope} role {contract['role']}")
        for field in ("fantasy", "purpose", "decision", "distinctive_reason"):
            if not isinstance(contract[field], str) or len(contract[field].strip()) < 8:
                errors.append(f"skill {skill_id}: {field} is not authored")
        if not contract["strengths"] or not contract["tradeoffs"]:
            errors.append(f"skill {skill_id}: strengths/tradeoffs must be explicit")
        distinctive[str(contract["distinctive_reason"]).strip()] += 1
        for partner in contract["partner_skill_ids"]:
            if int(partner) not in row_by_id:
                errors.append(f"skill {skill_id}: unknown partner {partner}")
        for tag in contract["setup_tags"]:
            producer_ids[str(tag)].add(skill_id)
        for tag in contract["payoff_tags"]:
            payoff_ids[str(tag)].add(skill_id)
        try:
            config = json.loads(row.get("config") or "{}")
        except json.JSONDecodeError:
            errors.append(f"skill {skill_id}: invalid config JSON")
            continue
        signatures[(expected_scope, _structural_signature(config))].append(skill_id)

    repeated_reasons = sorted(text for text, count in distinctive.items() if count > 1)
    if repeated_reasons:
        errors.append(f"repeated distinctive reasons: {len(repeated_reasons)}")

    orphan_payoffs = sorted(set(payoff_ids) - set(producer_ids))
    if orphan_payoffs:
        errors.append(f"payoff tags without producer: {orphan_payoffs}")

    duplicate_groups: list[list[int]] = []
    for ids in signatures.values():
        if len(ids) <= 1:
            continue
        duplicate_groups.append(ids)
        root = ids[0]
        for skill_id in ids[1:]:
            contract = contracts.get(skill_id, {})
            variant_of = int(contract.get("variant_of") or 0)
            if variant_of not in row_by_id:
                errors.append(
                    f"skill {skill_id}: duplicate structure requires an existing variant_of"
                )
            elif len(str(contract.get("distinctive_reason", ""))) < 8:
                errors.append(f"skill {skill_id}: duplicate variant lacks tradeoff rationale")
        if contracts.get(root, {}).get("variant_of") not in (None, 0):
            warnings.append(f"duplicate root {root} also declares variant_of")

    return {
        "contracts": len(contracts),
        "player_contracts": sum(value.get("scope") == "player" for value in contracts.values()),
        "monster_contracts": sum(value.get("scope") == "monster" for value in contracts.values()),
        "duplicate_structure_groups": sorted(duplicate_groups),
        "setup_tags": {key: sorted(value) for key, value in sorted(producer_ids.items())},
        "payoff_tags": {key: sorted(value) for key, value in sorted(payoff_ids.items())},
        "errors": errors,
        "warnings": warnings,
        "passed": not errors,
    }


def first_link_probability(setup_copies: int, payoff_copies: int) -> float:
    """Chance that the first relevant card in a shuffled bag is a setup."""
    total = max(0, setup_copies) + max(0, payoff_copies)
    return (max(0, setup_copies) / total) if total else 0.0


def deck_link_summary(deck: Sequence[int], configs: Mapping[int, Mapping[str, Any]]) -> list[dict[str, Any]]:
    setup_counts: Counter[str] = Counter()
    payoff_counts: Counter[str] = Counter()
    active_cards = 0
    for skill_id in deck:
        if not skill_id or skill_id not in configs:
            continue
        design = configs[skill_id].get("design", {})
        if design.get("deck_slot") == "passive" or design.get("role") == "engine" and not configs[skill_id].get("components"):
            continue
        active_cards += 1
        setup_counts.update(str(tag) for tag in design.get("setup_tags", []))
        payoff_counts.update(str(tag) for tag in design.get("payoff_tags", []))
    result = []
    for tag in sorted(set(setup_counts) | set(payoff_counts)):
        setup = setup_counts[tag]
        payoff = payoff_counts[tag]
        result.append({
            "tag": tag,
            "setup_copies": setup,
            "payoff_copies": payoff,
            "first_link_probability": first_link_probability(setup, payoff),
            "active_cards": active_cards,
        })
    return result
