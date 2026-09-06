"""Archive and reset all player progression for a Balance V2 season.

Dry-run is the default. Execution requires all of ``--execute``, an expected
season identifier, and a concrete PostgreSQL backup output path.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
from tortoise import Tortoise

from config import BALANCE_V2, SKILL_ID
from scripts.migrate_balance_v2 import database_url, migrate

load_dotenv()

DIRECT_TABLES = {
    "user_inventory": "user_id", "user_equipment": "user_id",
    "user_owned_skill": "user_id", "user_skill_deck": "user_id",
    "user_ultimate_deck": "user_id", "user_collection": "user_id",
    "user_achievement": "user_id", "user_deck_presets": "user_id",
    "skill_equip": "user_id",
    "user_raid_progress": "user_id", "user_tower_progress": "user_id",
    "dungeon_user_pos": "user_id", "combat_history": "user_id", "mail": "user_id",
    "user_box_pity": "user_id", "box_open_receipt": "user_id",
    "dungeon_run_record": "user_id",
}
RELATED_TABLES = {
    "auction_listing": ('seller_id=$1 OR buyer_id=$1', "user_id"),
    "auction_bid": ('bidder_id=$1', "user_id"),
    "auction_history": ('seller_id=$1 OR buyer_id=$1', "user_id"),
    "buy_order": ('buyer_id=$1 OR seller_id=$1', "user_id"),
    # Voice progression is shared, but MVP ownership is the only user link.
    # Store it in every matching user's archive while the full pg_dump remains
    # the authoritative whole-database restore.
    "voice_channel_level": ('mvp_user_id=$1', "discord_id"),
}
DELETE_TABLES = (
    "auction_bid", "auction_history", "buy_order", "auction_listing",
    "user_equipment", "user_inventory", "user_skill_deck", "skill_equip", "user_owned_skill",
    "user_ultimate_deck", "user_collection", "user_achievement", "user_deck_preset",
    "user_raid_progress", "user_tower_progress", "dungeon_user_pos", "combat_history",
    "mail", "user_box_pity", "box_open_receipt", "dungeon_run_record", "user_deck_presets",
    "voice_channel_level",
)


async def existing_tables(connection) -> set[str]:
    rows = await connection.execute_query_dict(
        "SELECT table_name FROM information_schema.tables WHERE table_schema='public'"
    )
    return {row["table_name"] for row in rows}


async def dry_run_summary(connection, season_id: str) -> dict:
    tables = await existing_tables(connection)
    counts = {}
    for table in DELETE_TABLES:
        if table in tables:
            result = await connection.execute_query_dict(f'SELECT COUNT(*) AS count FROM "{table}"')
            counts[table] = int(result[0]["count"])
    user_count = await connection.execute_query_dict("SELECT COUNT(*) AS count FROM users")
    return {
        "mode": "dry-run", "season_id": season_id, "profile": BALANCE_V2.version,
        "users": int(user_count[0]["count"]), "rows_to_reset": counts,
    }


async def progression_totals(connection, tables: set[str]) -> dict:
    totals: dict[str, object] = {}
    users = await connection.execute_query_dict(
        "SELECT COUNT(*) AS rows, COALESCE(SUM(gold),0) AS gold FROM users"
    )
    totals["users"] = int(users[0]["rows"])
    totals["gold"] = int(users[0]["gold"])
    specs = {
        "user_inventory": ("quantity", "items"),
        "user_owned_skill": ("quantity", "skills"),
        "user_inventory:enhancement": ("enhancement_level", "enhancement_levels"),
        "user_box_pity": ("failure_count", "pity_failures"),
    }
    for spec, (column, label) in specs.items():
        table = spec.split(":", 1)[0]
        if table not in tables:
            totals[label] = 0
            continue
        rows = await connection.execute_query_dict(
            f'SELECT COALESCE(SUM("{column}"),0) AS total FROM "{table}"'
        )
        totals[label] = int(rows[0]["total"])
    totals["table_rows"] = {}
    for table in DELETE_TABLES:
        if table in tables:
            rows = await connection.execute_query_dict(f'SELECT COUNT(*) AS count FROM "{table}"')
            totals["table_rows"][table] = int(rows[0]["count"])
    return totals


def create_backup(path: Path) -> None:
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f"Refusing to overwrite backup: {path}")
    command = ["pg_dump", "--format=custom", "--file", str(path), database_url()]
    subprocess.run(command, check=True)
    if not path.exists() or path.stat().st_size == 0:
        raise RuntimeError("pg_dump did not create a usable backup")


async def execute_reset(connection, season_id: str, backup_path: Path) -> dict:
    from tortoise.transactions import in_transaction

    tables = await existing_tables(connection)
    already = await connection.execute_query_dict("SELECT id FROM game_season WHERE id=$1", [season_id])
    if already:
        raise RuntimeError(f"Season transition {season_id!r} was already executed")

    users = await connection.execute_query_dict("SELECT * FROM users ORDER BY id")
    before_totals = await progression_totals(connection, tables)
    async with in_transaction() as transaction:
        await transaction.execute_query("UPDATE game_season SET is_active=FALSE, ended_at=NOW() WHERE is_active")
        await transaction.execute_query(
            "INSERT INTO game_season(id, profile_version, backup_path) VALUES($1,$2,$3)",
            [season_id, BALANCE_V2.version, str(backup_path.resolve())],
        )
        for user in users:
            snapshot: dict[str, object] = {"users": user, "tables": {}}
            for table, user_column in DIRECT_TABLES.items():
                if table not in tables:
                    continue
                rows = await transaction.execute_query_dict(
                    f'SELECT * FROM "{table}" WHERE "{user_column}"=$1 ORDER BY 1', [user["id"]]
                )
                snapshot["tables"][table] = rows
            for table, (where_clause, parameter_mode) in RELATED_TABLES.items():
                if table not in tables:
                    continue
                params = [user["discord_id"]] if parameter_mode == "discord_id" else [user["id"]]
                rows = await transaction.execute_query_dict(
                    f'SELECT * FROM "{table}" WHERE {where_clause} ORDER BY 1', params
                )
                snapshot["tables"][table] = rows
            snapshot["reconciliation"] = {
                "gold": int(user.get("gold") or 0),
                "item_quantity": sum(
                    int(row.get("quantity") or 0)
                    for row in snapshot["tables"].get("user_inventory", [])
                ),
                "skill_quantity": sum(
                    int(row.get("quantity") or 0)
                    for row in snapshot["tables"].get("user_owned_skill", [])
                ),
                "enhancement_levels": sum(
                    int(row.get("enhancement_level") or 0)
                    for row in snapshot["tables"].get("user_inventory", [])
                ),
                "pity_failures": sum(
                    int(row.get("failure_count") or 0)
                    for row in snapshot["tables"].get("user_box_pity", [])
                ),
            }
            await transaction.execute_query(
                """
                INSERT INTO season_progress_archive(season_id,user_id,discord_id,snapshot)
                VALUES($1,$2,$3,$4::jsonb)
                """,
                [season_id, user["id"], user["discord_id"], json.dumps(snapshot, default=str, ensure_ascii=False)],
            )
        for table in DELETE_TABLES:
            if table in tables:
                await transaction.execute_query(f'DELETE FROM "{table}"')

        base = BALANCE_V2.base_stats(1)
        await transaction.execute_query(
            """
            UPDATE users SET gold=0,hp=$1,now_hp=$1,attack=$2,ap_attack=$3,defense=$4,
                ap_defense=$5,speed=$6,accuracy=$7,evasion=$8,critical_rate=$9,
                critical_damage=$10,level=1,exp=0,stat_points=0,bonus_str=0,bonus_int=0,
                bonus_dex=0,bonus_vit=0,bonus_luk=0,attendance_streak=0,last_attendance=NULL,
                last_regen_time=NOW(),last_intervention_time=NULL
            """,
            [base.hp, base.attack, base.ap_attack, base.ad_defense, base.ap_defense,
             base.speed, base.accuracy, base.evasion, base.critical_rate, base.critical_damage],
        )
        basic_skill = SKILL_ID.BASIC_ATTACK_ID
        for user in users:
            if "user_owned_skill" in tables:
                await transaction.execute_query(
                    "INSERT INTO user_owned_skill(user_id,skill_id,quantity,equipped_count,created_at,updated_at) VALUES($1,$2,10,10,NOW(),NOW())",
                    [user["id"], basic_skill],
                )
            if "user_skill_deck" in tables:
                for slot in range(10):
                    await transaction.execute_query(
                        "INSERT INTO user_skill_deck(user_id,slot_index,skill_id) VALUES($1,$2,$3)",
                        [user["id"], slot, basic_skill],
                    )
            if "user_collection" in tables:
                await transaction.execute_query(
                    "INSERT INTO user_collection(user_id,collection_type,target_id,first_obtained_at) VALUES($1,'SKILL',$2,NOW())",
                    [user["id"], basic_skill],
                )
    after_totals = await progression_totals(connection, tables)
    return {
        "mode": "executed", "season_id": season_id,
        "users_archived": len(users), "backup": str(backup_path.resolve()),
        "reconciliation": {"before": before_totals, "after_reset": after_totals},
    }


async def run(args) -> dict:
    await migrate()
    await Tortoise.init(db_url=database_url(), modules={"models": ["models"]})
    connection = Tortoise.get_connection("default")
    try:
        if not args.execute:
            return await dry_run_summary(connection, args.expected_season)
        if not args.expected_season or not args.backup:
            raise ValueError("--execute requires --expected-season and --backup")
        create_backup(args.backup)
        return await execute_reset(connection, args.expected_season, args.backup)
    finally:
        await Tortoise.close_connections()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-season", default="balance-v2")
    parser.add_argument("--backup", type=Path)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(args)), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
