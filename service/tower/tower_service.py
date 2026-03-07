"""
주간 타워 서비스
"""
from __future__ import annotations

import logging
import random
from datetime import datetime, timezone

import discord

from config import WEEKLY_TOWER
from exceptions import WeeklyTowerRestrictionError
from models import Dungeon, MonsterTypeEnum
from models.repos.dungeon_repo import find_all_dungeon_spawn_monster_by
from models.repos.monster_repo import find_monster_by_id
from models.repos.static_cache import dungeon_cache, monster_cache_by_id
from models.repos.tower_progress_repo import get_or_create_progress, save_progress
from service.session import ContentType, SessionType, DungeonSession, end_session
from service.tower.tower_reward_service import calculate_floor_reward, apply_floor_reward
from service.tower.tower_season_service import get_current_season

logger = logging.getLogger(__name__)

FLOOR_DUNGEON_MAP = {
    (1, 10): 1,
    (11, 20): 2,
    (21, 30): 3,
    (31, 40): 4,
    (41, 50): 5,
    (51, 60): 6,
    (61, 70): 7,
    (71, 80): 8,
    (81, 90): 9,
    (91, 100): 10,
}


def get_dungeon_for_floor(floor: int) -> int:
    for (start, end), dungeon_id in FLOOR_DUNGEON_MAP.items():
        if start <= floor <= end:
            return dungeon_id
    return 10


def is_boss_floor(floor: int) -> bool:
    return floor % WEEKLY_TOWER.BOSS_FLOOR_INTERVAL == 0


def _normalize_tower_start_floor(current_floor: int) -> int:
    if 1 <= current_floor <= WEEKLY_TOWER.TOTAL_FLOORS:
        return current_floor
    return 1


async def initialize_tower_session(user, session: DungeonSession):
    season_id = get_current_season()
    progress = await get_or_create_progress(user, season_id)

    # 과거 버그/수동 수정으로 current_floor가 범위를 벗어난 경우 복구
    if progress.current_floor > WEEKLY_TOWER.TOTAL_FLOORS or progress.current_floor < 0:
        progress.current_floor = 0
        await save_progress(progress)

    session.user = user
    session.content_type = ContentType.WEEKLY_TOWER
    session.current_floor = _normalize_tower_start_floor(progress.current_floor)
    session.status = SessionType.IDLE
    session.tower_progress = progress

    return progress


async def prepare_floor(session: DungeonSession, progress) -> None:
    session.ended = False
    session.pending_exit = False
    session.status = SessionType.IDLE
    session.exploration_step = 0
    session.max_steps = 1
    session.total_exp = 0
    session.total_gold = 0
    session.monsters_defeated = 0
    session.items_found = []

    session.current_floor = _normalize_tower_start_floor(progress.current_floor)
    dungeon_id = get_dungeon_for_floor(session.current_floor)
    session.dungeon = dungeon_cache.get(dungeon_id) or await Dungeon.get(id=dungeon_id)


async def get_floor_monster(tower_floor: int):
    dungeon_id = get_dungeon_for_floor(tower_floor)
    spawns = find_all_dungeon_spawn_monster_by(dungeon_id)

    if not spawns:
        raise WeeklyTowerRestrictionError("몬스터 스폰 정보를 찾을 수 없습니다.")

    if is_boss_floor(tower_floor):
        monster_ids = [spawn.monster_id for spawn in spawns]
        boss_candidates = [
            monster_cache_by_id[mid]
            for mid in monster_ids
            if mid in monster_cache_by_id and monster_cache_by_id[mid].type in (MonsterTypeEnum.BOSS, MonsterTypeEnum.BOSS.value)
        ]
        if not boss_candidates:
            boss_candidates = [
                m for m in monster_cache_by_id.values()
                if getattr(m, "type", None) in (MonsterTypeEnum.BOSS, MonsterTypeEnum.BOSS.value)
            ]
        if not boss_candidates:
            chosen_spawn = random.choice(spawns)
            return find_monster_by_id(chosen_spawn.monster_id)
        chosen = random.choice(boss_candidates)
        return find_monster_by_id(chosen.id)

    weights = [spawn.prob for spawn in spawns]
    chosen_spawn = random.choices(spawns, weights=weights, k=1)[0]
    return find_monster_by_id(chosen_spawn.monster_id)


async def handle_floor_clear(session: DungeonSession, interaction: discord.Interaction) -> None:
    progress = getattr(session, "tower_progress", None)
    if not progress:
        return

    cleared_floor = session.current_floor
    is_boss = is_boss_floor(cleared_floor)

    reward = calculate_floor_reward(cleared_floor, is_boss)
    reward_result = await apply_floor_reward(
        session.user, progress, cleared_floor, is_boss
    )

    progress.current_floor = cleared_floor + 1
    if cleared_floor > progress.highest_floor_reached:
        progress.highest_floor_reached = cleared_floor

    await save_progress(progress)

    if progress.current_floor > WEEKLY_TOWER.TOTAL_FLOORS:
        await _handle_tower_complete(session, interaction)
        return

    if cleared_floor % WEEKLY_TOWER.BOSS_FLOOR_INTERVAL == 0:
        await enter_rest_area(session, interaction, reward_result, reward.tower_coins)
        return

    await _show_floor_clear_ui(session, interaction, reward_result, reward.tower_coins, cleared_floor)


async def _show_floor_clear_ui(
    session: DungeonSession,
    interaction: discord.Interaction,
    reward_result,
    tower_coins: int,
    cleared_floor: int
) -> None:
    from views.tower_view import TowerFloorClearView

    view = TowerFloorClearView(interaction.user, cleared_floor)
    embed = view.create_embed(session.user, reward_result, tower_coins)

    await interaction.followup.send(embed=embed, view=view, ephemeral=True)
    await view.wait()

    if view.action == "next":
        session.tower_result = "next"
    else:
        session.tower_result = "return"
        session.ended = True


async def enter_rest_area(
    session: DungeonSession,
    interaction: discord.Interaction,
    reward_result,
    tower_coins: int
) -> None:
    from views.tower_rest_area_view import TowerRestAreaView

    session.status = SessionType.REST

    view = TowerRestAreaView(interaction.user, session.user, session)
    embed = view.create_embed(reward_result, tower_coins)

    await interaction.followup.send(embed=embed, view=view, ephemeral=True)
    await view.wait()

    session.status = SessionType.IDLE

    if view.action == "next":
        session.tower_result = "next"
    else:
        session.tower_result = "return"
        session.ended = True


async def handle_tower_death(session: DungeonSession, interaction: discord.Interaction) -> None:
    progress = getattr(session, "tower_progress", None)
    if progress:
        progress.current_floor = 0
        await save_progress(progress)

    session.tower_result = "death"
    session.ended = True

    embed = discord.Embed(
        title="💀 타워에서 쓰러졌습니다",
        description=(
            f"최고 기록: **{progress.highest_floor_reached if progress else 0}층**\n"
            "다시 1층부터 도전하세요."
        ),
        color=discord.Color.dark_red()
    )
    await interaction.followup.send(embed=embed, ephemeral=True)


async def _handle_tower_complete(session: DungeonSession, interaction: discord.Interaction) -> None:
    from service.economy.reward_service import RewardService

    session.tower_result = "complete"
    session.ended = True

    reward_result = await RewardService.apply_rewards(session.user, 50000, 100000)
    if getattr(session, "tower_progress", None):
        session.tower_progress.tower_coins += 50
        # 완주 후에는 다음 도전을 1층부터 시작한다.
        session.tower_progress.current_floor = 0
        await save_progress(session.tower_progress)

    embed = discord.Embed(
        title="🎊 타워 정복!",
        description="주간 타워 100층을 클리어했습니다!",
        color=discord.Color.gold()
    )
    embed.add_field(
        name="완료 보상",
        value=f"💎 경험치: +{reward_result.exp_gained:,}\n💰 골드: +{reward_result.gold_gained:,}\n🪙 타워 코인: +50",
        inline=False
    )
    await interaction.followup.send(embed=embed, ephemeral=True)


async def run_tower(session: DungeonSession, interaction: discord.Interaction) -> None:
    progress = getattr(session, "tower_progress", None)
    if not progress:
        return

    while True:
        await prepare_floor(session, progress)
        session.tower_result = None

        from service.dungeon.dungeon_service import start_dungeon
        await start_dungeon(session, interaction)

        result = getattr(session, "tower_result", None)
        if result == "next":
            continue
        if result in {"return", "death", "complete"}:
            await end_session(session.user_id)
            break
        await end_session(session.user_id)
        break
