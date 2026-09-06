"""Data-preserving deployment of the authored monster-skill graph.

Only the two monster behavior fields and the three repaired skill definitions are
updated.  User ownership, decks, inventory, progression, and combat records are
never seeded or rewritten here.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tortoise import Tortoise
from tortoise.backends.base.client import BaseDBAsyncClient
from tortoise.transactions import in_transaction

from models import Monster, Skill_Model
from scripts.migrate_roguelike_reward_system import init_db
from scripts.seed_monsters import load_monsters_from_csv
from scripts.seed_skills import load_skills_from_csv
from tools.skill_ecosystem_v3 import audit, load_assignment_manifest


REVISION = "monster-skill-connectivity-2026-09-06-v1"
REPAIRED_SKILL_IDS = frozenset({9006, 9199, 9219})


def _expected_rows() -> tuple[dict[int, dict], dict[int, dict], set[int]]:
    report = audit()
    if not report["passed"]:
        raise RuntimeError(f"V3 connectivity audit failed: {report['errors']}")

    monsters = {row["id"]: row for row in load_monsters_from_csv()}
    skills = {row["id"]: row for row in load_skills_from_csv()}
    assignment_ids = {
        int(row["skill_id"])
        for row in load_assignment_manifest()["assignments"]
    }
    if len(monsters) != 128 or len(assignment_ids) != 65:
        raise RuntimeError(
            f"Refusing incomplete authored graph: monsters={len(monsters)}, assignments={len(assignment_ids)}"
        )
    missing_skills = (assignment_ids | REPAIRED_SKILL_IDS) - skills.keys()
    if missing_skills:
        raise RuntimeError(f"Assigned skill definitions missing from CSV: {sorted(missing_skills)}")
    return monsters, skills, assignment_ids


async def update_using_db(connection: BaseDBAsyncClient) -> dict:
    """Apply the graph using an existing transaction connection."""
    monsters, skills, assignment_ids = _expected_rows()

    database_monsters = set(
        await Monster.all().using_db(connection).values_list("id", flat=True)
    )
    database_skills = set(
        await Skill_Model.filter(id__in=assignment_ids | REPAIRED_SKILL_IDS)
        .using_db(connection)
        .values_list("id", flat=True)
    )
    missing_monsters = monsters.keys() - database_monsters
    missing_db_skills = (assignment_ids | REPAIRED_SKILL_IDS) - database_skills
    if missing_monsters or missing_db_skills:
        raise RuntimeError(
            "Refusing partial connectivity update: "
            f"missing monsters={sorted(missing_monsters)}, skills={sorted(missing_db_skills)}"
        )

    stat_override_ids = {
        int(monster_id)
        for monster_id in (load_assignment_manifest().get("stat_overrides") or {})
    }
    for monster_id, row in monsters.items():
        values = {"skill_ids": row["skill_ids"], "action_profile": row["action_profile"]}
        if monster_id in stat_override_ids:
            values.update(attack=row["attack"], ap_attack=row["ap_attack"])
        await (
            Monster.filter(id=monster_id)
            .using_db(connection)
            .update(**values)
        )

    for skill_id in REPAIRED_SKILL_IDS:
        row = skills[skill_id]
        await (
            Skill_Model.filter(id=skill_id)
            .using_db(connection)
            .update(config=row["config"], description=row["description"])
        )

    return {
        "revision": REVISION,
        "monsters_updated": len(monsters),
        "assignments_materialized": len(assignment_ids),
        "skills_repaired": sorted(REPAIRED_SKILL_IDS),
        "secondary_attack_stats_repaired": sorted(stat_override_ids),
    }


async def update() -> dict:
    async with in_transaction() as connection:
        return await update_using_db(connection)


async def verify() -> dict:
    """Verify the persisted database rather than merely re-reading CSV files."""
    monsters, _, assignment_ids = _expected_rows()
    persisted = {
        row["id"]: row
        for row in await Monster.all().values(
            "id", "skill_ids", "action_profile", "attack", "ap_attack"
        )
    }
    stat_override_ids = {
        int(monster_id)
        for monster_id in (load_assignment_manifest().get("stat_overrides") or {})
    }
    mismatched = [
        monster_id
        for monster_id, expected in monsters.items()
        if persisted.get(monster_id, {}).get("skill_ids") != expected["skill_ids"]
        or persisted.get(monster_id, {}).get("action_profile") != expected["action_profile"]
        or (
            monster_id in stat_override_ids
            and (
                persisted.get(monster_id, {}).get("attack") != expected["attack"]
                or persisted.get(monster_id, {}).get("ap_attack") != expected["ap_attack"]
            )
        )
    ]
    connected = {
        int(skill_id)
        for row in persisted.values()
        for skill_id in (row.get("skill_ids") or [])
        if int(skill_id) != 0
    }
    missing = assignment_ids - connected
    if mismatched or missing:
        raise RuntimeError(
            f"Persisted monster graph mismatch: monsters={mismatched}, assignments={sorted(missing)}"
        )
    return {
        "revision": REVISION,
        "verified_monsters": len(persisted),
        "verified_assignments": len(assignment_ids),
    }


async def main() -> None:
    try:
        await init_db()
        result = await update()
        result["verification"] = await verify()
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    finally:
        await Tortoise.close_connections()


if __name__ == "__main__":
    asyncio.run(main())
