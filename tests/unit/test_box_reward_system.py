import asyncio
import random

import pytest

from config import (
    BOX_CONFIGS, BOX_PITY_BY_ID, BoxConfig, BoxRewardConfig, BoxRewardType,
)
from models import Item, User
from models.game_system import BoxOpenReceipt, UserBoxPity
from models.user_inventory import UserInventory
from service.item.box_open_service import BoxOpenService, pity_chances, roll_atom


def test_soft_and_hard_pity_boundaries_are_exact():
    rule = BOX_PITY_BY_ID[5940]
    base, before_soft, hard = pity_chances(5940, rule.soft_start - 1)
    _, at_soft, _ = pity_chances(5940, rule.soft_start)
    _, at_hard, hard = pity_chances(5940, rule.hard_pity - 1)

    assert before_soft == base
    assert at_soft == min(0.50, base + 0.03)
    assert at_hard == 1.0
    assert hard


def test_100k_rolls_match_displayed_adjusted_probability():
    box_id = 5941
    failure_count = 12
    rule = BOX_PITY_BY_ID[box_id]
    _, displayed, _ = pity_chances(box_id, failure_count)
    rng = random.Random(20260813)
    rolls = 100_000
    successes = sum(
        roll_atom(box_id, failure_count, rng)[0].grade >= rule.target_grade
        for _ in range(rolls)
    )
    observed = successes / rolls
    assert abs(observed - displayed) <= 0.005


def test_hard_pity_never_returns_gold_or_below_target():
    for box_id, rule in BOX_PITY_BY_ID.items():
        rng = random.Random(box_id)
        for _ in range(1000):
            atom, _, adjusted, hard = roll_atom(box_id, rule.hard_pity - 1, rng)
            assert hard and adjusted == 1.0
            assert atom.reward_type != BoxRewardType.GOLD
            assert atom.grade >= rule.target_grade


@pytest.mark.asyncio
async def test_open_receipt_is_idempotent_and_pity_is_persistent(test_db, monkeypatch):
    monkeypatch.setitem(
        BOX_CONFIGS,
        5940,
        BoxConfig(5940, "test box", [BoxRewardConfig(BoxRewardType.GOLD, 1.0)]),
    )
    user = await User.create(discord_id=99112233, username="box-test")
    await Item.create(id=5940, name="test box")
    inventory = await UserInventory.create(user=user, item_id=5940, quantity=1)

    first = await BoxOpenService.open_boxes(user, inventory.id, 1, "interaction-1", rng=random.Random(7))
    replay = await BoxOpenService.open_boxes(user, inventory.id, 1, "interaction-1", rng=random.Random(999))

    assert len(first.outcomes) == 1
    assert replay.replayed
    assert replay.outcomes[0].to_dict() == first.outcomes[0].to_dict()
    assert await UserInventory.get_or_none(id=inventory.id) is None
    assert await BoxOpenReceipt.filter(interaction_id="interaction-1").count() == 1
    pity = await UserBoxPity.get(user=user, pity_group="low")
    assert pity.failure_count == 1


@pytest.mark.asyncio
async def test_pity_groups_are_independent(test_db):
    user = await User.create(discord_id=44112233, username="pity-test")
    await UserBoxPity.create(user=user, pity_group="low", failure_count=14)
    await UserBoxPity.create(user=user, pity_group="mid", failure_count=3)
    progress = await BoxOpenService.get_pity_progress(user)
    assert progress == {"low": 14, "mid": 3}
