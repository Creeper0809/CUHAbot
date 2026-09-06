import copy

import pytest

from models import Monster, Skill_Model, User
from scripts.seed_monsters import load_monsters_from_csv
from scripts.seed_skills import load_skills_from_csv
from scripts.update_monster_skill_connectivity import (
    REPAIRED_SKILL_IDS,
    update,
    verify,
)
from scripts.update_beginner_static import update as update_beginner_static


async def _seed_static() -> None:
    await Skill_Model.bulk_create([Skill_Model(**row) for row in load_skills_from_csv()])
    monsters = []
    for row in load_monsters_from_csv():
        stored = dict(row)
        stored.pop("level", None)
        monsters.append(Monster(**stored))
    await Monster.bulk_create(monsters)


@pytest.mark.asyncio
async def test_connectivity_update_is_complete_idempotent_and_preserves_users(test_db):
    await _seed_static()
    user = await User.create(discord_id=99101, username="preserved", gold=7654, exp=321)

    # Reproduce the deployed defect without altering any unrelated monster data.
    expected_slime = await Monster.get(id=1)
    original_hp = expected_slime.hp
    await Monster.all().update(skill_ids=[0] * 10, action_profile={})
    for skill_id in REPAIRED_SKILL_IDS:
        await Skill_Model.filter(id=skill_id).update(config={"components": []}, description="stale")

    first = await update()
    assert first["assignments_materialized"] == 65
    assert first["monsters_updated"] == 128
    assert await verify()
    slime = await Monster.get(id=1)
    assert 9001 in slime.skill_ids
    assert any(action.get("skill_id") == 9001 for action in slime.action_profile["actions"])
    assert slime.hp == original_hp
    assert (await Monster.get(id=31)).ap_attack == 360
    assert (await Monster.get(id=34)).attack == 545
    assert (await Monster.get(id=38)).ap_attack == 430
    preserved = await User.get(id=user.id)
    assert (preserved.gold, preserved.exp) == (7654, 321)

    snapshot = {
        row["id"]: (copy.deepcopy(row["skill_ids"]), copy.deepcopy(row["action_profile"]))
        for row in await Monster.all().values("id", "skill_ids", "action_profile")
    }
    second = await update()
    assert second == first
    assert snapshot == {
        row["id"]: (row["skill_ids"], row["action_profile"])
        for row in await Monster.all().values("id", "skill_ids", "action_profile")
    }
    assert (await User.get(id=user.id)).gold == 7654


@pytest.mark.asyncio
async def test_connectivity_update_refuses_partial_static_database(test_db):
    await _seed_static()
    await Monster.filter(id=1).delete()
    with pytest.raises(RuntimeError, match="Refusing partial connectivity update"):
        await update()


@pytest.mark.asyncio
async def test_populated_nas_update_path_applies_beginner_stats_and_connectivity(test_db):
    await _seed_static()
    user = await User.create(discord_id=99102, username="integrated", gold=4321)
    await Monster.filter(id=1).update(ap_attack=0, skill_ids=[0] * 10, action_profile={})

    result = await update_beginner_static()
    slime = await Monster.get(id=1)
    assert slime.ap_attack == 8
    assert 9001 in slime.skill_ids
    assert result["revision"] == "beginner-2026-09-v2"
    assert result["monster_skill_connectivity"]["assignments_materialized"] == 65
    assert (await User.get(id=user.id)).gold == 4321
