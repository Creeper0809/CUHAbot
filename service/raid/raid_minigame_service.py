from __future__ import annotations

import random
from math import ceil

from models.repos.static_cache import raid_minigames_by_raid_id, raid_minigame_rule_by_minigame_id
from service.raid.raid_combat_engine import resolve_pending_raid_minigame

SEQUENCE_TYPES = {
    "order_select",
    "safe_tile_select",
    "route_match",
    "rotation_match",
    "price_select",
}
TIMING_TYPES = {
    "timing_sync",
    "timing_jump",
    "sequential_timing",
}
SIMULTANEOUS_TYPES = {
    "simultaneous_choice",
}
DEFAULT_FAIL_FAST_TYPES = {"safe_tile_select"}


def get_pending_raid_minigame(session):
    if not session or not session.raid_id:
        return None
    minigame_id = int(getattr(session, "raid_pending_minigame_id", 0) or 0)
    if minigame_id <= 0:
        return None
    for mg in raid_minigames_by_raid_id.get(session.raid_id, []):
        if int(mg.minigame_id) == minigame_id:
            return mg
    return None


def _get_rule(minigame_id: int) -> dict:
    return dict(raid_minigame_rule_by_minigame_id.get(int(minigame_id), {}) or {})


def _alive_raid_members(session) -> list:
    members = []
    leader = getattr(session, "user", None)
    if leader and getattr(leader, "now_hp", 0) > 0:
        members.append(leader)
    for p in (getattr(session, "participants", {}) or {}).values():
        if getattr(p, "now_hp", 0) > 0:
            members.append(p)
    return members


def _build_seed(session, minigame_id: int, round_number: int) -> int:
    return int(session.raid_id or 0) * 1009 + int(minigame_id) * 131 + int(round_number)


def _choices_for_type(minigame_type: str) -> list[tuple[str, str]]:
    if minigame_type in TIMING_TYPES:
        return [("E", "이른 입력"), ("P", "정확 입력"), ("L", "늦은 입력")]
    if minigame_type in SIMULTANEOUS_TYPES:
        return [("S", "희생"), ("B", "균형"), ("R", "저항")]
    return [("1", "A 패턴"), ("2", "B 패턴"), ("3", "C 패턴"), ("4", "D 패턴")]


def _sim_tokens() -> list[str]:
    return ["ALL_DIFFERENT", "DEFENSIVE", "AGGRESSIVE"]


def _rule_sim_tokens(rule: dict) -> list[str]:
    pool = (rule.get("sim_token_pool") or "").strip()
    if not pool:
        return _sim_tokens()
    tokens = [t.strip() for t in pool.split("|") if t.strip()]
    return tokens or _sim_tokens()


def _sim_prompt(token: str, alive_count: int) -> str:
    if token == "ALL_DIFFERENT":
        return f"단계 목표: {alive_count}명 선택이 모두 달라야 함"
    if token == "DEFENSIVE":
        return "단계 목표: 균형(B) 다수 + 저항(R) 최소 1"
    return "단계 목표: 희생(S) 최소 1 + 균형(B) 최소 1"


def _generate_expected(session, minigame, round_number: int) -> tuple[list[str], str]:
    rng = random.Random(_build_seed(session, int(minigame.minigame_id), round_number))
    count = max(1, int(getattr(minigame, "input_count", 1) or 1))
    rule = _get_rule(int(minigame.minigame_id))

    if minigame.minigame_type in TIMING_TYPES:
        # 세부화: 전부 정확(P)이 아니라 랜덤 타이밍 시퀀스
        options = ["E", "P", "L"]
        expected = [rng.choice(options) for _ in range(count)]
        allowed_miss = max(0, int(rule.get("timing_allowed_miss", 1)))
        prompt = f"타이밍 시퀀스 {count}회 입력 (오차 {allowed_miss}회 허용)"
        return expected, prompt

    if minigame.minigame_type in SIMULTANEOUS_TYPES:
        tokens = _rule_sim_tokens(rule)
        expected = [rng.choice(tokens) for _ in range(count)]
        alive_min = max(1, int(rule.get("sim_required_alive_min", 1)))
        alive_count = max(alive_min, len(_alive_raid_members(session)))
        prompt = f"동시 선택 {count}단계 진행 (현재 인원 {alive_count}명)"
        return expected, prompt

    options = [v for v, _ in _choices_for_type(minigame.minigame_type)]
    expected = [rng.choice(options) for _ in range(count)]
    prompt = f"패턴 {count}개를 순서대로 입력"
    return expected, prompt


def _ensure_minigame_state(session, round_number: int):
    minigame = get_pending_raid_minigame(session)
    if not minigame:
        return None

    expected = list(getattr(session, "raid_minigame_expected", []) or [])
    if not expected:
        expected, prompt = _generate_expected(session, minigame, round_number)
        session.raid_minigame_expected = expected
        session.raid_minigame_prompt = prompt
        session.raid_minigame_inputs = []
        session.raid_minigame_stage_inputs = {}
        session.raid_minigame_stage_index = 0

    return minigame


def get_minigame_choice_payloads(session, round_number: int) -> tuple[list[tuple[str, str]], str]:
    """
    returns: ([(value,label), ...], progress_text)
    """
    minigame = _ensure_minigame_state(session, round_number)
    if not minigame:
        return [], ""

    options = _choices_for_type(minigame.minigame_type)
    expected = list(getattr(session, "raid_minigame_expected", []) or [])

    if minigame.minigame_type in SIMULTANEOUS_TYPES:
        stage = int(getattr(session, "raid_minigame_stage_index", 0) or 0)
        per_stage = dict(getattr(session, "raid_minigame_stage_inputs", {}) or {})
        progress_text = f"단계 {stage + 1}/{len(expected)} | 제출 {len(per_stage)}"
        return options, progress_text

    inputs = list(getattr(session, "raid_minigame_inputs", []) or [])
    progress_text = f"{len(inputs)}/{len(expected)}"
    return options, progress_text


def _eval_sim_stage(stage_token: str, choices: list[str], required_count: int) -> bool:
    picks = choices[:required_count]
    if not picks:
        return False

    if stage_token == "ALL_DIFFERENT":
        return len(set(picks)) == len(picks)

    b_count = sum(1 for c in picks if c == "B")
    r_count = sum(1 for c in picks if c == "R")
    s_count = sum(1 for c in picks if c == "S")

    if stage_token == "DEFENSIVE":
        return b_count >= max(1, ceil(required_count / 2)) and r_count >= 1
    if stage_token == "AGGRESSIVE":
        return s_count >= 1 and b_count >= 1
    return False


def _resolve_final(session, actor, current_round: int, minigame, success: bool, detail: str) -> list[str]:
    if not session.combat_context or not session.combat_context.monsters:
        return ["⚠️ 전투 대상 정보가 없습니다."]

    boss = session.combat_context.monsters[0]
    leader = session.user
    return resolve_pending_raid_minigame(
        session=session,
        leader=leader,
        boss=boss,
        success=success,
        current_round=current_round,
        actor_name=getattr(actor, "username", None) or getattr(actor, "display_name", None),
        reason=detail,
    )


def _resolve_sequence_or_timing(session, actor, selected_value: str, current_round: int, minigame) -> list[str]:
    expected = list(getattr(session, "raid_minigame_expected", []) or [])
    inputs = list(getattr(session, "raid_minigame_inputs", []) or [])
    rule = _get_rule(int(minigame.minigame_id))

    if len(inputs) >= len(expected):
        return ["⚠️ 이미 필요한 입력 수를 채웠습니다."]

    inputs.append(selected_value)
    session.raid_minigame_inputs = inputs
    idx = len(inputs) - 1

    logs: list[str] = [f"🎮 미니게임 입력: {len(inputs)}/{len(expected)}"]

    # 즉시 실패 타입: 틀린 순간 종료
    fail_fast = bool(rule.get("fail_fast", minigame.minigame_type in DEFAULT_FAIL_FAST_TYPES))
    if fail_fast and selected_value != expected[idx]:
        logs.extend(_resolve_final(
            session,
            actor,
            current_round,
            minigame,
            False,
            detail=f"즉시 실패 입력={inputs}, 정답={expected}",
        ))
        return logs

    if len(inputs) < len(expected):
        return logs

    if minigame.minigame_type in TIMING_TYPES:
        matched = sum(1 for i, v in enumerate(inputs[:len(expected)]) if v == expected[i])
        allowed_miss = max(0, int(rule.get("timing_allowed_miss", 1)))
        success = matched >= max(1, len(expected) - allowed_miss)
    else:
        success = inputs[:len(expected)] == expected

    detail = f"입력={inputs}"
    if minigame.minigame_type in SEQUENCE_TYPES or minigame.minigame_type in TIMING_TYPES:
        detail += f", 정답={expected}"

    logs.extend(_resolve_final(session, actor, current_round, minigame, success, detail))
    return logs


def _resolve_simultaneous(session, actor, selected_value: str, current_round: int, minigame) -> list[str]:
    expected = list(getattr(session, "raid_minigame_expected", []) or [])
    rule = _get_rule(int(minigame.minigame_id))
    if not expected:
        return ["⚠️ 미니게임 상태가 유효하지 않습니다."]

    stage_idx = int(getattr(session, "raid_minigame_stage_index", 0) or 0)
    if stage_idx >= len(expected):
        return ["⚠️ 미니게임 단계가 이미 종료되었습니다."]

    stage_inputs = dict(getattr(session, "raid_minigame_stage_inputs", {}) or {})
    actor_id = str(int(getattr(actor, "id", 0) or 0))
    if not actor_id or actor_id == "0":
        return ["⚠️ 입력자 식별에 실패했습니다."]
    if actor_id in stage_inputs:
        return ["⏳ 이번 단계는 이미 선택 완료했습니다. 다른 파티원을 기다리세요."]

    stage_inputs[actor_id] = selected_value
    session.raid_minigame_stage_inputs = stage_inputs

    alive = _alive_raid_members(session)
    required_min = max(1, int(rule.get("sim_required_alive_min", 1)))
    required_count = max(required_min, len(alive))

    logs: list[str] = []
    token = expected[stage_idx]
    logs.append(f"🎮 동시선택 단계 {stage_idx + 1}/{len(expected)} 제출: {len(stage_inputs)}/{required_count}")
    logs.append(f"📋 {_sim_prompt(token, required_count)}")

    if len(stage_inputs) < required_count:
        return logs

    # 단계 판정
    choices = list(stage_inputs.values())
    stage_success = _eval_sim_stage(token, choices, required_count)
    results = list(getattr(session, "raid_minigame_inputs", []) or [])
    results.append("S" if stage_success else "F")
    session.raid_minigame_inputs = results

    label_map = dict(_choices_for_type(minigame.minigame_type))
    choices_text = ", ".join(label_map.get(c, c) for c in choices)
    logs.append(f"🧮 단계 선택: {choices_text}")
    logs.append("✅ 단계 성공" if stage_success else "❌ 단계 실패")

    # 다음 단계 준비
    session.raid_minigame_stage_index = stage_idx + 1
    session.raid_minigame_stage_inputs = {}

    if session.raid_minigame_stage_index < len(expected):
        return logs

    # 최종 판정: CSV 허용치 기반
    fail_count = sum(1 for x in results if x == "F")
    tolerance = max(0, int(rule.get("sim_fail_tolerance", 1)))
    final_success = fail_count <= tolerance
    logs.extend(_resolve_final(
        session,
        actor,
        current_round,
        minigame,
        final_success,
        detail=f"단계결과={results}, 실패수={fail_count}, 허용={tolerance}",
    ))
    return logs


def resolve_raid_minigame_choice(session, actor, selected_value: str, current_round: int) -> list[str]:
    if not session or not session.raid_id:
        return ["⚠️ 레이드 전투가 아닙니다."]

    minigame = _ensure_minigame_state(session, current_round)
    if not minigame:
        return ["⚠️ 진행 중인 레이드 미니게임이 없습니다."]

    if minigame.minigame_type in SIMULTANEOUS_TYPES:
        return _resolve_simultaneous(session, actor, selected_value, current_round, minigame)
    return _resolve_sequence_or_timing(session, actor, selected_value, current_round, minigame)
