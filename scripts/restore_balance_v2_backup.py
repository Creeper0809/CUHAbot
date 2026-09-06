"""Guarded PostgreSQL restore utility for a Balance V2 season backup.

The command is dry-run by default and only inspects the custom-format archive.
An actual restore requires ``--execute``, ``--expected-season``, and an exact
confirmation string. It is intentionally not called by deployment scripts.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.migrate_balance_v2 import database_url


def inspect_backup(backup: Path) -> dict:
    backup = backup.resolve()
    if not backup.is_file() or backup.stat().st_size <= 0:
        raise FileNotFoundError(f"Backup is missing or empty: {backup}")
    result = subprocess.run(
        ["pg_restore", "--list", str(backup)],
        check=True,
        capture_output=True,
        text=True,
    )
    entries = [line for line in result.stdout.splitlines() if line and not line.startswith(";")]
    required = ("TABLE DATA public users", "TABLE DATA public user_inventory")
    missing = [needle for needle in required if not any(needle in entry for entry in entries)]
    if missing:
        raise RuntimeError(f"Backup does not contain required progression tables: {missing}")
    return {"backup": str(backup), "size": backup.stat().st_size, "entries": len(entries), "missing": []}


def restore(backup: Path, expected_season: str, confirmation: str) -> dict:
    expected_confirmation = f"RESTORE {expected_season}"
    if confirmation != expected_confirmation:
        raise ValueError(f"--confirm must exactly equal {expected_confirmation!r}")
    inspection = inspect_backup(backup)
    subprocess.run(
        [
            "pg_restore", "--clean", "--if-exists", "--no-owner",
            "--dbname", database_url(), str(backup.resolve()),
        ],
        check=True,
    )
    return {**inspection, "mode": "restored", "expected_season": expected_season}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backup", type=Path, required=True)
    parser.add_argument("--expected-season", required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--confirm", default="")
    args = parser.parse_args()
    result = (
        restore(args.backup, args.expected_season, args.confirm)
        if args.execute else
        {**inspect_backup(args.backup), "mode": "dry-run", "expected_season": args.expected_season}
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
