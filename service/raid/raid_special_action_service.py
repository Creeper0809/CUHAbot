from models.repos.raid_repo import find_raid_special_actions
from service.dungeon.status.helpers import remove_status_effects
from service.raid.raid_combat_engine import process_raid_part_breaks


def use_raid_special_action(session, actor, action_key: str, current_round: int) -> list[str]:
    """
    레이드 특수 액션 사용 처리.
    반환 로그를 전투 로그에 추가해 UI에 반영한다.
    """
    logs: list[str] = []

    if not session or not session.raid_id:
        return ["⚠️ 레이드 전투에서만 사용할 수 있습니다."]
    if not session.combat_context or not session.combat_context.monsters:
        return ["⚠️ 현재 전투 정보가 없습니다."]

    actions = find_raid_special_actions()
    action = actions.get(action_key)
    if not action:
        return ["⚠️ 존재하지 않는 특수 액션입니다."]

    actor_id = int(getattr(actor, "discord_id", 0))
    if actor_id <= 0:
        return ["⚠️ 액터 정보가 올바르지 않습니다."]

    # 라운드당 1회 제한 (플레이어 기준)
    used_round = session.raid_action_used_round.get(actor_id, 0)
    if used_round == current_round:
        return [f"⏳ {actor.get_name()}님은 이번 라운드에 이미 특수 액션을 사용했습니다."]

    # 액션별 쿨다운 체크
    cd_key = f"{actor_id}:{action_key}"
    available_round = session.raid_action_next_round.get(cd_key, 1)
    if current_round < available_round:
        remain = available_round - current_round
        return [f"⏳ `{action.action_name}` 쿨다운 {remain}라운드 남음"]

    # 사용 확정
    session.raid_action_used_round[actor_id] = current_round
    cooldown_rounds = int(getattr(action, "cooldown_rounds", 0) or 0)
    session.raid_action_next_round[cd_key] = current_round + cooldown_rounds + 1
    session.raid_action_counters[action_key] = session.raid_action_counters.get(action_key, 0) + 1

    boss = session.combat_context.monsters[0]
    logs.append(f"🛠️ **{actor.get_name()}** 특수 액션 사용: `{action.action_name}`")

    if action_key == "cut":
        part_damage = int(getattr(action, "base_value", 0) or 0)
        session.raid_action_counters["cut_count"] = session.raid_action_counters.get("cut_count", 0) + 1
        cut_logs = process_raid_part_breaks(
            session,
            boss,
            part_damage=part_damage,
            current_round=current_round,
        )
        if cut_logs:
            logs.extend(cut_logs)
        else:
            logs.append("⚠️ 절단 대상 부위가 없거나 타격에 실패했습니다.")

    elif action_key == "seal":
        # 기믹 카운터용 봉인 누적
        session.raid_action_counters["seal_count"] = session.raid_action_counters.get("seal_count", 0) + 1
        logs.append("🔏 보스 충전/카운트다운 흐름을 교란했습니다.")

    elif action_key == "cleanse":
        result = remove_status_effects(actor, count=99, filter_debuff=True)
        session.raid_action_counters["cleanse_count"] = session.raid_action_counters.get("cleanse_count", 0) + 1
        if result:
            logs.append(result)
        else:
            logs.append("✨ 해제할 디버프가 없습니다.")

    elif action_key == "provoke":
        session.raid_provoke_target_discord_id = actor_id
        session.raid_provoke_until_round = current_round + 1
        session.raid_action_counters["provoke_success"] = session.raid_action_counters.get("provoke_success", 0) + 1
        logs.append(f"🧲 보스의 단일 공격이 **{actor.get_name()}**에게 유도됩니다.")

    else:
        logs.append("⚠️ 아직 연결되지 않은 특수 액션입니다.")

    return logs
