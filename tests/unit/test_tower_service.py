"""
주간 타워 서비스 핵심 동작 테스트
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from service.session import ContentType
from service.tower.tower_service import _normalize_tower_start_floor, _handle_tower_complete
from service.dungeon.encounter_processor import process_encounter


class TestTowerEncounterFlow:
    @pytest.mark.asyncio
    async def test_tower_process_encounter_skips_social_events(self, monkeypatch):
        async def _fake_process_monster(_session, _interaction):
            return "tower-combat"

        monkeypatch.setattr(
            "service.dungeon.encounter_processor._process_monster_encounter",
            _fake_process_monster,
        )

        def _social_should_not_be_called(_session):
            raise AssertionError("tower should not call social encounter checker")

        monkeypatch.setattr(
            "service.dungeon.social_encounter_checker.check_social_encounter",
            _social_should_not_be_called,
        )

        session = SimpleNamespace(
            exploration_step=0,
            content_type=ContentType.WEEKLY_TOWER,
        )

        result = await process_encounter(session, interaction=SimpleNamespace())

        assert result == "tower-combat"
        assert session.exploration_step == 1


class TestTowerService:
    def test_normalize_tower_start_floor(self):
        assert _normalize_tower_start_floor(1) == 1
        assert _normalize_tower_start_floor(50) == 50
        assert _normalize_tower_start_floor(100) == 100
        assert _normalize_tower_start_floor(0) == 1
        assert _normalize_tower_start_floor(101) == 1
        assert _normalize_tower_start_floor(-5) == 1

    @pytest.mark.asyncio
    async def test_tower_complete_resets_current_floor(self, monkeypatch):
        reward_result = SimpleNamespace(exp_gained=123, gold_gained=456)
        monkeypatch.setattr(
            "service.economy.reward_service.RewardService.apply_rewards",
            AsyncMock(return_value=reward_result),
        )
        mock_save_progress = AsyncMock()
        monkeypatch.setattr("service.tower.tower_service.save_progress", mock_save_progress)

        progress = SimpleNamespace(current_floor=101, tower_coins=0)
        session = SimpleNamespace(
            tower_result=None,
            ended=False,
            user=SimpleNamespace(),
            tower_progress=progress,
        )
        interaction = SimpleNamespace(
            followup=SimpleNamespace(send=AsyncMock()),
        )

        await _handle_tower_complete(session, interaction)

        assert session.tower_result == "complete"
        assert session.ended is True
        assert progress.current_floor == 0
        assert progress.tower_coins == 50
        mock_save_progress.assert_awaited_once_with(progress)

