"""
주간 타워 제한 규칙 테스트
"""
from types import SimpleNamespace

import pytest

from exceptions import WeeklyTowerRestrictionError
from service.session import ContentType, SessionType
from service.tower.tower_restriction import enforce_skill_change_restriction


class TestTowerSkillRestriction:
    def test_allow_skill_change_between_floors_in_tower(self):
        session = SimpleNamespace(
            content_type=ContentType.WEEKLY_TOWER,
            status=SessionType.IDLE,
        )

        enforce_skill_change_restriction(session)

    def test_block_skill_change_during_fight_in_tower(self):
        session = SimpleNamespace(
            content_type=ContentType.WEEKLY_TOWER,
            status=SessionType.FIGHT,
        )

        with pytest.raises(WeeklyTowerRestrictionError):
            enforce_skill_change_restriction(session)

