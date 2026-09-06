from types import SimpleNamespace

import pytest

from models import Monster, User, UserStatEnum


def _monster(monster_id: int, name: str, *, hp: int = 1000, attack: int = 100, ap: int = 100):
    return Monster(
        id=monster_id,
        name=name,
        description="",
        hp=hp,
        attack=attack,
        ap_attack=ap,
        defense=0,
        ap_defense=0,
        accuracy=95,
        evasion=5,
    )


def test_exhaustive_game_data_and_public_render_audit_is_clean():
    from tools.game_bug_audit import run_audit

    result = run_audit()
    assert result.counts["skills"] == 647
    assert result.counts["skill_components"] == 994
    assert result.errors == []
    assert result.warnings == []


@pytest.mark.parametrize("effect", ["fear", "root", "charm"])
def test_new_control_statuses_really_block_actions(effect):
    from service.dungeon.status import apply_status_effect, can_entity_act

    target = _monster(1, "target")
    assert apply_status_effect(target, effect, duration=2)
    assert not can_entity_act(target)


def test_status_payload_dot_blind_taunt_and_cleanse_protection(monkeypatch):
    from service.dungeon.status import (
        apply_status_effect,
        get_taunt_source,
        process_status_ticks,
        remove_status_effects,
    )

    monkeypatch.setattr("service.dungeon.status.helpers.random.random", lambda: 0.99)
    source = _monster(1, "source")
    target = _monster(2, "target", hp=1000)
    apply_status_effect(target, "blind", duration=2)
    assert target.get_stat()[UserStatEnum.ACCURACY] == 65
    apply_status_effect(target, "taunt", duration=2, source=source)
    assert get_taunt_source(target) is source
    apply_status_effect(
        target,
        "dot",
        duration=2,
        effect_config={"damage_type": "max_hp_percent", "value": 0.10, "cannot_cleanse": True},
    )
    assert remove_status_effects(target, count=99, filter_debuff=True)
    assert any(getattr(value, "effect_type", "") == "dot" for value in target.status)
    before = target.now_hp
    assert process_status_ticks(target)
    assert before - target.now_hp == 100


def test_status_component_honors_all_target_scope(monkeypatch):
    from service.dungeon.components.special_components import StatusComponent

    attacker = _monster(1, "caster")
    first, second = _monster(2, "first"), _monster(3, "second")
    component = StatusComponent()
    component.apply_config({"type": "fear", "target": "all", "chance": 1.0, "duration": 1}, "terror")
    monkeypatch.setattr(
        "service.dungeon.components.targeting_utils.resolve_targets",
        lambda *_: [first, second],
    )
    component.on_turn(attacker, first)
    assert [getattr(value, "effect_type", "") for value in first.status] == ["fear"]
    assert [getattr(value, "effect_type", "") for value in second.status] == ["fear"]


def test_aoe_damage_component_hits_each_target_once(monkeypatch):
    from service.dungeon.components.attack_components import DamageComponent

    attacker = _monster(1, "caster")
    first, second = _monster(2, "first"), _monster(3, "second")
    component = DamageComponent()
    component.apply_config(
        {"damage_type": "fixed", "value": 100, "target": "all", "cannot_evade": True},
        "blast",
    )
    monkeypatch.setattr(
        "service.dungeon.components.targeting_utils.resolve_targets",
        lambda *_: [first, second],
    )
    component.on_turn(attacker, first)
    assert first.now_hp == 900
    assert second.now_hp == 900


def test_random_buffs_roll_per_use_instead_of_at_cache_load(monkeypatch):
    from service.dungeon.components.stat_components import BuffComponent

    attacker = _monster(1, "caster")
    component = BuffComponent()
    component.apply_config({"stat": "random", "value": 0.20}, "fortune")
    assert component.attack_mod == component.defense_mod == component.speed_mod == 0
    choices = iter(["attack", "speed"])
    monkeypatch.setattr("service.dungeon.components.stat_components.random.choice", lambda _: next(choices))
    component.on_turn(attacker, attacker)
    component.on_turn(attacker, attacker)
    assert {value.buff_type for value in attacker.status} == {"attack", "speed"}


def test_heal_block_is_negative_and_prevents_healing():
    from service.dungeon.components.stat_components import DebuffComponent
    from service.dungeon.components.support_components import HealComponent

    caster = _monster(1, "caster")
    target = _monster(2, "target")
    target.now_hp = 500
    debuff = DebuffComponent()
    debuff.apply_config({"stat": "heal_block", "value": 1.0, "duration": 2}, "seal")
    debuff.on_turn(caster, target)
    assert target.status[0].amount == -1.0
    heal = HealComponent()
    heal.apply_config({"percent": 0.25, "target": "self"}, "heal")
    heal.on_turn(target, target)
    assert target.now_hp == 500


def test_self_destruct_charge_is_combat_local_and_explodes_after_owner_turns(monkeypatch):
    from service.dungeon.combat_context import CombatContext
    from service.dungeon.components.special_components import (
        SelfDestructComponent,
        process_delayed_self_destructs,
    )

    monkeypatch.setattr("service.combat.damage_calculator.random.uniform", lambda *_: 0.0)
    attacker = _monster(1, "bomber", hp=1000, ap=100)
    target = _monster(2, "target", hp=1000)
    context = CombatContext([attacker])
    context.runtime_state.bind(attacker)
    component = SelfDestructComponent()
    component.apply_config({"charge_turns": 2, "ap_ratio": 1.0, "target": "all"}, "overload")
    component.skill = SimpleNamespace(id=9135)
    assert "2턴" in component.on_turn(attacker, target)
    assert "1턴 남음" in "\n".join(process_delayed_self_destructs(attacker, context, [target]))
    assert "자폭" in "\n".join(process_delayed_self_destructs(attacker, context, [target]))
    assert attacker.now_hp == 0
    assert target.now_hp < 1000


def test_monster_attack_charge_metadata_extends_telegraph(monkeypatch):
    from service.dungeon.combat_context import CombatContext
    from service.dungeon.monster_ai import decide_monster_action

    monster = _monster(1, "boss")
    monster.action_profile = {
        "revision": "V3-FSM",
        "kind": "boss",
        "actions": [{"skill_id": 99, "weight": 1, "telegraph": "warning", "interruptible": True}],
        "phase_patterns": [{"phase": 1, "skill_ids": [99]}],
    }
    skill = SimpleNamespace(components=[SimpleNamespace(_tag="attack", charge_turns=3)])
    monkeypatch.setattr("models.repos.skill_repo.get_skill_by_id", lambda _: skill)
    context = CombatContext([monster])
    assert decide_monster_action(monster, context).state == "telegraph"
    assert decide_monster_action(monster, context).state == "telegraph"
    assert decide_monster_action(monster, context).state == "telegraph"
    assert decide_monster_action(monster, context).skill is skill


@pytest.mark.asyncio
async def test_reward_passives_modify_the_persisted_values(monkeypatch):
    from service.economy.reward_service import RewardService

    user = User(discord_id=123, username="reward", exp=0, gold=0, level=1)
    monkeypatch.setattr(
        "service.dungeon.skill.get_passive_effect_bonuses",
        lambda *_args, **_kwargs: {"exp_bonus": 0.10, "gold_bonus": 0.20},
    )

    async def fake_save(*_args, **_kwargs):
        return None

    monkeypatch.setattr(User, "save", fake_save)
    result = await RewardService.apply_rewards(user, 100, 100)
    assert (result.exp_gained, result.gold_gained) == (110, 120)
    assert (user.exp, user.gold) == (110, 120)


def test_grade_upgrade_passives_are_applied_only_to_drops(monkeypatch):
    from service.item.grade_service import GradeService

    monkeypatch.setattr("service.item.grade_service.random.choices", lambda *_args, **_kwargs: [3])
    monkeypatch.setattr("service.item.grade_service.random.random", lambda: 0.0)
    monkeypatch.setattr(
        "service.dungeon.skill.get_passive_effect_bonuses",
        lambda *_args, **_kwargs: {"grade_up2_chance": 1.0, "shop_rare": 1.0},
    )
    user = SimpleNamespace(equipped_skill=[])
    assert GradeService.roll_grade("normal", user=user) == 5
    assert GradeService.roll_grade("normal", user=user, shop=True) == 4


@pytest.mark.asyncio
async def test_shop_discount_and_enhancement_luck_use_passive_contract(monkeypatch):
    from service.economy.shop_service import ShopItem, ShopItemType, ShopService
    from service.item.enhancement_service import EnhancementService

    sample = ShopItem(1, "sample", "", 100, ShopItemType.CONSUMABLE, 1)

    async def potions():
        return [sample]

    async def equipment(**_kwargs):
        return []

    async def skills(**_kwargs):
        return []

    async def no_equipment(_user):
        return []

    monkeypatch.setattr(ShopService, "_build_potion_items", potions)
    monkeypatch.setattr(ShopService, "_build_random_equipment_items", equipment)
    monkeypatch.setattr(ShopService, "_build_random_skill_items", skills)
    monkeypatch.setattr(
        "service.dungeon.skill.get_passive_effect_bonuses",
        lambda *_args, **_kwargs: {"shop_discount": 0.10, "enhance_luck": 0.05},
    )
    monkeypatch.setattr(
        "service.item.equipment_component_loader.load_user_equipment_components",
        no_equipment,
    )
    user = SimpleNamespace(equipped_skill=[])
    shown = await ShopService.get_shop_items_for_display(user=user)
    assert shown[0].price == 90
    assert await EnhancementService._get_equipment_success_bonus(user) == pytest.approx(0.05)
