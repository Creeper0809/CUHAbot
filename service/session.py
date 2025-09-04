import asyncio
import logging
from enum import IntEnum

from models import Dungeon
class SessionType(IntEnum):  # 숫자 기반 enum
    IDLE = 1
    FIGHT = 2
    EVENT = 3

class DungeonSession:
    def __init__(self, user_id):
        self.user_id = user_id
        self.dungeon : Dungeon = None
        self.in_combat = False
        self.start_time = asyncio.get_event_loop().time()
        self.ended = False
        self.ui_message = None
        self.user = None
        self.dm_message = None
        self.status = SessionType.IDLE

active_sessions: dict[int, DungeonSession] = {}

def create_session(user_id) -> DungeonSession:
    logging.info(f"Creating session for {user_id}")
    session = DungeonSession(user_id)
    active_sessions[user_id] = session
    return session

def get_session(user_id: int) -> DungeonSession | None:
    return active_sessions.get(user_id)

async def end_session(user_id: int):
    if user_id in active_sessions:
        logging.info(f"End session for {user_id}")
        active_sessions[user_id].ended = True
        await active_sessions[user_id].user.save()
        del active_sessions[user_id]

def is_in_session(user_id: int) -> bool:
    return user_id in active_sessions and not active_sessions[user_id].ended

