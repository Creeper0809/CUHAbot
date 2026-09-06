"""Targeted, transactional static update. Never seed, truncate, delete, or reset users."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tortoise import Tortoise
from tortoise.transactions import in_transaction
from models import Monster, Skill_Model
from config.beginner_balance import MONSTER_STATS, REVISION
from scripts.migrate_beginner_recovery import migrate
from scripts.migrate_roguelike_reward_system import init_db
from scripts.seed_skills import load_skills_from_csv
from scripts.update_monster_skill_connectivity import update_using_db as update_connectivity


async def update():
    # DDL is idempotent and must complete before opening the static-data transaction.
    await migrate()
    async with in_transaction() as connection:
        for monster_id, (hp, ad, ap, defense) in MONSTER_STATS.items():
            changed = await Monster.filter(id=monster_id).using_db(connection).update(
                hp=hp, attack=ad, ap_attack=ap, defense=defense, ap_defense=defense)
            if changed != 1:
                raise RuntimeError(f"Missing static monster {monster_id}; refusing partial update")
        split = next(row for row in load_skills_from_csv() if row["id"] == 9545)
        if await Skill_Model.filter(id=9545).using_db(connection).update(
            config=split["config"], description=split["description"]
        ) != 1:
            raise RuntimeError("Missing static split skill 9545")
        connectivity = await update_connectivity(connection)
    return {"revision": REVISION, "monster_ids": sorted(MONSTER_STATS), "skill_ids": [9545],
            "monster_skill_connectivity": connectivity}


async def main():
    try:
        await init_db()
        print(await update())
    finally:
        await Tortoise.close_connections()


if __name__ == "__main__":
    asyncio.run(main())
