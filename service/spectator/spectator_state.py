"""
관전자 상태 관리

각 관전자의 상태를 추적합니다 (관전 대상, 관전 시작 시간 등).
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class SpectatorState:
    """단일 관전자의 상태"""

    spectator_id: int
    """관전자 Discord 유저 ID"""

    target_id: int
    """관전 대상 Discord 유저 ID"""

    started_at: datetime = None
    """관전 시작 시각"""

    def __post_init__(self):
        if self.started_at is None:
            self.started_at = datetime.now()


# 전역 관전자 상태 추적
_spectator_states: dict[int, SpectatorState] = {}
"""관전자 ID → SpectatorState 매핑"""


def start_spectating(spectator_id: int, target_id: int) -> SpectatorState:
    """
    관전 시작

    Args:
        spectator_id: 관전자 Discord 유저 ID
        target_id: 관전 대상 Discord 유저 ID

    Returns:
        생성된 SpectatorState
    """
    state = SpectatorState(spectator_id=spectator_id, target_id=target_id)
    _spectator_states[spectator_id] = state
    return state


def stop_spectating(spectator_id: int) -> None:
    """
    관전 종료

    Args:
        spectator_id: 관전자 Discord 유저 ID
    """
    if spectator_id in _spectator_states:
        del _spectator_states[spectator_id]


def get_spectator_state(spectator_id: int) -> Optional[SpectatorState]:
    """
    관전자 상태 조회

    Args:
        spectator_id: 관전자 Discord 유저 ID

    Returns:
        SpectatorState 또는 None (관전 중이 아닌 경우)
    """
    return _spectator_states.get(spectator_id)


def is_spectating(spectator_id: int) -> bool:
    """
    관전 중인지 확인

    Args:
        spectator_id: 관전자 Discord 유저 ID

    Returns:
        관전 중이면 True
    """
    return spectator_id in _spectator_states


def get_target_id(spectator_id: int) -> Optional[int]:
    """
    관전 대상 ID 조회

    Args:
        spectator_id: 관전자 Discord 유저 ID

    Returns:
        관전 대상 Discord 유저 ID 또는 None
    """
    state = get_spectator_state(spectator_id)
    return state.target_id if state else None


def get_target_spectators(target_id: int) -> list[SpectatorState]:
    """
    특정 대상을 관전 중인 모든 관전자 조회

    Args:
        target_id: 관전 대상 Discord 유저 ID

    Returns:
        해당 대상을 관전 중인 SpectatorState 리스트
    """
    return [
        state for state in _spectator_states.values()
        if state.target_id == target_id
    ]
