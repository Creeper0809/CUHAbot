import copy
import logging
import random

import pytest
from tortoise import Tortoise
from models import User, Monster, UserStatEnum
from models.repos import static_cache
from service.dungeon.components import get_component_by_tag
from service.dungeon.components.attack_components import DamageComponent
from service.dungeon.components.modular_combat_components import AttackComponent
from service.dungeon.combat_executor import _decrement_status_durations
from service.dungeon.status import apply_status_effect, can_entity_act
from service.dungeon.skill import Skill
from tools.beginner_runtime import Harness, seed_fixture


def test_registered_attack_uses_v2_curve_and_real_crit_and_augment(monkeypatch):
    component = get_component_by_tag("attack")
    assert type(component) is AttackComponent and isinstance(component, DamageComponent)
    component.apply_config({"ad_ratio": 1.0}, "probe")
    user = User(discord_id=7000, username="probe", attack=100, critical_rate=70, critical_damage=250)
    monster = Monster(id=1, name="target", description="", hp=10000, attack=1, defense=100)
    from models.skill import Skill_Model
    skill = Skill(Skill_Model(id=1001, name="probe", config={}), [component])
    monkeypatch.setattr(random, "uniform", lambda *a: 0)
    monkeypatch.setattr(random, "random", lambda: .01)
    monkeypatch.setattr(random, "randint", lambda *a: 1)
    skill.on_turn(user, monster)
    # V2 50% mitigation, natural crit 250%; legacy subtraction yielded 1.
    assert monster.hp - monster.now_hp == 125
    monster.now_hp = monster.hp
    skill.roguelike_overload = .45
    skill.on_turn(user, monster)
    assert monster.hp - monster.now_hp > 125


@pytest.mark.parametrize("effect", ["stun", "freeze", "paralyze"])
def test_one_turn_cc_expires_after_lost_action(effect):
    user = User(discord_id=7001, username="cc")
    apply_status_effect(user, effect, duration=1)
    assert not can_entity_act(user)
    _decrement_status_durations(user)
    assert can_entity_act(user)


@pytest.mark.asyncio
async def test_real_novice_runtime_fixed_seeds_and_static_cache_preservation():
    await seed_fixture()
    try:
        before = {key: (value.hp, value.attack, value.ap_attack, copy.deepcopy(value.action_profile))
                  for key, value in static_cache.monster_cache_by_id.items()}
        for level, dungeon, strategy, mode, seed in ((1,1,"random","starter",1), (5,2,"elite","starter",4),
                                                     (1,1,"random","basic",4), (1,1,"random","empty",4)):
            harness = Harness(strategy, capture_ui=True)
            first = await harness.run(level, dungeon, seed, mode)
            again = await harness.run(level, dungeon, seed, mode)
            assert first["passed"] and again["passed"]
            assert first["encounters"] == again["encounters"]
            assert first["initial"]["equipment_ids"] == []
            assert all(e["all_enemies_dead"] for e in first["encounters"])
            assert any(p["components"] for p in harness.transport.payloads)
        after = {key: (value.hp, value.attack, value.ap_attack, value.action_profile)
                 for key, value in static_cache.monster_cache_by_id.items()}
        assert before == after
    finally:
        await Tortoise.close_connections()


@pytest.mark.asyncio
async def test_no_rest_eight_elites_heals_first_and_late_dots(monkeypatch):
    from config import RouteKind
    from service.dungeon.roguelike_routes import make_offer
    await seed_fixture()
    original_shuffle = random.shuffle

    def heals_first(cards):
        original_shuffle(cards)
        if set(cards) <= {1001, 1002, 1003, 2001, 2003}:
            cards.sort(key=lambda sid: sid in {2001, 2003})  # pop heals first

    monkeypatch.setattr(random, "shuffle", heals_first)

    class AdversarialHarness(Harness):
        async def choose(self, session, *args):
            room = session.exploration_step + 1
            if room == 7:
                apply_status_effect(session.user, "poison", duration=3)
                apply_status_effect(session.user, "bleed", duration=3)
            # Deliberately adversarial fixture, not the production generator.
            return make_offer(RouteKind.ELITE, room, session.run_rng)

    try:
        for level, dungeon in [(1, 1), (5, 2)]:
            for seed in range(10):
                run = await AdversarialHarness("elite").run(level, dungeon, seed)
                assert run["passed"], (level, seed)
                assert len(run["encounters"]) == 9
                assert all(e["all_enemies_dead"] for e in run["encounters"])
    finally:
        await Tortoise.close_connections()


@pytest.mark.asyncio
@pytest.mark.parametrize("exit_kind", ["timeout", "return"])
async def test_noncombat_exit_is_not_counted_as_clear_and_keeps_box(exit_kind):
    from service.item.inventory_service import InventoryService
    await seed_fixture()

    class ExitHarness(Harness):
        async def choose(self, session, *args):
            await InventoryService.add_item(session.user, 5940, 1)
            session.items_found.append(5940)
            session.total_exp, session.total_gold = 50, 100
            session.ended = exit_kind == "return"
            return None

    try:
        result = await ExitHarness("random").run(1, 1, 441)
        assert result["outcome"] == exit_kind and not result["passed"]
        assert result["death_room"] is None
        assert result["settled_exp"] == (50 if exit_kind == "return" else 35)
        assert result["gold"] == (100 if exit_kind == "return" else 70)
        assert result["inventory"] == [{"item_id": 5940, "quantity": 1}]
    finally:
        await Tortoise.close_connections()
