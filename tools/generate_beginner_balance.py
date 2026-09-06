"""Deterministically patch only authored entry monster numbers; emit a review diff."""
import csv
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from config.beginner_balance import MONSTER_STATS, REVISION


def generate():
    path = ROOT / "data/monsters.csv"
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fields, rows = reader.fieldnames, list(reader)
    changes = []
    report = ROOT / "reports/beginner-static-changes.json"
    original = {r["id"]: r["before"] for r in json.loads(report.read_text(encoding="utf-8")).get("changes", [])} if report.exists() else {}
    for row in rows:
        monster_id = int(row["ID"])
        if monster_id not in MONSTER_STATS:
            continue
        hp, ad, ap, defense = MONSTER_STATS[monster_id]
        values = {"HP": hp, "Attack": ad, "AP_Attack": ap, "Defense": defense, "AP_Defense": defense}
        before = original.get(monster_id, {key: row[key] for key in values})
        row.update({key: str(value) for key, value in values.items()})
        changes.append({"id": monster_id, "name": row["이름"], "before": before, "after": values,
                        "reason": "minimum-area-level starter, no gear/enhancement/allocated stats; actual FSM action burst"})
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    report = ROOT / "reports/beginner-static-changes.json"
    report.parent.mkdir(exist_ok=True)
    report.write_text(json.dumps({"revision": REVISION, "changes": changes}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Updated {len(changes)} entry monster definitions; no upper-area rows changed")


if __name__ == "__main__":
    generate()
