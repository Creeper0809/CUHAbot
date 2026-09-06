from collections import Counter
import asyncio

import pytest

from models import User, Skill_Model
from models.game_system import UserStarterRecovery
from models.user_owned_skill import UserOwnedSkill
from models.user_skill_deck import UserSkillDeck
from models.repos.users_repo import find_account_by_discordid
from service.player.user_service import UserService
from service.player.starter_recovery import ensure_account
from service.session import active_sessions, DungeonSession
from scripts.seed_skills import load_skills_from_csv


async def seed():
    await Skill_Model.bulk_create([Skill_Model(**s) for s in load_skills_from_csv()])


@pytest.mark.asyncio
async def test_registration_is_atomic_and_concurrent(test_db):
    await seed()
    results = await asyncio.gather(*(ensure_account(60001, "starter") for _ in range(8)))
    assert len({u.id for u in results}) == 1
    user = await find_account_by_discordid(60001)
    assert user.equipped_skill == UserService.DEFAULT_SKILL_DECK
    counts = Counter(user.equipped_skill)
    for row in await UserOwnedSkill.filter(user=user):
        assert row.quantity == row.equipped_count == counts[row.skill_id]
    assert await UserStarterRecovery.filter(user=user).count() == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("old_deck", [[], [1001] * 10, [1002] * 10])
async def test_legacy_repair_once_preserves_custom_deck_and_progress(test_db, old_deck):
    await seed()
    user = await User.create(discord_id=60002, username="legacy", gold=4321, exp=19, now_hp=1)
    for slot, skill_id in enumerate(old_deck):
        await UserSkillDeck.create(user=user, slot_index=slot, skill_id=skill_id)
    repaired = await ensure_account(user.discord_id, user.username)
    assert repaired.now_hp == 300
    assert repaired.gold == 4321 and repaired.exp == 19
    expected = old_deck if old_deck == [1002] * 10 else UserService.DEFAULT_SKILL_DECK
    assert repaired.equipped_skill == expected
    before = await UserOwnedSkill.filter(user=user).values("skill_id", "quantity", "equipped_count")
    await User.filter(id=user.id).update(now_hp=10)
    again = await ensure_account(user.discord_id, user.username)
    assert again.now_hp == 10
    assert before == await UserOwnedSkill.filter(user=user).values("skill_id", "quantity", "equipped_count")


@pytest.mark.asyncio
async def test_no_repair_during_run_and_failed_create_rolls_back(test_db, monkeypatch):
    await seed()
    user = await User.create(discord_id=60003, username="running", now_hp=7)
    active_sessions[user.discord_id] = DungeonSession(user_id=user.discord_id, user=user)
    try:
        await ensure_account(user.discord_id, user.username)
        assert not await UserStarterRecovery.filter(user=user).exists()
        assert (await User.get(id=user.id)).now_hp == 7
    finally:
        active_sessions.pop(user.discord_id)
    await ensure_account(user.discord_id, user.username)
    assert (await User.get(id=user.id)).now_hp == 300

    async def fail(user):
        await UserSkillDeck.create(user=user, slot_index=0, skill_id=1001)
        raise RuntimeError("injected initializer failure")
    monkeypatch.setattr(UserService, "_initialize_default_deck", fail)
    with pytest.raises(RuntimeError):
        await UserService.create_user(60004, "rollback")
    assert not await User.filter(discord_id=60004).exists()
