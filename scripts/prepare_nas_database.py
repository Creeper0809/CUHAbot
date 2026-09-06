"""Explicitly separate first installation from data-preserving release updates."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tortoise import Tortoise
from scripts.migrate_roguelike_reward_system import init_db


async def main():
    await init_db()
    conn = Tortoise.get_connection("default")
    rows = await conn.execute_query_dict("SELECT to_regclass('public.skill') AS table_name")
    populated = rows[0]["table_name"] is not None
    if populated:
        rows = await conn.execute_query_dict("SELECT EXISTS(SELECT 1 FROM skill) AS populated")
        populated = rows[0]["populated"]
    await Tortoise.close_connections()
    if populated:
        from scripts.update_beginner_static import main as update_main
        await update_main()
        return
    from scripts import seed_from_csv, seed_achievements
    await seed_from_csv.main(fresh=True)
    # Legacy first-install migrations remain explicit and never run on updates.
    import subprocess
    for script in ("seed_achievements", "migrate_roguelike_reward_system", "migrate_balance_v2",
                   "migrate_skill_ecosystem_v3", "migrate_itemization_v4", "migrate_beginner_recovery"):
        subprocess.run([sys.executable, str(Path(__file__).with_name(script + ".py"))], check=True)


if __name__ == "__main__":
    asyncio.run(main())
