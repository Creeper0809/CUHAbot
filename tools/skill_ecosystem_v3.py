"""Compile, audit, and report the authored Skill Ecosystem V3 data."""
from __future__ import annotations

import argparse
import csv
from copy import deepcopy
import json
from pathlib import Path
from typing import Any

from service.skill.design_v3 import (
    apply_authored_design,
    audit_authored_contracts,
    build_authored_config,
    clear_design_cache,
    describe_skill_config,
    load_design_contracts,
)


ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "data" / "skills.csv"
MONSTERS = ROOT / "data" / "monsters.csv"
PROFILES = ROOT / "data" / "monster_action_profiles.json"
ASSIGNMENTS = ROOT / "data" / "monster_skill_assignments.json"
REPORT_JSON = ROOT / "reports" / "skill_ecosystem_v3.json"
REPORT_MD = ROOT / "reports" / "skill_ecosystem_v3.md"
SKILL_DOC = ROOT / "docs" / "Skills.md"


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def write_csv(path: Path, headers: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _load_raw_profiles() -> dict[int, dict[str, Any]]:
    payload = json.loads(PROFILES.read_text(encoding="utf-8"))
    profiles: dict[int, dict[str, Any]] = {}
    for profile in payload:
        monster_id = int(profile["monster_id"])
        if monster_id in profiles:
            raise ValueError(f"duplicate monster action profile {monster_id}")
        profiles[monster_id] = profile
    return profiles


def load_assignment_manifest() -> dict[str, Any]:
    payload = json.loads(ASSIGNMENTS.read_text(encoding="utf-8"))
    assignments = payload.get("assignments") or []
    skill_ids = [int(value["skill_id"]) for value in assignments]
    if len(skill_ids) != len(set(skill_ids)):
        raise ValueError("duplicate skill ID in monster assignment manifest")
    if not payload.get("revision"):
        raise ValueError("monster assignment manifest requires a revision")
    for monster_id, values in (payload.get("stat_overrides") or {}).items():
        int(monster_id)
        if not values or not set(values).issubset({"Attack", "AP_Attack"}):
            raise ValueError(f"monster {monster_id}: invalid assignment stat override")
        if any(float(value) <= 0 for value in values.values()):
            raise ValueError(f"monster {monster_id}: secondary attack override must be positive")
    return payload


def _apply_profile_assignments(
    profiles: dict[int, dict[str, Any]],
    manifest: dict[str, Any],
) -> dict[int, dict[str, Any]]:
    """Overlay the explicit connectivity manifest onto the authored FSMs."""
    result = deepcopy(profiles)
    removals = {
        int(monster_id): {int(skill_id) for skill_id in skill_ids}
        for monster_id, skill_ids in (manifest.get("remove_skill_ids") or {}).items()
    }
    for monster_id, skill_ids in removals.items():
        if monster_id not in result:
            raise ValueError(f"assignment removal references unknown monster {monster_id}")
        profile = result[monster_id]
        profile["actions"] = [
            action for action in profile.get("actions", [])
            if int(action.get("skill_id", 0) or 0) not in skill_ids
        ]
        for pattern in profile.get("phase_patterns", []):
            pattern["skill_ids"] = [
                int(skill_id) for skill_id in pattern.get("skill_ids", [])
                if int(skill_id) not in skill_ids
            ]

    action_keys = {
        "skill_id", "weight", "telegraph", "interruptible",
        "cooldown_actions", "recover_actions",
    }
    for assignment in manifest.get("assignments") or []:
        skill_id = int(assignment["skill_id"])
        monster_id = int(assignment["monster_id"])
        unlock_phase = max(1, int(assignment.get("unlock_phase", 1) or 1))
        if monster_id not in result:
            raise ValueError(f"skill {skill_id}: unknown assigned monster {monster_id}")
        profile = result[monster_id]
        action = {
            "skill_id": skill_id,
            "weight": max(1, int(assignment.get("weight", 1) or 1)),
            "telegraph": assignment.get("telegraph"),
            "interruptible": bool(assignment.get("interruptible", False)),
            "cooldown_actions": max(0, int(assignment.get("cooldown_actions", 0) or 0)),
            "recover_actions": max(0, int(assignment.get("recover_actions", 0) or 0)),
        }
        unknown = set(assignment) - action_keys - {"monster_id", "unlock_phase"}
        if unknown:
            raise ValueError(f"skill {skill_id}: unknown assignment keys {sorted(unknown)}")
        current = next(
            (value for value in profile.get("actions", []) if int(value.get("skill_id", 0) or 0) == skill_id),
            None,
        )
        if current is None:
            profile.setdefault("actions", []).append(action)
        else:
            current.clear()
            current.update(action)
        patterns = profile.get("phase_patterns") or []
        eligible = [pattern for pattern in patterns if int(pattern.get("phase", 0) or 0) >= unlock_phase]
        if not eligible:
            raise ValueError(
                f"skill {skill_id}: monster {monster_id} has no phase >= {unlock_phase}"
            )
        for pattern in eligible:
            ids = [int(value) for value in pattern.get("skill_ids", [])]
            if skill_id not in ids:
                ids.append(skill_id)
            pattern["skill_ids"] = ids
    return result


def load_profiles() -> dict[int, dict[str, Any]]:
    return _apply_profile_assignments(_load_raw_profiles(), load_assignment_manifest())


def _connect_combat_deck(
    row: dict[str, str],
    profile: dict[str, Any],
    removed: set[int],
) -> list[int]:
    """Keep the legacy ten-slot deck synchronized without dropping passives."""
    deck = [int(value) for value in json.loads(row.get("skill_ids") or "[]")]
    deck = (deck + [0] * 10)[:10]
    deck = [0 if value in removed else value for value in deck]
    required: list[int] = []
    for action in profile.get("actions", []):
        skill_id = int(action.get("skill_id", 0) or 0)
        if skill_id and skill_id not in required:
            required.append(skill_id)
    for skill_id in required:
        if skill_id in deck:
            continue
        try:
            index = len(deck) - 1 - deck[::-1].index(0)
        except ValueError:
            index = next(
                (
                    candidate for candidate in range(len(deck) - 1, -1, -1)
                    if deck[candidate] and deck.count(deck[candidate]) > 1
                ),
                -1,
            )
            if index < 0:
                raise ValueError(
                    f"monster {row['ID']}: ten-slot deck has no capacity for action skill {skill_id}"
                )
        deck[index] = skill_id
    return deck


def compile_rows(write: bool = False) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    skill_headers, skill_rows = read_csv(SKILLS)
    monster_headers, monster_rows = read_csv(MONSTERS)
    profiles = load_profiles()
    manifest = load_assignment_manifest()
    contracts = load_design_contracts()

    for row in skill_rows:
        skill_id = int(row["ID"])
        contract = contracts[skill_id]
        record = contract["record"]
        row.update({
            "이름": record["name"],
            "타입": record["type"],
            "카테고리": record["category"],
            "속성": record["attribute"],
            "등급": record["grade"],
            "획득처": record["acquisition_source"],
            "키워드": record["keywords"],
            "플레이어_획득가능": "Y" if contract["scope"] == "player" else "N",
        })
        config = build_authored_config(skill_id)
        row["config"] = json.dumps(config, ensure_ascii=False, separators=(",", ":"))
        row["효과"] = describe_skill_config(config)
        if contract.get("name") != row.get("이름"):
            raise ValueError(f"skill {skill_id}: name differs from authored source")

    if "action_profile" not in monster_headers:
        phase_index = monster_headers.index("phase_config") + 1 if "phase_config" in monster_headers else len(monster_headers)
        monster_headers.insert(phase_index, "action_profile")
    stat_overrides = {
        int(monster_id): values
        for monster_id, values in (manifest.get("stat_overrides") or {}).items()
    }
    for row in monster_rows:
        monster_id = int(row["ID"])
        if monster_id not in profiles:
            raise ValueError(f"monster {monster_id}: missing action profile")
        for field, value in stat_overrides.get(monster_id, {}).items():
            row[field] = str(int(value))
        removed = {
            int(value)
            for value in (manifest.get("remove_skill_ids") or {}).get(str(monster_id), [])
        }
        row["skill_ids"] = json.dumps(
            _connect_combat_deck(row, profiles[monster_id], removed),
            ensure_ascii=False,
        )
        row["action_profile"] = json.dumps(profiles[monster_id], ensure_ascii=False, separators=(",", ":"))

    if write:
        PROFILES.write_text(
            json.dumps([profiles[key] for key in sorted(profiles)], ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        write_csv(SKILLS, skill_headers, skill_rows)
        write_csv(MONSTERS, monster_headers, monster_rows)
    return skill_rows, monster_rows


def audit() -> dict[str, Any]:
    skill_rows, monster_rows = compile_rows(write=False)
    contracts_result = audit_authored_contracts(skill_rows)
    profiles = load_profiles()
    errors = list(contracts_result["errors"])
    warnings = list(contracts_result["warnings"])
    skill_by_id = {int(row["ID"]): row for row in skill_rows}
    monster_by_id = {int(row["ID"]): row for row in monster_rows}
    contracts = load_design_contracts()
    monster_contract_ids = {
        skill_id for skill_id, contract in contracts.items()
        if contract.get("scope") == "monster"
    }
    active_monster_ids = {
        skill_id for skill_id in monster_contract_ids
        if contracts[skill_id].get("record", {}).get("type") == "active"
    }
    deck_refs = {
        int(skill_id)
        for row in monster_rows
        for skill_id in json.loads(row.get("skill_ids") or "[]")
        if int(skill_id)
    }
    action_refs: set[int] = set()
    reachable_refs: set[int] = set()

    if len(profiles) != 128:
        errors.append(f"expected 128 monster profiles, got {len(profiles)}")
    missing_profiles = sorted(set(monster_by_id) - set(profiles))
    extra_profiles = sorted(set(profiles) - set(monster_by_id))
    if missing_profiles:
        errors.append(f"monsters without action profile: {missing_profiles}")
    if extra_profiles:
        errors.append(f"profiles without monster: {extra_profiles}")

    type_counts = {"common": 0, "elite": 0, "boss": 0}
    telegraphed_bosses = 0
    for monster_id, profile in profiles.items():
        kind = str(profile.get("kind") or "")
        if kind not in type_counts:
            errors.append(f"monster {monster_id}: invalid profile kind {kind}")
            continue
        type_counts[kind] += 1
        if profile.get("revision") != "V3-FSM":
            errors.append(f"monster {monster_id}: profile is not V3-FSM")
        actions = profile.get("actions") or []
        if not actions:
            errors.append(f"monster {monster_id}: no actions")
            continue
        has_telegraph = False
        phase_ids = {
            int(skill_id)
            for pattern in profile.get("phase_patterns", [])
            for skill_id in pattern.get("skill_ids", [])
            if int(skill_id)
        }
        for action in actions:
            skill_id = int(action.get("skill_id", 0) or 0)
            if skill_id:
                action_refs.add(skill_id)
                if skill_id in phase_ids:
                    reachable_refs.add(skill_id)
            if skill_id and skill_id not in skill_by_id:
                errors.append(f"monster {monster_id}: unknown action skill {skill_id}")
            if skill_id and skill_id not in json.loads(monster_by_id[monster_id].get("skill_ids") or "[]"):
                errors.append(f"monster {monster_id}: action skill {skill_id} is absent from ten-slot deck")
            if action.get("telegraph"):
                has_telegraph = True
                if not action.get("interruptible"):
                    errors.append(f"monster {monster_id}: telegraph must declare interruption")
            if int(action.get("weight", 0) or 0) <= 0:
                errors.append(f"monster {monster_id}: non-positive action weight")
        if kind == "boss":
            if has_telegraph:
                telegraphed_bosses += 1
            else:
                errors.append(f"boss {monster_id}: no telegraphed high-impact action")
            patterns = profile.get("phase_patterns") or []
            distinct_patterns = {tuple(pattern.get("skill_ids", [])) for pattern in patterns}
            if len(patterns) < 2 or len(distinct_patterns) < 2:
                errors.append(f"boss {monster_id}: phase patterns do not unlock different actions")
        elif kind == "elite":
            if not has_telegraph:
                errors.append(f"elite {monster_id}: punish action has no telegraph")
            if not any(int(action.get("recover_actions", 0) or 0) > 0 for action in actions):
                errors.append(f"elite {monster_id}: punish action has no recovery window")
        elif len(actions) < 2:
            errors.append(f"common monster {monster_id}: requires a core and support action")
        elif not any(
            int(action.get("skill_id", 0) or 0) > 0
            and action.get("action_kind") != "support"
            and int(action.get("skill_id", 0) or 0) in phase_ids
            for action in actions
        ):
            errors.append(f"common monster {monster_id}: no reachable authored core skill")

        deck = json.loads(monster_by_id[monster_id].get("skill_ids") or "[]")
        if len(deck) != 10:
            errors.append(f"monster {monster_id}: combat deck must contain exactly ten slots")

    expected_types = {"common": 72, "elite": 23, "boss": 33}
    if type_counts != expected_types:
        errors.append(f"monster type counts {type_counts} != {expected_types}")

    missing_deck = sorted(monster_contract_ids - deck_refs)
    missing_actions = sorted(active_monster_ids - action_refs)
    unreachable_actions = sorted(active_monster_ids - reachable_refs)
    if missing_deck:
        errors.append(f"monster skills absent from every combat deck: {missing_deck}")
    if missing_actions:
        errors.append(f"active monster skills absent from every FSM: {missing_actions}")
    if unreachable_actions:
        errors.append(f"active monster skills unreachable in every FSM phase: {unreachable_actions}")

    raw_profiles = _load_raw_profiles()
    if raw_profiles != profiles:
        errors.append("monster action profile assignments are not materialized; run compile")
    _, raw_monster_rows = read_csv(MONSTERS)
    compiled_by_id = {int(row["ID"]): row for row in monster_rows}
    for row in raw_monster_rows:
        expected = compiled_by_id[int(row["ID"])]
        if row.get("skill_ids") != expected.get("skill_ids") or row.get("action_profile") != expected.get("action_profile"):
            errors.append(f"monster {row['ID']}: generated connectivity fields are stale; run compile")

    for row in skill_rows:
        config = json.loads(row.get("config") or "{}")
        expected = describe_skill_config(config)
        if row.get("효과") != expected:
            errors.append(f"skill {row['ID']}: mechanical description drift")
        design = config.get("design") or {}
        if design.get("payoff_tags") and not design.get("fallback"):
            errors.append(f"skill {row['ID']}: payoff has no fallback contract")

    return {
        "revision": "V3",
        "skill_contracts": contracts_result,
        "monster_skill_contracts": len(monster_contract_ids),
        "monster_skills_in_combat_decks": len(monster_contract_ids & deck_refs),
        "active_monster_skill_contracts": len(active_monster_ids),
        "active_monster_skills_in_fsm": len(active_monster_ids & action_refs),
        "active_monster_skills_phase_reachable": len(active_monster_ids & reachable_refs),
        "explicit_connectivity_assignments": len(load_assignment_manifest().get("assignments") or []),
        "monster_profiles": len(profiles),
        "monster_type_counts": type_counts,
        "telegraphed_bosses": telegraphed_bosses,
        "errors": errors,
        "warnings": warnings,
        "passed": not errors,
    }


def report(write: bool = True) -> dict[str, Any]:
    skill_rows, _ = compile_rows(write=False)
    audit_result = audit()
    contracts = load_design_contracts()
    entries = []
    for row in sorted(skill_rows, key=lambda value: int(value["ID"])):
        skill_id = int(row["ID"])
        contract = contracts[skill_id]
        baseline = contract.get("baseline", {})
        entries.append({
            "id": skill_id,
            "scope": contract["scope"],
            "name": row["이름"],
            "family": contract["family"],
            "role": contract["role"],
            "old_description": baseline.get("description", ""),
            "new_description": row["효과"],
            "purpose": contract["purpose"],
            "decision": contract["decision"],
            "distinctive_reason": contract["distinctive_reason"],
            "setup_tags": contract["setup_tags"],
            "payoff_tags": contract["payoff_tags"],
            "partners": contract["partner_skill_ids"],
            "variant_of": contract["variant_of"],
            "validation": "passed" if contract.get("manual_revision") == "V3-manual" else "failed",
        })
    payload = {"summary": audit_result, "skills": entries}
    if write:
        REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
        REPORT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        lines = [
            "# Skill Ecosystem V3 per-ID review", "",
            f"- Skills: {len(entries)}", f"- Passed: {audit_result['passed']}",
            f"- Monster profiles: {audit_result['monster_profiles']}", "",
            f"- Monster skills connected: {audit_result['monster_skills_in_combat_decks']}/{audit_result['monster_skill_contracts']}",
            f"- Active monster skills phase-reachable: {audit_result['active_monster_skills_phase_reachable']}/{audit_result['active_monster_skill_contracts']}", "",
            "| ID | Scope | Name | Family | Role | Variant | Validation |", "|---:|---|---|---|---|---:|---|",
        ]
        lines.extend(
            f"| {entry['id']} | {entry['scope']} | {entry['name']} | {entry['family']} | {entry['role']} | {entry['variant_of'] or ''} | {entry['validation']} |"
            for entry in entries
        )
        REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
        role_counts: dict[str, int] = {}
        family_counts: dict[str, int] = {}
        for entry in entries:
            role_key = f"{entry['scope']}:{entry['role']}"
            family_key = f"{entry['scope']}:{entry['family']}"
            role_counts[role_key] = role_counts.get(role_key, 0) + 1
            family_counts[family_key] = family_counts.get(family_key, 0) + 1
        doc_lines = [
            "# Skill Ecosystem V3", "",
            "이 문서는 `data/skill_design/`의 수작업 계약과 실행 컴포넌트에서 생성됩니다. `data/skills.csv`는 결과물이며 설계 원본이 아닙니다.", "",
            f"- 전체 스킬: {len(entries)} (플레이어 326 / 몬스터 321)",
            "- 몬스터 행동 세트: 128 (일반 72 / 정예 23 / 보스 33)",
            "- 플레이어 셔플백은 순서 보정 없이 유지하며, 생성기/소비기 장수 비율이 조건 성립률을 결정합니다.",
            "- 조건이 먼저 나오면 특수효과는 생략되고 계약에 기록된 기본 피해·회복·방어 효과만 적용됩니다.",
            "- 같은 패시브 ID는 중첩되지 않으므로 두 슬롯에 편성할 수 없습니다.", "",
            "## 전투 자원 연결", "",
            "| 계열 | 생성 자원 | 대표 생성기 | 대표 소비기 |", "|---|---|---|---|",
            "| 물리 | 기세 | 1001 강타 | 8504 출혈 폭발 |",
            "| 화염 | 불씨 | 1101 화염구, 8001 불씨 키우기 | 8003 화상 폭발 |",
            "| 냉기 | 서리 | 1201 얼음 화살 | 8102 빙결 분쇄 |",
            "| 번개 | 전하 | 1301 전격 | 8121 천둥 낙뢰 |",
            "| 수속성 | 조류 | 1401 물의 창 | 1409 생명의 원천 |",
            "| 신성 | 신념 | 1501 빛의 화살 | 8405 성스러운 폭발 |",
            "| 암흑 | 영혼 | 1601 암흑 화살 | 8303 저주 수확 |", "",
            "## 역할 분포", "", "| 범위:역할 | 개수 |", "|---|---:|",
        ]
        doc_lines.extend(f"| {key} | {value} |" for key, value in sorted(role_counts.items()))
        doc_lines.extend(["", "## 계열 분포", "", "| 범위:계열 | 개수 |", "|---|---:|"])
        doc_lines.extend(f"| {key} | {value} |" for key, value in sorted(family_counts.items()))
        doc_lines.extend([
            "", "## 검증 산출물", "",
            "- `reports/skill_ecosystem_v3.json`: 647개 기존값·신규값·변경 이유·검증 결과",
            "- `reports/skill_ecosystem_v3.md`: ID별 요약 표",
            "- `data/monster_action_profiles.json`: 전조·실행·회복·페이즈 전이 원본", "",
            "- `data/monster_skill_assignments.json`: 기존 미연결 65개 스킬의 명시적 몬스터·페이즈 배정", "",
        ])
        with SKILL_DOC.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write("\n".join(doc_lines))
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("compile", "audit", "report"))
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    clear_design_cache()
    if args.command == "compile":
        skills, monsters = compile_rows(write=args.write)
        print(json.dumps({"skills": len(skills), "monsters": len(monsters), "written": args.write}))
    elif args.command == "audit":
        result = audit()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        raise SystemExit(0 if result["passed"] else 1)
    else:
        payload = report(write=True)
        print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))
        raise SystemExit(0 if payload["summary"]["passed"] else 1)


if __name__ == "__main__":
    main()
