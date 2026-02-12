"""
주간 타워 제약 조건
"""
from exceptions import WeeklyTowerRestrictionError
from service.session import DungeonSession, ContentType, SessionType


def _is_tower(session: DungeonSession) -> bool:
    return bool(session and session.content_type == ContentType.WEEKLY_TOWER)


def enforce_item_usage_restriction(session: DungeonSession) -> None:
    if _is_tower(session):
        raise WeeklyTowerRestrictionError("아이템을 사용할 수 없습니다.")


def enforce_skill_change_restriction(session: DungeonSession) -> None:
    if _is_tower(session):
        # 주간 타워는 "층 사이(비전투)" 스킬 변경 허용
        if session.status not in (SessionType.IDLE, SessionType.REST):
            raise WeeklyTowerRestrictionError("층 사이에서만 스킬을 변경할 수 있습니다.")


def enforce_equipment_change_restriction(session: DungeonSession) -> None:
    if _is_tower(session):
        if session.status != SessionType.REST:
            raise WeeklyTowerRestrictionError("휴식공간에서만 장비를 변경할 수 있습니다.")


def enforce_flee_restriction(session: DungeonSession) -> None:
    if _is_tower(session):
        raise WeeklyTowerRestrictionError("도주할 수 없습니다.")
