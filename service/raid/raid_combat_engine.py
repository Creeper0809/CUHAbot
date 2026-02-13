import logging
from typing import Iterable

from models import User, UserStatEnum
from models.repos.raid_repo import find_all_raid_gimmicks, find_all_raid_parts, find_raid_by_id
from models.repos.static_cache import (
    raid_boss_skills_by_raid_id,
    raid_minigames_by_raid_id,
    raid_phase_transitions_by_raid_id,
)
from service.session import DungeonSession

logger = logging.getLogger(__name__)


def _alive_party(session: DungeonSession, leader: User) -> list[User]:
    players = [leader]
    if session.participants:
        players.extend(session.participants.values())
    return [p for p in players if p.now_hp > 0]


def _apply_party_percent_damage(session: DungeonSession, leader: User, ratio: float) -> list[str]:
    logs = []
    for player in _alive_party(session, leader):
        max_hp = max(1, player.get_stat()[UserStatEnum.HP])
        dmg = max(1, int(max_hp * ratio))
        player.now_hp = max(0, player.now_hp - dmg)
        logs.append(f"💥 **{player.get_name()}** -{dmg} (레이드 기믹)")
    return logs


def _parse_hp_triggers(phase_hp_triggers: str) -> list[int]:
    result = []
    for raw in (phase_hp_triggers or "").split("|"):
        raw = raw.strip()
        if not raw:
            continue
        try:
            result.append(int(raw))
        except ValueError:
            continue
    return sorted(result, reverse=True)


def _extract_pct(token: str) -> float:
    token = token or ""
    if "pct" not in token:
        return 0.0
    for raw in token.split("_"):
        if raw.endswith("pct"):
            try:
                return float(raw.replace("pct", "")) / 100.0
            except ValueError:
                return 0.0
    return 0.0


def _find_transition(session: DungeonSession, transition_id: int):
    for tr in raid_phase_transitions_by_raid_id.get(session.raid_id, []):
        if int(tr.transition_id) == int(transition_id):
            return tr
    return None


def _find_minigame(session: DungeonSession, minigame_id: int):
    for mg in raid_minigames_by_raid_id.get(session.raid_id, []):
        if int(mg.minigame_id) == int(minigame_id):
            return mg
    return None


def _apply_minigame_effect_token(
    session: DungeonSession,
    leader: User,
    boss,
    token: str,
    success: bool,
) -> list[str]:
    token = (token or "").strip()
    if not token:
        return []

    logs: list[str] = []
    session.raid_action_counters[f"effect:{token}"] = _counter(session, f"effect:{token}") + 1

    # 즉시 적용 가능한 효과 우선
    if token.startswith("boss_heal_"):
        ratio = _extract_pct(token)
        if ratio > 0:
            heal = max(1, int(max(1, boss.hp) * ratio))
            before = boss.now_hp
            boss.now_hp = min(boss.hp, boss.now_hp + heal)
            logs.append(f"🩹 보스 회복: +{boss.now_hp - before} ({token})")
            return logs

    if token.startswith("party_hp_loss_"):
        ratio = _extract_pct(token)
        if ratio > 0:
            logs.extend(_apply_party_percent_damage(session, leader, ratio))
            return logs

    if token == "boss_enter_crash_mode":
        session.raid_action_counters["boss_crash_mode"] = _counter(session, "boss_crash_mode") + 1
        logs.append("📉 보스가 급락 모드에 진입했습니다.")
        return logs

    if token.startswith("regen_multiplier_"):
        logs.append(f"🌿 보스 재생 계수 약화 적용: {token}")
        return logs

    if token.startswith("boss_attack_down_"):
        logs.append(f"🛡️ 보스 공격력 약화 적용: {token}")
        return logs

    if success:
        logs.append(f"✅ 미니게임 보너스 적용: {token}")
    else:
        logs.append(f"❌ 미니게임 페널티 적용: {token}")
    return logs


def _counter(session: DungeonSession, key: str) -> int:
    return int((session.raid_action_counters or {}).get(key, 0))


def _eval_clause(session: DungeonSession, clause: str) -> bool:
    clause = clause.strip()
    if not clause:
        return False

    # 문자열 비교 케이스 (part_destroy와 함께 사용)
    if clause == "break_target_part":
        return bool(session.raid_last_broken_part_key)

    for op in (">=", "<=", "=="):
        if op in clause:
            left, right = clause.split(op, 1)
            left = left.strip()
            right = right.strip()
            # 문자열 비교 우선
            if left == "break_target_part":
                val = session.raid_last_broken_part_key or ""
                if op == "==":
                    return val == right
                return False
            cur = _counter(session, left)
            try:
                rhs = int(right)
            except ValueError:
                return False
            if op == ">=":
                return cur >= rhs
            if op == "<=":
                return cur <= rhs
            return cur == rhs

    # 단일 토큰은 1 이상이면 참
    return _counter(session, clause) >= 1


def _eval_success_condition(session: DungeonSession, expr: str) -> bool:
    """
    간단 조건식 파서
    - OR: |
    - AND: &
    - 비교: >=, <=, ==
    """
    expr = (expr or "").strip()
    if not expr:
        return False

    groups = [g.strip() for g in expr.split("|") if g.strip()]
    for group in groups:
        clauses = [c.strip() for c in group.split("&") if c.strip()]
        if clauses and all(_eval_clause(session, c) for c in clauses):
            return True
    return False


def process_raid_phase_transition(
    session: DungeonSession,
    leader: User,
    boss,
    combat_log: Iterable[str],
    current_round: int = 1,
) -> list[str]:
    """보스 HP 기반 페이즈 전환 처리"""
    if not session.raid_id:
        return []

    raid = find_raid_by_id(session.raid_id)
    if not raid:
        return []

    logs: list[str] = []
    hp_pct = int((boss.now_hp / max(1, boss.hp)) * 100)
    triggers = _parse_hp_triggers(raid.phase_hp_triggers)

    target_phase = 1
    for trigger in triggers:
        if hp_pct <= trigger:
            target_phase += 1

    target_phase = min(target_phase, max(1, raid.phase_count))
    if target_phase <= session.raid_phase:
        return []

    from_phase = session.raid_phase
    session.raid_phase = target_phase
    logs.append(f"🌗 레이드 페이즈 전환: **P{from_phase} -> P{target_phase}**")

    transitions = raid_phase_transitions_by_raid_id.get(session.raid_id, [])
    for tr in transitions:
        if tr.from_phase != from_phase or tr.to_phase != target_phase:
            continue
        minigame = None
        for mg in raid_minigames_by_raid_id.get(session.raid_id, []):
            if mg.minigame_id == tr.minigame_id:
                minigame = mg
                break
        if minigame:
            session.raid_pending_transition_id = tr.transition_id
            session.raid_pending_minigame_id = minigame.minigame_id
            session.raid_minigame_started_round = int(current_round)
            session.raid_minigame_inputs = []
            session.raid_minigame_expected = []
            session.raid_minigame_prompt = None
            session.raid_minigame_stage_inputs = {}
            session.raid_minigame_stage_index = 0
            logs.append(f"🎮 전환 미니게임 대기: **{minigame.minigame_name}**")
            logs.append(f"  성공 시: {minigame.success_effect}")
            logs.append(f"  실패 시: {minigame.fail_effect}")
            logs.append("  전투 UI의 미니게임 버튼(또는 선택 메뉴)으로 입력하세요.")

    return logs


def resolve_pending_raid_minigame(
    session: DungeonSession,
    leader: User,
    boss,
    success: bool,
    current_round: int,
    actor_name: str | None = None,
    reason: str | None = None,
) -> list[str]:
    """대기 중인 레이드 전환 미니게임 결과 적용"""
    if not session.raid_id:
        return []
    if not session.raid_pending_transition_id or not session.raid_pending_minigame_id:
        return []

    tr = _find_transition(session, int(session.raid_pending_transition_id))
    mg = _find_minigame(session, int(session.raid_pending_minigame_id))

    # 대기 상태 해제
    session.raid_pending_transition_id = None
    session.raid_pending_minigame_id = None
    session.raid_minigame_started_round = 0
    session.raid_minigame_inputs = []
    session.raid_minigame_expected = []
    session.raid_minigame_prompt = None
    session.raid_minigame_stage_inputs = {}
    session.raid_minigame_stage_index = 0

    if not tr or not mg:
        return ["⚠️ 전환 미니게임 메타데이터를 찾지 못해 결과 적용을 건너뜁니다."]

    logs: list[str] = []
    who = f" ({actor_name})" if actor_name else ""
    why = f" - {reason}" if reason else ""
    verdict = "성공" if success else "실패"
    logs.append(f"🎮 전환 미니게임 결과{who}: **{mg.minigame_name}** {verdict}{why}")

    if success:
        logs.extend(_apply_minigame_effect_token(session, leader, boss, mg.success_effect, True))
        logs.extend(_apply_minigame_effect_token(session, leader, boss, tr.success_buff_key, True))
        session.raid_action_counters["minigame_success"] = _counter(session, "minigame_success") + 1
    else:
        logs.extend(_apply_minigame_effect_token(session, leader, boss, mg.fail_effect, False))
        logs.extend(_apply_minigame_effect_token(session, leader, boss, tr.fail_penalty_key, False))
        session.raid_action_counters["minigame_fail"] = _counter(session, "minigame_fail") + 1

    return logs


def process_pending_raid_minigame_timeout(
    session: DungeonSession,
    leader: User,
    boss,
    current_round: int,
) -> list[str]:
    """미니게임이 라운드 내 처리되지 않으면 자동 실패 처리"""
    if not session.raid_pending_transition_id or not session.raid_pending_minigame_id:
        return []
    started = int(getattr(session, "raid_minigame_started_round", 0) or 0)
    if started <= 0:
        started = current_round
    # 시작 라운드가 지나도 입력이 없으면 실패
    if current_round <= started:
        return []
    return resolve_pending_raid_minigame(
        session=session,
        leader=leader,
        boss=boss,
        success=False,
        current_round=current_round,
        actor_name=None,
        reason="라운드 제한 초과",
    )


def _lock_skills_for_part_break(session: DungeonSession, part_key: str) -> list[str]:
    logs: list[str] = []
    skills = raid_boss_skills_by_raid_id.get(session.raid_id, [])
    for row in skills:
        if not row.removable_by_part:
            continue
        if row.remove_source_part_key != part_key:
            continue
        if row.skill_key in session.raid_locked_skills:
            continue
        session.raid_locked_skills.add(row.skill_key)
        logs.append(f"🔒 보스 스킬 봉인: **{row.skill_name}**")
    return logs


def process_raid_part_breaks(
    session: DungeonSession,
    boss,
    part_damage: int = 0,
    current_round: int = 1,
) -> list[str]:
    """부위별 HP 누적 파괴/스킬 봉인 처리"""
    if not session.raid_id:
        return []
    if part_damage <= 0:
        return []

    logs: list[str] = []
    parts = [p for p in find_all_raid_parts(session.raid_id) if p.part_key != "body"]
    if not parts:
        return []

    target_key = session.raid_current_target or (session.raid_target_priority[0] if session.raid_target_priority else None)
    target = None
    for part in parts:
        if part.part_key != target_key:
            continue
        if not part.destructible:
            continue
        if current_round < int(part.targetable_from_turn):
            continue
        if part.part_key in session.raid_destroyed_parts:
            continue
        target = part
        break
    if target is None:
        return []

    current_hp = session.raid_part_hp.get(target.part_key, 0)
    session.raid_action_counters[f"{target.part_key}_hit_count"] = _counter(session, f"{target.part_key}_hit_count") + 1
    if current_hp <= 0:
        return []

    remain = max(0, current_hp - part_damage)
    # defense_multiplier > 1.0 이면 더 단단, < 1.0 이면 더 약함
    adjusted = max(1, int(part_damage / max(0.1, float(target.defense_multiplier))))
    remain = max(0, current_hp - adjusted)
    session.raid_part_hp[target.part_key] = remain
    max_hp = max(1, session.raid_part_max_hp.get(target.part_key, remain))
    logs.append(
        f"🎯 부위 타격: **{target.part_name}** -{adjusted} "
        f"(남은 내구도 {remain}/{max_hp})"
    )

    if remain > 0:
        return logs

    session.raid_destroyed_parts.add(target.part_key)
    session.raid_last_broken_part_key = target.part_key
    session.raid_action_counters[f"break_{target.part_key}"] = 1
    logs.append(f"🧩 부위 파괴: **{target.part_name}**")
    logs.extend(_lock_skills_for_part_break(session, target.part_key))
    return logs


def process_raid_round_gimmicks(session: DungeonSession, leader: User, round_number: int) -> list[str]:
    """라운드 시작 시 기믹 처리 (interval_turn 중심)"""
    if not session.raid_id:
        return []

    logs: list[str] = []
    for gimmick in find_all_raid_gimmicks(session.raid_id):
        if gimmick.phase != session.raid_phase:
            continue
        if gimmick.trigger_type != "interval_turn":
            continue

        try:
            interval = int(gimmick.trigger_value)
        except ValueError:
            interval = 0
        if interval <= 0:
            continue
        if round_number % interval != 0:
            continue
        last_round = int((session.raid_gimmick_last_round or {}).get(gimmick.gimmick_key, 0))
        cooldown = int(getattr(gimmick, "cooldown_turns", 0) or 0)
        if last_round > 0 and round_number - last_round <= cooldown:
            continue

        logs.append(f"⚠️ 기믹 발동: **{gimmick.gimmick_name}**")
        session.raid_gimmick_last_round[gimmick.gimmick_key] = round_number

        success = _eval_success_condition(session, gimmick.success_condition_value or "")
        if success:
            logs.append(f"✅ 기믹 파훼 성공: {gimmick.success_effect}")
            continue

        fail = gimmick.fail_effect or ""
        logs.append(f"❌ 기믹 실패: {fail}")
        if "lethal" in fail:
            logs.extend(_apply_party_percent_damage(session, leader, 0.25))
        elif "aoe" in fail or "damage" in fail:
            logs.extend(_apply_party_percent_damage(session, leader, 0.12))

    return logs


def filter_locked_boss_skills(session: DungeonSession, skill_ids: list[int]) -> list[int]:
    """
    봉인된 보스 스킬을 스킬 덱에서 제거.
    skill_key → skill_id 정밀 매핑은 아직 없으므로, 봉인 수만큼 뒤쪽 슬롯을 비활성화한다.
    """
    if not session.raid_id or not session.raid_locked_skills:
        return skill_ids

    result = skill_ids[:]
    locked_keys = set(session.raid_locked_skills)
    known_skills = raid_boss_skills_by_raid_id.get(session.raid_id, [])
    locked_skill_ids = {
        int(s.skill_id) for s in known_skills
        if s.skill_key in locked_keys and s.skill_id is not None
    }

    # 1) skill_id 매핑이 존재하면 정확 제거
    if locked_skill_ids:
        for i, sid in enumerate(result):
            if sid in locked_skill_ids:
                result[i] = 0
        return result

    # 2) 매핑 미존재 시 기존 fallback
    locked_count = len(locked_keys)
    disabled = 0
    for i in range(len(result) - 1, -1, -1):
        if result[i] != 0:
            result[i] = 0
            disabled += 1
            if disabled >= locked_count:
                break
    return result


def get_boss_skill_lock_summary(session: DungeonSession) -> list[str]:
    if not session.raid_id:
        return []
    if not session.raid_locked_skills:
        return []

    known_skills = raid_boss_skills_by_raid_id.get(session.raid_id, [])
    locked = sorted(session.raid_locked_skills)
    if not known_skills:
        return [f"🔒 봉인 스킬: {', '.join(locked)}"]

    mapping = {s.skill_key: s.skill_name for s in known_skills}
    labels = [mapping.get(k, k) for k in locked]
    return [f"🔒 봉인 스킬: {', '.join(labels)}"]
