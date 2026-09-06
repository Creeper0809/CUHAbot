"""Exhaustive static audit for player-facing game data and runtime contracts.

The audit intentionally reads the authored V3 manifests instead of the generated
CSV so a broken source contract cannot be hidden by the compiler.  It also uses
Python's AST to compare every component config key with the keys its registered
runtime component actually reads.
"""

from __future__ import annotations

import argparse
import ast
import csv
import json
import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
DESIGN_DIR = ROOT / "data" / "skill_design"
COMPONENT_DIR = ROOT / "service" / "dungeon" / "components"

RAW_TOKEN_RE = re.compile(r"(?<![A-Za-z0-9])(?:[a-z][a-z0-9]*_[a-z0-9_]+)(?![A-Za-z0-9])")
PLACEHOLDER_RE = re.compile(r"\{[A-Za-z_][A-Za-z0-9_]*\}|%\([A-Za-z_][A-Za-z0-9_]*\)[a-z]")


@dataclass
class Finding:
    severity: str
    category: str
    subject: str
    message: str


@dataclass
class AuditResult:
    counts: dict[str, int] = field(default_factory=dict)
    findings: list[Finding] = field(default_factory=list)

    @property
    def errors(self) -> list[Finding]:
        return [finding for finding in self.findings if finding.severity == "error"]

    @property
    def warnings(self) -> list[Finding]:
        return [finding for finding in self.findings if finding.severity == "warning"]


def _load_skill_contracts() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(DESIGN_DIR.glob("*.json")):
        if path.name.startswith("_"):
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError(f"{path}: expected a list")
        rows.extend(payload)
    return rows


def _iter_components(contract: dict[str, Any]) -> Iterable[dict[str, Any]]:
    mechanics = contract.get("mechanics") or {}
    components = mechanics.get("components") or []
    for component in components:
        if isinstance(component, dict):
            yield component


def _decorator_tag(decorator: ast.expr) -> str | None:
    if not isinstance(decorator, ast.Call) or not decorator.args:
        return None
    func = decorator.func
    if not isinstance(func, ast.Name) or func.id != "register_skill_with_tag":
        return None
    arg = decorator.args[0]
    return arg.value if isinstance(arg, ast.Constant) and isinstance(arg.value, str) else None


def _literal_config_keys(node: ast.AST) -> set[str]:
    keys: set[str] = set()
    for child in ast.walk(node):
        if not isinstance(child, ast.Call) or not isinstance(child.func, ast.Attribute):
            continue
        if child.func.attr != "get" or not isinstance(child.func.value, ast.Name):
            continue
        if child.func.value.id != "config" or not child.args:
            continue
        arg = child.args[0]
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            keys.add(arg.value)
    return keys


def _runtime_component_keys() -> dict[str, set[str]]:
    classes: dict[str, list[ast.ClassDef]] = defaultdict(list)
    tagged: dict[str, list[ast.ClassDef]] = defaultdict(list)
    for path in sorted(COMPONENT_DIR.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:
            if not isinstance(node, ast.ClassDef):
                continue
            classes[node.name].append(node)
            tags = [tag for tag in (_decorator_tag(d) for d in node.decorator_list) if tag]
            for tag in tags:
                tagged[tag].append(node)

    def inherited_keys(node: ast.ClassDef, seen: set[int] | None = None) -> set[str]:
        seen = set(seen or ())
        if id(node) in seen:
            return set()
        seen.add(id(node))
        keys = _literal_config_keys(node)
        for base in node.bases:
            if isinstance(base, ast.Name):
                for candidate in classes.get(base.id, []):
                    keys.update(inherited_keys(candidate, seen))
            elif isinstance(base, ast.Attribute):
                for candidate in classes.get(base.attr, []):
                    keys.update(inherited_keys(candidate, seen))
        return keys

    result: dict[str, set[str]] = defaultdict(set)
    for tag, nodes in tagged.items():
        for node in nodes:
            result[tag].update(inherited_keys(node))
    return dict(result)


def _scan_text(result: AuditResult, category: str, subject: str, value: Any) -> None:
    if value is None:
        return
    if isinstance(value, dict):
        for key, nested in value.items():
            _scan_text(result, category, f"{subject}.{key}", nested)
        return
    if isinstance(value, list):
        for index, nested in enumerate(value):
            _scan_text(result, category, f"{subject}[{index}]", nested)
        return
    if not isinstance(value, str):
        return

    if "�" in value:
        result.findings.append(Finding("error", category, subject, "replacement character in text"))
    placeholders = PLACEHOLDER_RE.findall(value)
    if placeholders:
        result.findings.append(
            Finding("error", category, subject, f"unresolved placeholders: {', '.join(placeholders)}")
        )
    raw_tokens = sorted(set(RAW_TOKEN_RE.findall(value)))
    if raw_tokens:
        result.findings.append(
            Finding("error", category, subject, f"internal tokens exposed: {', '.join(raw_tokens)}")
        )


def _audit_skill_contracts(result: AuditResult, contracts: list[dict[str, Any]]) -> None:
    from service.dungeon.status import status_effect_register
    from service.skill.design_v3 import describe_component

    runtime_keys = _runtime_component_keys()
    from service.dungeon.skill import PASSIVE_EFFECT_KEYS

    runtime_keys.setdefault("passive_buff", set()).update(PASSIVE_EFFECT_KEYS)
    tag_counts: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()

    allowed_metadata = {"tag", "priority"}
    semantic_stat_values = {
        "buff": {
            "", "attack", "defense", "speed", "all", "random", "random_all",
            "invincible", "invulnerability", "evasion", "damage_reduction",
            "hit_stack_attack",
        },
        "debuff": {
            "", "attack", "defense", "speed", "all", "all_debuffs", "random",
            "random_all", "accuracy", "evasion", "heal_received", "heal_block",
            "random_redistribute", "buff_reverse", "buff_duration", "skill_seal",
            "effect_reverse", "taunt", "death_mark", "self_destruct",
        },
    }

    for contract in contracts:
        skill_id = contract.get("id", "?")
        name = contract.get("name", "?")
        subject = f"skill:{skill_id}:{name}"
        if contract.get("manual_revision") in (None, ""):
            result.findings.append(Finding("error", "skill-contract", subject, "manual_revision missing"))

        for component in _iter_components(contract):
            tag = str(component.get("tag", ""))
            tag_counts[tag] += 1
            if tag not in runtime_keys:
                result.findings.append(Finding("error", "component-tag", subject, f"unregistered tag: {tag}"))
                continue

            supported = runtime_keys[tag] | allowed_metadata
            unknown = sorted(set(component) - supported)
            if unknown:
                result.findings.append(
                    Finding("error", "component-config", subject, f"{tag} unread keys: {', '.join(unknown)}")
                )

            if tag == "status":
                status_type = str(component.get("type", ""))
                status_counts[status_type] += 1
                if status_type not in status_effect_register:
                    result.findings.append(
                        Finding("error", "status-type", subject, f"unregistered status: {status_type}")
                    )
            elif tag in semantic_stat_values:
                stat = str(component.get("stat", ""))
                if stat not in semantic_stat_values[tag]:
                    result.findings.append(
                        Finding("error", "component-value", subject, f"unsupported {tag}.stat: {stat}")
                    )

            _scan_text(result, "skill-render", subject, describe_component(component))

        # These fields are shown in Discord after localization.  Scan the rendered
        # text, not the authored machine tags themselves.
        from utils.game_text import design_tags_text, family_label, localize_internal_terms, role_label

        rendered_design = {
            "fantasy": localize_internal_terms(contract.get("fantasy", "")),
            "purpose": localize_internal_terms(contract.get("purpose", "")),
            "decision": localize_internal_terms(contract.get("decision", "")),
            "fallback": localize_internal_terms(contract.get("fallback", "")),
            "family": family_label(contract.get("family", "")),
            "role": role_label(contract.get("role", "")),
            "setup_tags": design_tags_text(contract.get("setup_tags", [])),
            "payoff_tags": design_tags_text(contract.get("payoff_tags", [])),
        }
        _scan_text(result, "skill-design-render", subject, rendered_design)

    result.counts["skills"] = len(contracts)
    result.counts["skill_components"] = sum(tag_counts.values())
    result.counts["component_tags"] = len(tag_counts)
    result.counts["status_types"] = len(status_counts)


def _audit_csv_text(result: AuditResult) -> None:
    public_columns: dict[str, tuple[str, ...]] = {
        # 키워드는 안정적인 내부 태그로 저장하고 모든 Discord 표시 경로에서
        # design_tag_label() 로 번역한다. 원본 CSV가 아닌 렌더러를 감사 대상으로 삼는다.
        "skills.csv": ("이름", "효과", "획득처"),
        "items_consumable.csv": ("이름", "카테고리", "효과", "지속", "범위", "획득처"),
        "items_equipment.csv": ("이름", "슬롯", "계열", "특수 효과", "세트", "획득처", "description"),
        "items_enhancement.csv": ("이름", "카테고리", "효과", "실패 시", "획득처"),
        "items_material.csv": ("이름", "설명", "획득처", "용도"),
        "monsters.csv": ("이름", "설명", "타입", "속성", "종족", "던전", "스킬", "패시브", "드롭"),
        "set_effects.csv": ("세트이름", "설명", "효과설명"),
        "dungeons.csv": ("이름", "설명", "타입", "주요 속성"),
    }

    for filename, columns in public_columns.items():
        path = ROOT / "data" / filename
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        result.counts[f"rows:{filename}"] = len(rows)
        for index, row in enumerate(rows, start=2):
            for column in columns:
                _scan_text(result, "csv-render", f"{filename}:{index}:{column}", row.get(column, ""))


def _audit_equipment_semantics(result: AuditResult) -> None:
    path = ROOT / "data" / "items_equipment.csv"
    if not path.exists():
        return
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    weapon_words = ("검", "도끼", "단검", "낫", "창", "활", "지팡이", "메이스", "총")
    for row in rows:
        name = row.get("이름", "")
        description = row.get("description", "")
        name_kinds = {word for word in weapon_words if word in name}
        desc_kinds = {word for word in weapon_words if word in description}
        if name_kinds and desc_kinds and name_kinds.isdisjoint(desc_kinds):
            result.findings.append(
                Finding(
                    "warning",
                    "equipment-semantics",
                    f"equipment:{row.get('ID')}:{name}",
                    f"name implies {sorted(name_kinds)}, description implies {sorted(desc_kinds)}",
                )
            )


def run_audit() -> AuditResult:
    # Importing the package registers every component/status class.
    import service.dungeon.components  # noqa: F401

    result = AuditResult()
    contracts = _load_skill_contracts()
    _audit_skill_contracts(result, contracts)
    _audit_csv_text(result)
    _audit_equipment_semantics(result)
    result.counts["errors"] = len(result.errors)
    result.counts["warnings"] = len(result.warnings)
    return result


def write_report(result: AuditResult, report_dir: Path) -> tuple[Path, Path]:
    report_dir.mkdir(parents=True, exist_ok=True)
    json_path = report_dir / "game_bug_audit.json"
    md_path = report_dir / "game_bug_audit.md"
    json_path.write_text(
        json.dumps(
            {"counts": result.counts, "findings": [asdict(finding) for finding in result.findings]},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    lines = ["# Game bug audit", "", "## Counts", ""]
    lines.extend(f"- {key}: {value}" for key, value in sorted(result.counts.items()))
    lines.extend(["", "## Findings", ""])
    if not result.findings:
        lines.append("No findings.")
    else:
        for finding in result.findings:
            lines.append(
                f"- **{finding.severity.upper()} / {finding.category}** "
                f"`{finding.subject}` — {finding.message}"
            )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report-dir", type=Path, default=ROOT / "reports")
    parser.add_argument("--allow-errors", action="store_true")
    args = parser.parse_args()

    result = run_audit()
    json_path, md_path = write_report(result, args.report_dir)
    print(json.dumps(result.counts, ensure_ascii=False, sort_keys=True))
    print(json_path)
    print(md_path)
    return 0 if args.allow_errors or not result.errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
