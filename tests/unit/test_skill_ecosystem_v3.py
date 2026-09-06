import json
from pathlib import Path
from types import SimpleNamespace

from models import UserStatEnum
from models.repos import static_cache
from service.dungeon.combat_runtime_state import CombatRuntimeState
from service.dungeon.components.ecosystem_v3_components import (
    CombatResourceComponent,
    ResourcePayoffComponent,
    StatusTransformComponent,
)
from service.dungeon.monster_ai import decide_monster_action, interrupt_pending_monster_action
from service.dungeon.status import apply_status_effect, get_status_stacks
from service.skill.design_v3 import (
    build_authored_config,
    deck_link_summary,
    first_link_probability,
    load_design_contracts,
)
from tools.skill_ecosystem_v3 import (
    audit,
    compile_rows,
    load_assignment_manifest,
    load_profiles,
)


ROOT = Path(__file__).resolve().parents[2]


class FakeEntity:
    def __init__(self, name="테스터", hp=1000, ad=100, ap=100):
        self.id = id(self)
        self.name = name
        self.hp = hp
        self.now_hp = hp
        self.attack = ad
        self.ap_attack = ap
        self.defense = 0
        self.ap_defense = 0
        self.attribute = "무속성"
        self.status = []

    def get_name(self):
        return self.name

    def get_stat(self):
        return {
            UserStatEnum.HP: self.hp,
            UserStatEnum.ATTACK: self.attack,
            UserStatEnum.AP_ATTACK: self.ap_attack,
            UserStatEnum.DEFENSE: self.defense,
            UserStatEnum.AP_DEFENSE: self.ap_defense,
            UserStatEnum.CRITICAL_RATE: 0,
            UserStatEnum.CRITICAL_DAMAGE: 150,
        }

    def take_damage(self, damage):
        actual = min(self.now_hp, max(0, int(damage)))
        self.now_hp -= actual
        return actual


def _component(component_type, config):
    value = component_type()
    value.apply_config(config, "V3 테스트")
    value.skill_attribute = "무속성"
    value.skill = SimpleNamespace(id=999999)
    return value


def test_v3_authored_source_covers_every_skill_and_runtime_row():
    result = audit()
    contracts = load_design_contracts()
    skill_rows, _ = compile_rows(write=False)

    assert result["passed"], result["errors"]
    assert len(contracts) == len(skill_rows) == 647
    assert sum(value["scope"] == "player" for value in contracts.values()) == 326
    assert sum(value["scope"] == "monster" for value in contracts.values()) == 321
    assert all(value["manual_revision"] == "V3-manual" for value in contracts.values())
    assert all("\ufffd" not in json.dumps(value, ensure_ascii=False) for value in contracts.values())
    assert all(build_authored_config(int(row["ID"])) == json.loads(row["config"]) for row in skill_rows)


def test_v3_monster_profiles_cover_128_behavior_sets():
    profiles = load_profiles()
    counts = {kind: sum(value["kind"] == kind for value in profiles.values()) for kind in ("common", "elite", "boss")}

    assert counts == {"common": 72, "elite": 23, "boss": 33}
    assert all(len(value["actions"]) >= 2 for value in profiles.values() if value["kind"] == "common")
    assert all(any(action.get("telegraph") for action in value["actions"]) for value in profiles.values() if value["kind"] in {"elite", "boss"})
    assert all(any(action.get("recover_actions", 0) for action in value["actions"]) for value in profiles.values() if value["kind"] in {"elite", "boss"})
    assert all(len({tuple(pattern["skill_ids"]) for pattern in value["phase_patterns"]}) >= 2 for value in profiles.values() if value["kind"] == "boss")


def test_every_monster_skill_is_connected_and_every_active_is_phase_reachable():
    contracts = load_design_contracts()
    _, monster_rows = compile_rows(write=False)
    profiles = load_profiles()
    monster_ids = {
        skill_id for skill_id, contract in contracts.items()
        if contract["scope"] == "monster"
    }
    active_ids = {
        skill_id for skill_id in monster_ids
        if contracts[skill_id]["record"]["type"] == "active"
    }
    deck_refs = {
        int(skill_id)
        for row in monster_rows
        for skill_id in json.loads(row["skill_ids"])
        if int(skill_id)
    }
    action_refs = {
        int(action["skill_id"])
        for profile in profiles.values()
        for action in profile["actions"]
        if int(action.get("skill_id", 0) or 0)
    }
    reachable = {
        int(action["skill_id"])
        for profile in profiles.values()
        for action in profile["actions"]
        if int(action.get("skill_id", 0) or 0)
        and any(
            int(action["skill_id"]) in {int(value) for value in pattern["skill_ids"]}
            for pattern in profile["phase_patterns"]
        )
    }

    assert monster_ids <= deck_refs
    assert active_ids <= action_refs
    assert active_ids <= reachable
    assert all(len(json.loads(row["skill_ids"])) == 10 for row in monster_rows)
    assert all(
        any(
            int(action.get("skill_id", 0) or 0) > 0
            and any(int(action["skill_id"]) in pattern["skill_ids"] for pattern in profile["phase_patterns"])
            for action in profile["actions"]
        )
        for profile in profiles.values()
        if profile["kind"] == "common"
    )


def test_connectivity_manifest_keeps_all_65_previously_orphaned_skills():
    manifest = load_assignment_manifest()
    assigned = {int(value["skill_id"]) for value in manifest["assignments"]}
    assert len(manifest["assignments"]) == len(assigned) == 65
    assert assigned == set(range(9001, 9049)) | {
        9057, 9069, 9109, 9152, 9153, 9181, 9182, 9183,
        9190, 9191, 9195, 9196, 9197, 9198, 9199, 9208, 9219,
    }


def test_every_new_assignment_is_actually_selected_by_its_unlocked_fsm(monkeypatch):
    from models.repos import skill_repo

    fake_skills = {
        int(value["skill_id"]): SimpleNamespace(id=int(value["skill_id"]), components=[])
        for value in load_assignment_manifest()["assignments"]
    }
    monkeypatch.setattr(skill_repo, "get_skill_by_id", lambda skill_id: fake_skills.get(int(skill_id)))
    profiles = load_profiles()
    for assignment in load_assignment_manifest()["assignments"]:
        skill_id = int(assignment["skill_id"])
        phase = int(assignment["unlock_phase"])
        monster = _monster(profiles[int(assignment["monster_id"])], phase_index=phase - 1)
        context = SimpleNamespace(runtime_state=CombatRuntimeState(seed=skill_id))
        selected = False
        for _ in range(300):
            decision = decide_monster_action(monster, context)
            if getattr(decision.skill, "id", None) == skill_id:
                selected = True
                break
        assert selected, f"skill {skill_id} was not selected in phase {phase}"


def test_connected_finisher_contracts_have_real_windows_and_truthful_text():
    from service.skill.design_v3 import describe_skill_config

    ultrasonic = build_authored_config(9006)
    genesis = build_authored_config(9199)
    judgment = build_authored_config(9219)
    assert ultrasonic["components"][0]["attack"] == -0.15
    assert genesis["components"][0]["hp_threshold"] == 0.15
    assert genesis["components"][0]["charge_turns"] == 3
    assert genesis["components"][0]["once_per_battle"] is True
    assert judgment["components"][0]["hp_threshold"] == 0.2
    assert judgment["components"][0]["value"] == 0.5
    assert judgment["components"][0]["once_per_battle"] is True
    assert "사용자 HP 15% 이하" in describe_skill_config(genesis)
    assert "3회 행동 충전" in describe_skill_config(genesis)
    assert "전투당 1회" in describe_skill_config(judgment)


def test_deck_link_probability_is_monotonic_and_reports_missing_sides():
    assert first_link_probability(1, 3) < first_link_probability(2, 3) < first_link_probability(3, 3)
    configs = {
        1: {"design": {"setup_tags": ["burn"], "payoff_tags": [], "role": "primer"}},
        2: {"design": {"setup_tags": [], "payoff_tags": ["burn"], "role": "payoff"}},
    }
    one = deck_link_summary([1, 2, 2], configs)[0]
    two = deck_link_summary([1, 1, 2], configs)[0]
    assert one["first_link_probability"] < two["first_link_probability"]
    assert (one["setup_copies"], one["payoff_copies"]) == (1, 2)


def test_named_resource_generator_and_payoff_share_combat_state():
    attacker = FakeEntity(ad=120)
    target = FakeEntity(name="표적", hp=2000)
    runtime = CombatRuntimeState(seed=17)
    runtime.bind(attacker)
    generator = _component(CombatResourceComponent, {"resource": "기세", "amount": 1, "maximum": 3})
    payoff = _component(ResourcePayoffComponent, {"resource": "기세", "cost": 3, "ad_ratio": 1.0})

    before = target.now_hp
    assert payoff.on_turn(attacker, target) == ""
    assert target.now_hp == before
    for _ in range(5):
        generator.on_turn(attacker, target)
    assert runtime.for_entity(attacker).resources["기세"] == 3
    log = payoff.on_turn(attacker, target)
    assert "기세 3 소비" in log
    assert target.now_hp < before
    assert runtime.for_entity(attacker).resources["기세"] == 0


def test_status_transform_is_config_driven_and_has_clean_failure():
    attacker = FakeEntity()
    target = FakeEntity(name="표적")
    transform = _component(StatusTransformComponent, {
        "from_status": "erode", "to_status": "submerge", "minimum": 2, "duration": 3,
    })
    assert transform.on_turn(attacker, target) == ""
    apply_status_effect(target, "erode", stacks=2, duration=2)
    log = transform.on_turn(attacker, target)
    assert "침식 x2" in log
    assert "침수" in log
    assert get_status_stacks(target, "erode") == 0
    assert get_status_stacks(target, "submerge") == 1


def _monster(profile, phase_index=0):
    return SimpleNamespace(
        id=71001,
        name="FSM 표적",
        hp=1000,
        now_hp=500,
        phase_index=phase_index,
        action_profile=profile,
        get_name=lambda: "FSM 표적",
        next_skill=lambda: None,
    )


def test_common_fsm_cycles_core_and_support_actions():
    profile = {
        "revision": "V3-FSM", "kind": "common", "interrupt_policy": "delay",
        "actions": [
            {"skill_id": 0, "weight": 1},
            {"skill_id": 0, "action_kind": "support", "weight": 1, "recover_hp_percent": 0.03},
        ],
        "phase_patterns": [{"phase": 1, "skill_ids": [0]}],
    }
    monster = _monster(profile)
    context = SimpleNamespace(runtime_state=CombatRuntimeState(seed=3))
    first = decide_monster_action(monster, context)
    second = decide_monster_action(monster, context)
    assert not first.skip_basic
    assert second.skip_basic and second.state == "execute"
    assert monster.now_hp == 530


def test_boss_fsm_telegraphs_executes_recovers_and_can_be_interrupted():
    skill = object()
    static_cache.skill_cache_by_id[999001] = skill
    profile = {
        "revision": "V3-FSM", "kind": "boss", "interrupt_policy": "cancel",
        "actions": [{
            "skill_id": 999001, "weight": 1, "telegraph": "⚠️ 큰 공격 준비",
            "interruptible": True, "cooldown_actions": 2, "recover_actions": 1,
        }],
        "phase_patterns": [{"phase": 1, "skill_ids": [0]}, {"phase": 2, "skill_ids": [999001]}],
    }
    try:
        context = SimpleNamespace(runtime_state=CombatRuntimeState(seed=5))
        monster = _monster(profile, phase_index=1)
        tell = decide_monster_action(monster, context)
        execute = decide_monster_action(monster, context)
        recover = decide_monster_action(monster, context)
        assert tell.skip_basic and tell.state == "telegraph"
        assert execute.skill is skill and execute.state == "execute"
        assert recover.skip_basic and recover.state == "recover"

        interrupted = _monster(profile, phase_index=1)
        context2 = SimpleNamespace(runtime_state=CombatRuntimeState(seed=5))
        decide_monster_action(interrupted, context2)
        assert "취소" in interrupt_pending_monster_action(interrupted, context2)
        assert decide_monster_action(interrupted, context2).state == "telegraph"
    finally:
        static_cache.skill_cache_by_id.pop(999001, None)
