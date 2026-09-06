"""On a restored *_beginner_check DB: verify two migrations preserve every user table."""
import asyncio
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tortoise import Tortoise
from scripts.migrate_roguelike_reward_system import init_db
from scripts.update_beginner_static import update


async def fingerprints():
    conn = Tortoise.get_connection("default")
    tables = await conn.execute_query_dict("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")
    result = {}
    for record in tables:
        table = record["tablename"]
        if table in {"monster", "skill", "user_starter_recovery"}:
            continue
        if not re.fullmatch(r"[a-z_]+", table):
            raise ValueError(table)
        values = await conn.execute_query_dict(f'SELECT count(*) AS rows, md5(COALESCE(string_agg(row_hash, \'\' ORDER BY row_hash), \'\')) AS hash FROM (SELECT md5(row_to_json(t)::text) AS row_hash FROM "{table}" t) s')
        result[table] = values[0]
    return result


async def main():
    if not os.environ.get("DATABASE_TABLE", "").endswith("_beginner_check"):
        raise RuntimeError("Use a restored isolated *_beginner_check database only")
    try:
        await init_db()
        before = await fingerprints()
        await update()
        after = await fingerprints()
        assert before == after, "First migration changed preserved tables"
        await update()
        assert before == await fingerprints(), "Second migration changed preserved tables"
        concurrency = await check_registration()
        assert before == await fingerprints(), "Temporary registration checks leaked user data"
        print(json.dumps({"passed": True, "tables": before, "registration": concurrency}, sort_keys=True))
    finally:
        await Tortoise.close_connections()


async def check_registration():
    from collections import Counter
    from models import User
    from models.user_owned_skill import UserOwnedSkill
    from models.user_skill_deck import UserSkillDeck
    from service.player.user_service import UserService
    from service.player.starter_recovery import ensure_account
    from exceptions import UserAlreadyExistsError
    snowflake = 890000000000000091
    assert not await User.filter(discord_id=snowflake).exists()
    try:
        attempts = await asyncio.gather(
            *(UserService.create_user(snowflake, "isolated beginner concurrency") for _ in range(12)),
            return_exceptions=True)
        assert sum(isinstance(result, User) for result in attempts) == 1
        assert sum(isinstance(result, UserAlreadyExistsError) for result in attempts) == 11
        user = await User.get(discord_id=snowflake)
        counts = Counter(UserService.DEFAULT_SKILL_DECK)
        rows = await UserOwnedSkill.filter(user=user)
        assert {r.skill_id: (r.quantity, r.equipped_count) for r in rows} == {s: (n, n) for s,n in counts.items()}
        await asyncio.gather(*(ensure_account(snowflake, "repeat") for _ in range(12)))
        assert await UserSkillDeck.filter(user=user).count() == 10
        assert sum(r.quantity for r in await UserOwnedSkill.filter(user=user)) == 10
        await user.delete()
        legacy = await User.create(discord_id=snowflake, username="legacy", now_hp=1, gold=4123, exp=19)
        await asyncio.gather(*(ensure_account(snowflake, "legacy") for _ in range(12)))
        again = await User.get(id=legacy.id)
        assert (again.now_hp, again.gold, again.exp) == (300, 4123, 19)
        assert await UserSkillDeck.filter(user=legacy).count() == 10
        assert sum(r.quantity for r in await UserOwnedSkill.filter(user=legacy)) == 10
        return {"concurrent_creates": 12, "created": 1, "repeat_repairs": 12,
                "legacy_concurrent_repairs": 12, "legacy_progress_preserved": True, "granted_copies": 10}
    finally:
        await User.filter(discord_id=snowflake).delete()


if __name__ == "__main__":
    asyncio.run(main())
