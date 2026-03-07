import logging
from typing import Optional

from models.repos.raid_repo import (
    find_all_raid_parts,
    find_raid_by_dungeon_id,
    find_raid_targeting_rule,
)
from service.session import DungeonSession

logger = logging.getLogger(__name__)


def init_raid_session_state(session: DungeonSession) -> None:
    """세션의 레이드 런타임 상태 초기화"""
    if not session.dungeon:
        return

    raid = find_raid_by_dungeon_id(session.dungeon.id)
    if not raid:
        logger.warning(f"Raid metadata not found for dungeon_id={session.dungeon.id}")
        return

    session.raid_id = raid.raid_id
    session.raid_phase = 1
    session.raid_current_target = None
    session.raid_pending_target = None
    session.raid_target_apply_turn = 0
    session.raid_destroyed_parts = set()
    session.raid_locked_skills = set()
    session.raid_part_hp = {}
    session.raid_part_max_hp = {}
    session.raid_target_priority = [
        raid.default_priority_1,
        raid.default_priority_2,
        raid.default_priority_3,
    ]
    session.raid_action_used_round = {}
    session.raid_action_next_round = {}
    session.raid_action_counters = {}
    session.raid_provoke_target_discord_id = None
    session.raid_provoke_until_round = 0
    session.raid_last_broken_part_key = None
    session.raid_gimmick_last_round = {}
    session.raid_pending_transition_id = None
    session.raid_pending_minigame_id = None
    session.raid_minigame_started_round = 0
    session.raid_minigame_inputs = []
    session.raid_minigame_expected = []
    session.raid_minigame_prompt = None
    session.raid_minigame_stage_inputs = {}
    session.raid_minigame_stage_index = 0


def init_raid_part_state_from_boss(session: DungeonSession, boss) -> None:
    """보스 최대 HP 기준으로 레이드 부위 HP를 초기화"""
    if not session.raid_id:
        return
    if not boss:
        return

    part_hp = {}
    part_max = {}
    for part in find_all_raid_parts(session.raid_id):
        if part.part_key == "body":
            continue
        max_hp = max(1, int(boss.hp * float(part.max_hp_ratio)))
        part_hp[part.part_key] = max_hp
        part_max[part.part_key] = max_hp

    session.raid_part_hp = part_hp
    session.raid_part_max_hp = part_max


def queue_raid_target_selection(session: DungeonSession, part_key: str, current_round: int) -> bool:
    """
    드롭다운 선택 반영 예약.
    적용은 즉시가 아니라 다음 턴/라운드부터 반영된다.
    """
    if not session.raid_id:
        return False

    rule = find_raid_targeting_rule(session.raid_id)
    delay = rule.apply_delay_turns if rule else 1

    session.raid_pending_target = part_key
    session.raid_target_apply_turn = current_round + delay
    return True


def apply_pending_raid_target_selection(session: DungeonSession, current_round: int) -> Optional[str]:
    """다음 턴 적용 규칙에 맞춰 예약된 타겟 선택을 적용"""
    if not session.raid_pending_target:
        return None
    if current_round < session.raid_target_apply_turn:
        return None

    session.raid_current_target = session.raid_pending_target
    session.raid_pending_target = None
    session.raid_target_apply_turn = 0
    return session.raid_current_target


def get_effective_raid_target(session: DungeonSession) -> Optional[str]:
    """현재 라운드 기준 유효 우선 타겟 반환"""
    if session.raid_current_target:
        return session.raid_current_target
    if session.raid_target_priority:
        return session.raid_target_priority[0]
    return None
