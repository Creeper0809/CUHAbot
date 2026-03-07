import asyncio
from dataclasses import dataclass, field


@dataclass
class RaidLobbyState:
    leader_id: int
    raid_id: int
    raid_name: str
    dungeon_id: int
    required_level: int
    max_party_size: int
    voice_channel_id: int | None
    timeout_seconds: int = 60
    participants: dict[int, bool] = field(default_factory=dict)
    consumed_entries: dict[int, tuple[int, int]] = field(default_factory=dict)
    started: bool = False
    cancelled: bool = False
    event: asyncio.Event = field(default_factory=asyncio.Event)

    def party_size(self) -> int:
        return len(self.participants)

    def ready_count(self) -> int:
        return sum(1 for ready in self.participants.values() if ready)

    def is_full(self) -> bool:
        return self.party_size() >= self.max_party_size

    def all_ready(self) -> bool:
        if not self.participants:
            return False
        return all(self.participants.values())


_raid_lobbies_by_leader: dict[int, RaidLobbyState] = {}


def create_raid_lobby(
    leader_id: int,
    raid_id: int,
    raid_name: str,
    dungeon_id: int,
    required_level: int,
    max_party_size: int,
    voice_channel_id: int | None,
    timeout_seconds: int = 60,
) -> RaidLobbyState:
    lobby = RaidLobbyState(
        leader_id=leader_id,
        raid_id=raid_id,
        raid_name=raid_name,
        dungeon_id=dungeon_id,
        required_level=required_level,
        max_party_size=max_party_size,
        voice_channel_id=voice_channel_id,
        timeout_seconds=timeout_seconds,
    )
    # 리더는 기본적으로 준비 완료 상태로 진입
    lobby.participants[leader_id] = True
    _raid_lobbies_by_leader[leader_id] = lobby
    return lobby


def get_raid_lobby(leader_id: int) -> RaidLobbyState | None:
    return _raid_lobbies_by_leader.get(leader_id)


def close_raid_lobby(leader_id: int) -> None:
    _raid_lobbies_by_leader.pop(leader_id, None)


async def wait_raid_lobby_result(lobby: RaidLobbyState) -> str:
    """
    Returns:
        "started" | "cancelled" | "timeout_auto_start"
    """
    try:
        await asyncio.wait_for(lobby.event.wait(), timeout=lobby.timeout_seconds)
    except asyncio.TimeoutError:
        if not lobby.cancelled and not lobby.started:
            lobby.started = True
            lobby.event.set()
            return "timeout_auto_start"

    if lobby.cancelled:
        return "cancelled"
    if lobby.started:
        return "started"
    return "cancelled"

