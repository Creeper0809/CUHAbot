"""
관전 시스템 모듈

실시간 전투 관전 기능을 제공합니다.
"""
from service.spectator.spectator_service import SpectatorService
from service.spectator.spectator_state import (
    SpectatorState,
    start_spectating,
    stop_spectating,
    get_spectator_state,
    is_spectating,
    get_target_id,
    get_target_spectators,
)

__all__ = [
    "SpectatorService",
    "SpectatorState",
    "start_spectating",
    "stop_spectating",
    "get_spectator_state",
    "is_spectating",
    "get_target_id",
    "get_target_spectators",
]
