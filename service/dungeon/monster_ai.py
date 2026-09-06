"""Interruptible finite-state decision machine for V3 monster action sets."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class MonsterDecision:
    skill: Any | None = None
    logs: list[str] = field(default_factory=list)
    skip_basic: bool = False
    state: str = "idle"


def _runtime_ai(monster: Any, context: Any) -> dict[str, Any]:
    runtime = getattr(context, "runtime_state", None)
    if runtime is not None:
        return runtime.for_entity(monster).ai
    return monster.__dict__.setdefault("_v3_ai_state", {})


def _active_actions(profile: dict[str, Any], phase: int) -> list[dict[str, Any]]:
    allowed: set[int] | None = None
    for value in profile.get("phase_patterns", []):
        if int(value.get("phase", 0)) == phase:
            allowed = {int(skill_id) for skill_id in value.get("skill_ids", [])}
            break
    actions = list(profile.get("actions", []))
    if allowed is not None:
        actions = [action for action in actions if int(action.get("skill_id", 0)) in allowed]
    return actions or list(profile.get("actions", []))


def _weighted_cycle(actions: list[dict[str, Any]]) -> list[int]:
    cycle: list[int] = []
    for index, action in enumerate(actions):
        cycle.extend([index] * max(1, int(action.get("weight", 1) or 1)))
    return cycle or [0]


def _attack_charge_actions(action: dict[str, Any]) -> int:
    """Read charge metadata only from the action's attack component."""
    from models.repos.skill_repo import get_skill_by_id

    skill_id = int(action.get("skill_id", 0) or 0)
    skill = get_skill_by_id(skill_id) if skill_id else None
    if skill is None:
        return 0
    return max(
        (
            int(getattr(component, "charge_turns", 0) or 0)
            for component in getattr(skill, "components", [])
            if getattr(component, "_tag", "") == "attack"
        ),
        default=0,
    )


def _resolve_action(monster: Any, context: Any, action: dict[str, Any], logs: list[str], phase: int) -> MonsterDecision:
    """Resolve a configured action without branching on a concrete skill ID."""
    from models.repos.skill_repo import get_skill_by_id

    if action.get("action_kind") == "support":
        percent = max(0.0, float(action.get("recover_hp_percent", 0.0) or 0.0))
        maximum_hp = max(1, int(getattr(monster, "hp", 1) or 1))
        old_hp = int(getattr(monster, "now_hp", maximum_hp))
        monster.now_hp = min(maximum_hp, old_hp + max(1, int(maximum_hp * percent)))
        healed = monster.now_hp - old_hp
        message = str(action.get("support_log") or f"🛡️ **{monster.get_name()}**이(가) 자세를 가다듬습니다.")
        logs.append(message)
        runtime = getattr(context, "runtime_state", None)
        if runtime is not None:
            runtime.record("monster_support", monster_id=monster.id, phase=phase, healing=healed)
        return MonsterDecision(logs=logs, skip_basic=True, state="execute")

    skill_id = int(action.get("skill_id", 0) or 0)
    return MonsterDecision(
        skill=get_skill_by_id(skill_id) if skill_id else None,
        logs=logs,
        state="execute",
    )


def decide_monster_action(monster: Any, context: Any) -> MonsterDecision:
    from models.repos.skill_repo import get_skill_by_id

    profile = getattr(monster, "action_profile", None) or {}
    if profile.get("revision") != "V3-FSM":
        return MonsterDecision(skill=monster.next_skill(), state="legacy")

    state = _runtime_ai(monster, context)
    phase = int(getattr(monster, "phase_index", 0) or 0) + 1
    logs: list[str] = []
    if state.get("phase") != phase:
        state.clear()
        state.update({"phase": phase, "mode": "phase_transition", "cursor": 0, "cooldowns": {}})
        logs.append(f"🔄 **{monster.get_name()}** 행동 패턴이 페이즈 {phase}로 전환됩니다.")

    pending = state.get("pending")
    if pending is not None and state.get("mode") == "telegraph":
        action = pending
        remaining = max(1, int(state.get("telegraph_remaining", 1) or 1))
        if remaining > 1:
            state["telegraph_remaining"] = remaining - 1
            logs.append(
                f"⏳ **{monster.get_name()}**의 큰 기술 발동까지 {remaining - 1}회 행동이 남았습니다."
            )
            return MonsterDecision(logs=logs, skip_basic=True, state="telegraph")
        state["pending"] = None
        state.pop("telegraph_remaining", None)
        recover = max(0, int(action.get("recover_actions", 0) or 0))
        state["recover_remaining"] = recover
        state["mode"] = "recover" if recover else "idle"
        cooldown = max(0, int(action.get("cooldown_actions", 0) or 0))
        if cooldown:
            state.setdefault("cooldowns", {})[str(action.get("skill_id", 0))] = cooldown
        skill_id = int(action.get("skill_id", 0) or 0)
        runtime = getattr(context, "runtime_state", None)
        if runtime is not None:
            runtime.record("monster_execute", monster_id=monster.id, skill_id=skill_id, phase=phase)
        return _resolve_action(monster, context, action, logs, phase)

    recover_remaining = int(state.get("recover_remaining", 0) or 0)
    if recover_remaining > 0:
        state["recover_remaining"] = recover_remaining - 1
        if state["recover_remaining"] <= 0:
            state["mode"] = "idle"
        logs.append(f"💨 **{monster.get_name()}**은(는) 큰 기술 뒤의 빈틈을 수습합니다.")
        return MonsterDecision(logs=logs, skip_basic=True, state="recover")

    actions = _active_actions(profile, phase)
    cooldowns = state.setdefault("cooldowns", {})
    for key in list(cooldowns):
        cooldowns[key] = max(0, int(cooldowns[key]) - 1)
        if cooldowns[key] == 0:
            cooldowns.pop(key, None)
    available = [action for action in actions if str(action.get("skill_id", 0)) not in cooldowns]
    if not available:
        available = actions
    cycle = _weighted_cycle(available)
    cursor = int(state.get("cursor", 0) or 0)
    action = available[cycle[cursor % len(cycle)]]
    state["cursor"] = cursor + 1

    charge_actions = _attack_charge_actions(action)
    telegraph = action.get("telegraph")
    if charge_actions and not telegraph:
        telegraph = f"⚠️ {monster.get_name()}이(가) 큰 기술을 준비합니다."
    if telegraph:
        state["pending"] = dict(action)
        state["mode"] = "telegraph"
        state["telegraph_remaining"] = max(1, charge_actions)
        logs.append(str(telegraph))
        runtime = getattr(context, "runtime_state", None)
        if runtime is not None:
            runtime.record("monster_telegraph", monster_id=monster.id, skill_id=int(action.get("skill_id", 0) or 0), phase=phase)
        return MonsterDecision(logs=logs, skip_basic=True, state="telegraph")

    state["mode"] = "idle"
    return _resolve_action(monster, context, action, logs, phase)


def interrupt_pending_monster_action(monster: Any, context: Any) -> str:
    profile = getattr(monster, "action_profile", None) or {}
    if profile.get("revision") != "V3-FSM":
        return ""
    state = _runtime_ai(monster, context)
    if state.get("mode") != "telegraph" or not state.get("pending"):
        return ""
    pending = state["pending"]
    if not pending.get("interruptible"):
        return ""
    skill_id = int(pending.get("skill_id", 0) or 0)
    if profile.get("interrupt_policy") == "cancel":
        state["pending"] = None
        state["mode"] = "idle"
        message = f"✅ **{monster.get_name()}**의 준비 행동이 취소되었습니다."
        event_type = "monster_telegraph_cancelled"
    else:
        message = f"⏸️ **{monster.get_name()}**의 준비 행동이 지연되었습니다."
        event_type = "monster_telegraph_delayed"
    runtime = getattr(context, "runtime_state", None)
    if runtime is not None:
        runtime.record(event_type, monster_id=monster.id, skill_id=skill_id)
    return message
