import pytest
from unittest.mock import AsyncMock

from e2e_runtime.runner import DiscordSuiteRunner
from e2e_runtime.semantic_scenarios import _execute_scenario
from service.economy.reward_service import RewardService, get_exp_to_next_level
from service.player.user_service import UserService


def test_all_suite_includes_semantics_without_visual() -> None:
    runner = object.__new__(DiscordSuiteRunner)

    assert runner._suite_order("all") == (
        "gateway",
        "components",
        "gameflow",
        "commands",
        "dungeon",
        "semantics",
        "roguelike",
        "rewards",
        "balance",
        "farming",
        "buildcraft",
        "economy",
    )


@pytest.mark.asyncio
async def test_semantic_failure_preserves_scenario_name_and_traceback() -> None:
    async def broken(_users):
        raise ValueError("broken contract")

    result = await _execute_scenario("semantic-broken", broken, {})

    assert result.status == "failed"
    assert result.name == "semantic-broken"
    assert "ValueError: broken contract" in result.details
    assert "Traceback (most recent call last)" in result.details


def _leveling_user():
    base = UserService.calculate_base_stats(1)

    class FakeUser:
        discord_id = 123
        level = 1
        exp = 0
        gold = 0
        stat_points = 0
        hp = base["hp"]
        now_hp = base["hp"] // 2
        attack = base["attack"]
        ap_attack = base["ap_attack"]
        defense = base["ad_defense"]
        ap_defense = base["ap_defense"]
        speed = base["speed"]
        save = AsyncMock()

    return FakeUser()


@pytest.mark.asyncio
async def test_reward_level_up_persists_all_base_stats_and_hp_ratio() -> None:
    user = _leveling_user()
    required = get_exp_to_next_level(1)

    result = await RewardService.apply_rewards(user, required, 0)

    expected = UserService.calculate_base_stats(2)
    assert result.level_up is not None
    assert (user.level, user.exp, user.stat_points) == (2, required, 3)
    assert (user.hp, user.attack, user.ap_attack, user.defense, user.ap_defense, user.speed) == (
        expected["hp"],
        expected["attack"],
        expected["ap_attack"],
        expected["ad_defense"],
        expected["ap_defense"],
        expected["speed"],
    )
    assert user.now_hp == int(expected["hp"] * 0.5)


@pytest.mark.asyncio
async def test_user_experience_path_uses_cumulative_reward_contract() -> None:
    user = _leveling_user()
    user.now_hp = user.hp
    required = get_exp_to_next_level(1)

    result = await UserService.add_experience(user, required)

    assert result["leveled_up"]
    assert (user.level, user.exp, user.stat_points) == (2, required, 3)
    assert user.now_hp == user.hp == UserService.calculate_base_stats(2)["hp"]
