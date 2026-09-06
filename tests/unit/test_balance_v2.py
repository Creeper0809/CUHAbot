import json

import pytest
from unittest.mock import Mock, patch

from config import BALANCE_V2
from models import UserStatEnum
from service.combat.damage_calculator import DamageCalculator
from service.combat.stats import ModifierBundle
from service.player.stat_conversion import convert_abilities_to_combat_stats
from tools.balance_v2 import audit, read_csv, DATA, equipment_final_cp, _phase_entries


class _RuntimeEntity:
    def __init__(self, *, hp=1000, now_hp=None, race="인간형", attribute="무속성"):
        self.hp = hp
        self.now_hp = hp if now_hp is None else now_hp
        self.attack = 100
        self.ap_attack = 100
        self.defense = 0
        self.ap_defense = 0
        self.accuracy = 95
        self.evasion = 5
        self.race = race
        self.attribute = attribute
        self.status = []
        self.equipped_skill = []
        self.modifier_bundle = ModifierBundle()

    def get_name(self):
        return "runtime-test"

    def get_stat(self):
        return {
            UserStatEnum.HP: self.hp,
            UserStatEnum.ATTACK: self.attack,
            UserStatEnum.AP_ATTACK: self.ap_attack,
            UserStatEnum.DEFENSE: self.defense,
            UserStatEnum.AP_DEFENSE: self.ap_defense,
            UserStatEnum.ACCURACY: self.accuracy,
            UserStatEnum.EVASION: self.evasion,
            UserStatEnum.CRITICAL_RATE: 0,
            UserStatEnum.CRITICAL_DAMAGE: 150,
        }

    def take_damage(self, damage):
        actual = min(self.now_hp, damage)
        self.now_hp -= actual
        return actual


def test_base_stats_and_progression_are_canonical():
    level_one = BALANCE_V2.base_stats(1)
    level_hundred = BALANCE_V2.base_stats(100)
    assert (level_one.hp, level_one.attack, level_one.ad_defense, level_one.speed) == (300, 15, 8, 100)
    assert (level_hundred.hp, level_hundred.attack, level_hundred.ad_defense) == (2582, 263, 141)
    assert sum(BALANCE_V2.target_clears_per_level(level) for level in range(1, 100)) == 226
    assert BALANCE_V2.exp_to_next(10) == 2510
    assert [BALANCE_V2.shop_grade_floor(level) for level in (10, 30, 50, 70, 90, 100)] == [2, 3, 4, 5, 6, 6]
    assert BALANCE_V2.skill_shop_price(6) == 12_000


def test_ability_conversion_rounds_only_at_final_aggregation():
    bonus = convert_abilities_to_combat_stats(1, 1, 1, 1, 1)
    assert bonus.hp == 27
    assert bonus.attack == pytest.approx(2.9)
    assert bonus.ap_attack == pytest.approx(2.3)
    assert bonus.ad_defense == pytest.approx(0.75)
    assert bonus.ap_defense == pytest.approx(0.65)
    assert bonus.speed == pytest.approx(0.25)


def test_speed_hit_and_party_caps():
    assert BALANCE_V2.action_rate(-100) == 0.75
    assert BALANCE_V2.action_rate(100) == 1.0
    assert BALANCE_V2.action_rate(300) == 1.5
    assert BALANCE_V2.hit_rate(0, 100) == 0.75
    assert BALANCE_V2.hit_rate(200, 0) == 0.98
    assert BALANCE_V2.party_hp_scale(3) == 2.5
    assert BALANCE_V2.party_attack_scale(3) == 1.24
    assert BALANCE_V2.party_reward_scale(3) == 2.3


def test_hyperbolic_damage_and_penetration_caps(monkeypatch):
    monkeypatch.setattr("service.combat.damage_calculator.random.uniform", lambda *_: 0.0)
    result = DamageCalculator.calculate_physical_damage(
        attack=100, defense=100, armor_penetration=0.0, critical_rate=0.0,
    )
    penetrated = DamageCalculator.calculate_physical_damage(
        attack=100, defense=100, armor_penetration=1.0, critical_rate=0.0,
    )
    assert result.damage == 50
    assert result.defense_reduction == 50
    assert penetrated.damage == 66
    assert penetrated.defense_reduction == 34


def test_modifier_bundle_consumes_every_set_effect_key():
    _, rows = read_csv(DATA / "set_effects.csv")
    for row in rows:
        config = json.loads(row["효과config"])
        ModifierBundle.from_mapping(config, strict=True, percentage_points=True)
        ModifierBundle.assert_runtime_consumers(set(config))


def test_persisted_modifier_values_always_use_percentage_points():
    bundle = ModifierBundle.from_mapping(
        {"heal_pct": 0.3636, "regen_pct": 0.0594},
        percentage_points=True,
    )
    assert bundle.healing_pct == pytest.approx(0.003636)
    assert bundle.regeneration_pct == pytest.approx(0.000594)


def test_damage_pipeline_consumes_mitigation_resistance_dragon_and_lifesteal():
    from service.dungeon.damage_pipeline import process_incoming_damage

    attacker = _RuntimeEntity(now_hp=500)
    attacker.modifier_bundle = ModifierBundle(dragon_bonus=0.20, lifesteal=0.10)
    target = _RuntimeEntity(race="드래곤", attribute="화염")
    target.modifier_bundle = ModifierBundle(damage_taken_pct=-0.20, all_resistance=0.10)

    event = process_incoming_damage(target, 100, attacker=attacker, attribute="화염")
    assert event.actual_damage == 87  # 100 * 1.20 * 0.80, then integer 10% resistance
    assert event.lifesteal_heal == 8
    assert attacker.now_hp == 508


def test_nonstandard_damage_components_use_v2_defense_and_runtime_modifiers(monkeypatch):
    from service.combat.runtime_damage import deal_runtime_damage

    monkeypatch.setattr("service.combat.damage_calculator.random.uniform", lambda *_: 0.0)
    attacker = _RuntimeEntity()
    target = _RuntimeEntity()
    target.defense = 100

    baseline = deal_runtime_damage(
        attacker, target, 100, is_physical=True, attribute="무속성"
    )
    assert baseline.calculation.damage == 50
    assert baseline.event.actual_damage == 50

    target.now_hp = target.hp
    attacker.modifier_bundle = ModifierBundle(
        physical_damage_pct=0.20,
        armor_penetration=0.50,
    )
    boosted = deal_runtime_damage(
        attacker, target, 100, is_physical=True, attribute="무속성"
    )
    assert boosted.calculation.damage == 80
    assert boosted.event.actual_damage == 80


def test_heal_regen_status_and_action_chance_consume_runtime_modifiers(monkeypatch):
    from service.dungeon.components.special_components import StatusComponent
    from service.dungeon.components.support_components import HealComponent
    from service.dungeon.combat_executor import _apply_synergy_hp_regen, _roll_modifier_chance

    attacker = _RuntimeEntity(now_hp=500)
    attacker.modifier_bundle = ModifierBundle(
        healing_pct=0.50,
        regeneration_pct=0.02,
        burn_chance=0.20,
        first_strike=0.25,
        extra_action=0.10,
    )
    del attacker.equipped_skill
    target = _RuntimeEntity(now_hp=500)

    heal = HealComponent()
    heal.apply_config({"percent": 0.10}, "runtime heal")
    heal.on_turn(attacker, target)
    assert attacker.now_hp == 650

    monkeypatch.setattr(
        "service.dungeon.combat_executor.get_hp_regen_per_turn_pct", lambda _: 0.0
    )
    assert "+20" in _apply_synergy_hp_regen(attacker)

    status = StatusComponent()
    status.apply_config({"type": "burn", "chance": 0.0, "duration": 2}, "runtime burn")
    monkeypatch.setattr("service.dungeon.components.special_components.random.random", lambda: 0.10)
    assert status.on_turn(attacker, target)
    assert any(getattr(value, "effect_type", "") == "burn" for value in target.status)

    assert _roll_modifier_chance(attacker, "first_strike", roll=lambda: 0.24)
    assert not _roll_modifier_chance(attacker, "first_strike", roll=lambda: 0.26)
    assert _roll_modifier_chance(attacker, "extra_action", cap=0.50, roll=lambda: 0.09)


def test_generated_balance_data_passes_full_audit():
    result = audit()
    assert result["counts"] == {"equipment": 486, "skills": 647, "monsters": 128, "sets": 36}
    assert result["equipment_outside_10_percent"] == 0
    assert result["final_equipment_cp_violations"] == []
    assert result["skill_action_value_outliers"] == []
    assert result["skills_evaluated"] == 647
    assert result["active_action_values_evaluated"] == 553
    assert result["passive_contracts_evaluated"] == 94
    assert result["passive_contract_errors"] == []
    assert result["missing_runtime_component_tags"] == []
    assert result["equipment_components_evaluated"] > 0
    assert result["missing_equipment_component_tags"] == []
    assert result["missing_equipment_runtime_consumers"] == []
    assert result["zero_attack_monsters"] == []
    assert result["unknown_set_effects"] == []
    assert result["phase_monsters"] == 29
    assert result["phase_transition_errors"] == []
    assert result["skill_ecosystem"]["skills_designed"] == 647
    assert result["skill_ecosystem"]["player_skills_designed"] == 326
    assert result["skill_ecosystem"]["missing_design"] == []
    assert result["skill_ecosystem"]["orphan_payoffs"] == []
    assert result["passed"]


def test_every_equipment_component_loads_and_has_an_executable_consumer():
    from service.item.equipment_component_loader import (
        EQUIPMENT_RUNTIME_CONSUMERS,
        load_equipment_components,
    )

    _, equipment = read_csv(DATA / "items_equipment.csv")
    loaded = []
    for row in equipment:
        loaded.extend(load_equipment_components(json.loads(row.get("config") or "{}")))
    assert len(loaded) == 399
    assert all(component._tag in EQUIPMENT_RUNTIME_CONSUMERS for component in loaded)


def test_legacy_equipment_aliases_reach_reflection_immunity_and_debuff_runtime():
    from service.dungeon.damage_pipeline import (
        get_debuff_reduction,
        get_status_immunities,
        process_incoming_damage,
    )
    from service.item.equipment_component_loader import load_equipment_components

    defender = _RuntimeEntity()
    defender._equipment_components_cache = load_equipment_components({"components": [
        {"tag": "damage_reflection", "reflection_percent": 0.25},
        {"tag": "status_immunity", "immune_statuses": ["기절", "치명타"]},
        {"tag": "debuff_reduction", "reduction_percent": 0.4},
    ]})
    attacker = _RuntimeEntity()
    event = process_incoming_damage(defender, 100, attacker=attacker)
    assert event.reflected_damage == 25
    assert get_status_immunities(defender)["types"] == {"stun", "critical"}
    assert get_debuff_reduction(defender) == pytest.approx(0.4)


def test_equipment_damage_delay_and_prediction_change_hp_not_only_logs():
    from service.dungeon.damage_pipeline import process_incoming_damage
    from service.item.equipment_component_loader import load_equipment_components

    defender = _RuntimeEntity()
    defender._equipment_components_cache = load_equipment_components({"components": [
        {"tag": "action_prediction", "prediction_chance": 1.0, "damage_reduction": 0.25},
        {"tag": "damage_delay", "delay_percent": 0.4},
    ]})
    prediction, delay = defender._equipment_components_cache
    prediction._predicted_this_turn = True
    event = process_incoming_damage(defender, 100)
    # Prediction: 100 -> 75. Delay: 30 is scheduled, so 45 is immediate.
    assert event.actual_damage == 45
    assert delay._delayed_damage == 30
    assert defender.now_hp == 955
    delay.on_turn_start(defender, None)
    assert defender.now_hp == 925


def test_unknown_equipment_effect_fails_closed():
    from service.item.equipment_component_loader import (
        UnknownEquipmentComponentError,
        load_equipment_components,
    )

    with pytest.raises(UnknownEquipmentComponentError):
        load_equipment_components({"components": [{"tag": "silent_power_creep"}]})


def test_phase_parser_does_not_treat_effect_percentages_as_hp_thresholds():
    phases = _phase_entries(
        "페이즈 전환 (HP 50%): 분노 모드 - 공격력 +30%, 공격속도 +50%"
    )
    assert [phase["hp_threshold"] for phase in phases] == [0.5]
    assert phases[0]["attack_pct"] == pytest.approx(0.30)
    assert phases[0]["speed_pct"] == pytest.approx(0.50)


def test_monster_phase_copy_transitions_shield_and_summon_immunity():
    from models.monster import Monster
    from service.dungeon.combat_context import CombatContext
    from service.dungeon.damage_pipeline import process_incoming_damage
    from service.dungeon.monster_phase_service import process_monster_phase_transitions
    from service.dungeon.status.stat_buffs import ShieldBuff

    source_config = {"phases": [{
        "hp_threshold": 0.5,
        "attack_pct": 0.2,
        "speed_pct": 0.1,
        "defense_pct": 0.0,
        "shield_pct": 0.1,
        "heal_pct": 0.0,
        "summon_count": 2,
        "invulnerable_until_summons": True,
    }]}
    source = Monster(
        id=9999, name="phase-source", description="", type="BossMob",
        hp=1000, attack=100, ap_attack=0, defense=10, ap_defense=10,
        speed=100, skill_ids=[], drop_skill_ids=[], phase_config=source_config,
    )
    monster = source.copy()
    monster.now_hp = 500
    context = CombatContext.from_single(monster)
    context.initialize_gauges(_RuntimeEntity())

    logs = process_monster_phase_transitions(monster, context)
    echoes = [value for value in context.monsters if getattr(value, "is_phase_summon", False)]
    assert logs and len(echoes) == 2
    assert monster.attack == 120 and monster.speed == 110
    assert any(isinstance(value, ShieldBuff) for value in monster.status)
    assert source.phase_config == source_config
    assert source.attack == 100
    assert process_incoming_damage(monster, 100).was_immune

    for echo in echoes:
        echo.now_hp = 0
    release_logs = process_monster_phase_transitions(monster, context)
    assert release_logs
    assert not getattr(monster, "_phase_invulnerable", False)


def test_rolled_special_effects_never_exceed_grade_cp_budget():
    from service.item.grade_service import GradeService

    _, equipment = read_csv(DATA / "items_equipment.csv")
    probe = equipment[0]
    previous = 0.0
    for grade_id, grade in enumerate(("D", "C", "B", "A", "S", "SS", "SSS", "MYTHIC"), 1):
        for _ in range(250):
            effects = GradeService.roll_special_effects(grade_id)
            assert GradeService.special_effect_budget_ratio(effects) <= BALANCE_V2.effect_budget_caps[grade] + 1e-9
            final_cp = equipment_final_cp(probe, grade, 15, effects)
            ceiling = equipment_final_cp(probe, grade, 15) * (1 + BALANCE_V2.effect_budget_caps[grade])
            assert final_cp <= ceiling + 1e-6
        unmodified = equipment_final_cp(probe, grade, 15)
        assert unmodified > previous
        previous = unmodified


def test_restore_tool_is_dry_run_and_validates_archive_contents(tmp_path):
    from scripts.restore_balance_v2_backup import inspect_backup, restore

    backup = tmp_path / "season.dump"
    backup.write_bytes(b"not-empty")
    listing = "; archive\n1; TABLE DATA public users postgres\n2; TABLE DATA public user_inventory postgres\n"
    with patch("scripts.restore_balance_v2_backup.subprocess.run", return_value=Mock(stdout=listing)) as run:
        result = inspect_backup(backup)
        assert result["entries"] == 2
        run.assert_called_once()
    with pytest.raises(ValueError, match="--confirm"):
        restore(backup, "balance-v2", "wrong")
