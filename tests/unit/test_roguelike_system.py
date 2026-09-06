import copy
import csv
import json
import random
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from config import ROGUELIKE, ULTIMATE_SKILL_IDS, RouteKind
from models import Monster
from service.dungeon.components.attack_components import DamageComponent
from service.dungeon.encounter_processor import _apply_roguelike_stat_scale
from service.dungeon.roguelike_routes import generate_route_offers, room_stat_scale
from service.dungeon.roguelike_settlement import apply_failure_penalty
from service.session import DungeonSession
from service.dungeon.skill import Skill
from service.dungeon.skill_augments import (
    AugmentId,
    available_augments,
    clone_with_augments,
    generate_augment_offers,
)
from views.roguelike_dungeon import RouteChoiceView


def _route_signature(offers):
    return [
        (offer.kind.value, offer.risk, offer.reward_grade, offer.payload)
        for offer in offers
    ]


def test_same_seed_reproduces_every_hidden_route_result():
    for room in range(1, 9):
        first = generate_route_offers(room, random.Random(8675309))
        second = generate_route_offers(room, random.Random(8675309))
        assert _route_signature(first) == _route_signature(second)
        assert len(first) == 3


def test_route_draws_are_independent_and_match_room_weights():
    rng = random.Random(20260813)
    counts = {kind: 0 for kind in RouteKind}
    draws = 100_000
    for _ in range(draws // 3 + 1):
        for offer in generate_route_offers(1, rng):
            counts[offer.kind] += 1
    total = sum(counts.values())
    expected = dict(ROGUELIKE.EARLY_WEIGHTS)
    for kind, weight in expected.items():
        assert abs(counts[kind] / total - weight / 100) < 0.005


def test_room_scaling_only_mutates_combat_copy():
    source = Monster(
        id=1, name="source", description="", hp=100, attack=20,
        defense=10, ap_attack=12, ap_defense=8, speed=10,
    )
    combat = source.copy()
    _apply_roguelike_stat_scale([combat], room_stat_scale(7))

    assert (source.hp, source.attack, source.defense) == (100, 20, 10)
    assert (combat.hp, combat.attack, combat.defense) == (120, 24, 12)
    assert combat.now_hp == combat.hp


def _skill(skill_id: int = 2000) -> Skill:
    component = DamageComponent()
    component._tag = "attack"
    component.apply_config({"ad_ratio": 1.0, "ap_ratio": 0.5}, "test")
    model = SimpleNamespace(
        id=skill_id, name="test", description="", attribute="neutral",
    )
    return Skill(model, [component])


def test_skill_augment_clone_never_mutates_cached_skill():
    original = _skill()
    before = {
        key: copy.deepcopy(value)
        for key, value in original.components[0].__dict__.items()
        if key != "skill"
    }
    clone = clone_with_augments(
        original,
        [AugmentId.POWER.value, AugmentId.MULTIHIT.value],
    )

    assert clone is not original
    assert clone.components[0] is not original.components[0]
    assert {
        key: value
        for key, value in original.components[0].__dict__.items()
        if key != "skill"
    } == before
    assert clone.components[0].hit_count == 2
    assert clone.components[0].ad_ratio != original.components[0].ad_ratio


def test_augment_rules_enforce_duplicates_limit_and_delivery_exclusion():
    skill = _skill()
    candidates = available_augments(
        skill,
        [AugmentId.MULTIHIT.value],
    )
    ids = {item.augment_id for item in candidates}
    assert AugmentId.MULTIHIT not in ids
    assert AugmentId.SPREAD not in ids
    assert len(generate_augment_offers(skill, [], random.Random(1))) == 3


def test_every_player_active_and_ultimate_has_three_valid_augments():
    with open("data/skills.csv", encoding="utf-8-sig", newline="") as source:
        rows = csv.reader(source)
        next(rows)
        checked = 0
        for row in rows:
            if row[2].lower() != "active" or row[10].upper() != "Y" or int(row[0]) == 1001:
                continue
            config = json.loads(row[9])
            components = []
            for value in config.get("components", []):
                component = SimpleNamespace(priority=0, **value)
                component._tag = value.get("tag")
                components.append(component)
            skill = Skill(
                SimpleNamespace(id=int(row[0]), name=row[1], description="", attribute=row[4]),
                components,
            )
            offers = generate_augment_offers(
                skill, [], random.Random(skill.id),
                is_ultimate=skill.id in ULTIMATE_SKILL_IDS,
            )
            assert len(offers) == 3, f"{skill.id} {skill.name}"
            checked += 1
    assert checked > 100


def test_exact_progression_contract_is_eight_rooms_then_boss():
    assert ROGUELIKE.ROUTE_ROOMS == 8
    assert ROGUELIKE.BOSS_STAGE == 9
    assert ROGUELIKE.AUGMENT_ROOMS == (2, 4, 6)
    assert ROGUELIKE.ROOM_STAT_SCALES == (0.9, 0.9, 1.0, 1.0, 1.1, 1.1, 1.2, 1.2)


def test_failure_settlement_keeps_items_and_retains_seventy_percent():
    session = DungeonSession(user_id=1)
    session.total_exp = 101
    session.total_gold = 99
    session.items_found = [5940, 5943]
    lost = apply_failure_penalty(session)
    assert (session.total_exp, session.total_gold) == (70, 69)
    assert lost == (31, 30)
    assert session.items_found == [5940, 5943]


def _interaction(user_id: int):
    interaction = SimpleNamespace(
        user=SimpleNamespace(id=user_id),
        response=SimpleNamespace(
            send_message=AsyncMock(), edit_message=AsyncMock(),
        ),
    )
    return interaction


@pytest.mark.asyncio
async def test_route_buttons_reject_other_owner_duplicate_and_stale_room():
    session = DungeonSession(user_id=1)
    session.exploration_step = 0
    offers = generate_route_offers(1, random.Random(3))
    view = RouteChoiceView(1, session, offers)

    other = _interaction(2)
    assert not await view.interaction_check(other)
    other.response.send_message.assert_awaited_once()

    first = _interaction(1)
    await view.children[0].callback(first)
    assert session.selected_route_token == offers[0].token
    first.response.edit_message.assert_awaited_once()

    duplicate = _interaction(1)
    await view.children[1].callback(duplicate)
    duplicate.response.send_message.assert_awaited_once()

    stale_session = DungeonSession(user_id=1)
    stale_session.exploration_step = 1
    stale = RouteChoiceView(1, stale_session, offers)
    stale_interaction = _interaction(1)
    await stale.children[0].callback(stale_interaction)
    stale_interaction.response.send_message.assert_awaited_once()
