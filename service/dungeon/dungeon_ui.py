"""
던전 UI - HP바, 전투 임베드, 던전 임베드, 진행바

전투 및 던전 진행 중 표시되는 Discord 임베드를 생성합니다.
"""
from collections import deque
from typing import Union

from discord import Embed

from config import COMBAT, EmbedColor
from models import UserStatEnum, User, Monster
from service.dungeon.status import get_status_icons
from service.dungeon.combat_context import CombatContext


# =============================================================================
# HP/게이지 바 생성
# =============================================================================


def create_hp_bar(current: int, maximum: int, length: int = 10) -> str:
    """HP 바 생성"""
    ratio = max(0, min(current / maximum, 1.0)) if maximum > 0 else 0
    filled = int(ratio * length)
    empty = length - filled

    if ratio > 0.6:
        bar_char = "🟩"
    elif ratio > 0.3:
        bar_char = "🟨"
    else:
        bar_char = "🟥"

    return bar_char * filled + "⬛" * empty


def create_gauge_bar(gauge: int, length: int = 8) -> str:
    """행동 게이지 바 생성"""
    ratio = max(0, min(gauge / COMBAT.ACTION_GAUGE_MAX, 1.0))
    filled = int(ratio * length)
    empty = length - filled

    if gauge >= COMBAT.ACTION_GAUGE_MAX:
        return "⚡" * length
    return "🟦" * filled + "⬜" * empty


def create_exploration_bar(progress: float, length: int = 12) -> str:
    """탐험 진행도 바 생성 (플레이어 아이콘 포함)"""
    filled = int(progress * length)
    empty = length - filled - 1

    if progress >= 1.0:
        return "🚪" + "▓" * (length - 1) + "🏆"
    if filled == 0:
        return "🚪🧑" + "░" * (length - 1) + "🏁"
    return "🚪" + "▓" * filled + "🧑" + "░" * max(0, empty) + "🏁"


def create_progress_bar(progress: float, length: int = 10) -> str:
    """진행도 바 생성"""
    filled = int(progress * length)
    empty = length - filled
    return "█" * filled + "░" * empty


# =============================================================================
# 던전 임베드
# =============================================================================


def create_dungeon_embed(session, event_queue: deque[str]) -> Embed:
    """던전 임베드 생성"""
    import discord

    user_name = session.user.get_name()
    description = f"**{user_name}**의 탐험"
    if session.dungeon.description:
        description += f"\n*{session.dungeon.description}*"

    embed = discord.Embed(
        title=f"🏰 {session.dungeon.name}",
        description=description,
        color=EmbedColor.DUNGEON
    )

    # 진행도 바
    progress = min(session.exploration_step / session.max_steps, 1.0)
    progress_bar = create_exploration_bar(progress, 12)
    progress_pct = int(progress * 100)

    embed.add_field(
        name="🗺️ 탐험 진행도",
        value=f"{progress_bar}\n**{session.exploration_step}** / {session.max_steps} 구역 ({progress_pct}%)",
        inline=False
    )

    # 플레이어 상태
    user_stat = session.user.get_stat()
    max_hp = user_stat[UserStatEnum.HP]
    hp_bar = create_hp_bar(session.user.now_hp, max_hp, 8)
    hp_pct = int((session.user.now_hp / max_hp) * 100) if max_hp > 0 else 0

    embed.add_field(
        name=f"👤 {user_name}",
        value=f"{hp_bar}\nHP **{session.user.now_hp}** / {max_hp} ({hp_pct}%)",
        inline=True
    )

    # 획득 보상
    embed.add_field(
        name="💎 획득 보상",
        value=(
            f"⭐ 경험치: **{session.total_exp:,}**\n"
            f"💰 골드: **{session.total_gold:,}**\n"
            f"⚔️ 처치: **{session.monsters_defeated}**"
        ),
        inline=True
    )

    # 탐험 로그
    log_text = "\n".join(event_queue) if event_queue else "탐험을 시작합니다..."
    embed.add_field(name="📜 탐험 로그", value=log_text, inline=False)

    return embed


# =============================================================================
# 전투 임베드 (다중 몬스터)
# =============================================================================


def create_battle_embed_multi(
    player: User,
    context: CombatContext,
    combat_log: deque[str]
) -> Embed:
    """전투 임베드 생성 (다중 몬스터 지원)"""
    alive = context.get_all_alive_monsters()
    monster_names = " + ".join([m.name for m in alive]) if alive else "없음"

    embed = Embed(
        title=f"⚔️ {player.get_name()} vs {monster_names}",
        color=EmbedColor.COMBAT
    )

    # 파티 멤버 (현재 1인)
    _add_player_fields(embed, player)

    # 몬스터들 (살아있는 것만)
    for monster in context.get_all_alive_monsters():
        _add_monster_field(embed, monster)

    # 행동 순서 예측
    action_order = predict_action_order(player, context, max_count=4)
    if action_order:
        order_items = []
        for actor, round_num in action_order:
            icon = "👤" if isinstance(actor, User) else "👹"
            order_items.append(f"[R{round_num}]{icon}**{actor.get_name()}**")
        embed.add_field(name="⏭️ 다음 행동 순서", value=" → ".join(order_items), inline=False)

    # 전투 로그
    log_text = "\n".join(combat_log) if combat_log else "```전투 준비 중...```"
    embed.add_field(name="📜 전투 로그", value=log_text, inline=False)

    # Footer
    round_marker_pct = int((context.round_marker_gauge / COMBAT.ACTION_GAUGE_MAX) * 100)
    footer_text = f"🌟 라운드 {context.round_number} | 다음 라운드까지: {round_marker_pct}%"

    # 필드 효과 표시
    if context.field_effect:
        footer_text += f" | {context.field_effect.get_display_text()}"

    embed.set_footer(text=footer_text)

    return embed


def _add_player_fields(embed: Embed, player: User) -> None:
    """파티 멤버 필드 추가 (중앙 정렬)"""
    # 좌측 빈 필드 (중앙 정렬)
    embed.add_field(name="\u200b", value="\u200b", inline=True)

    member_stat = player.get_stat()
    max_hp = member_stat[UserStatEnum.HP]
    hp_bar = create_hp_bar(player.now_hp, max_hp, 10)
    hp_pct = int((player.now_hp / max_hp) * 100) if max_hp > 0 else 0
    status = get_status_icons(player)

    value = f"{hp_bar}\n**{player.now_hp}** / {max_hp} ({hp_pct}%)"
    if status:
        value += f"\n{status}"

    embed.add_field(name=f"👤 {player.get_name()}", value=value, inline=True)

    # 우측 빈 필드 (중앙 정렬)
    embed.add_field(name="\u200b", value="\u200b", inline=True)


def _add_monster_field(embed: Embed, monster: Monster) -> None:
    """몬스터 필드 추가"""
    hp_bar = create_hp_bar(monster.now_hp, monster.hp, 8)
    hp_pct = int((monster.now_hp / monster.hp) * 100) if monster.hp > 0 else 0
    status = get_status_icons(monster)
    death_mark = " 💀" if monster.now_hp <= 0 else ""

    value = f"{hp_bar}\n**{monster.now_hp}** / {monster.hp} ({hp_pct}%)"
    if status and monster.now_hp > 0:
        value += f"\n{status}"

    embed.add_field(
        name=f"👹 {monster.get_name()}{death_mark}",
        value=value,
        inline=True
    )


# =============================================================================
# 행동 순서 예측
# =============================================================================


def predict_action_order(
    player: User,
    context: CombatContext,
    max_count: int = 6
) -> list[tuple[Union[User, Monster], int]]:
    """현재 게이지 상태에서 다음 행동 순서 예측"""
    from models.users import User as UserClass

    gauges = context.action_gauges.copy()
    round_marker_gauge = context.round_marker_gauge
    current_round = context.round_number
    action_order = []

    for _ in range(1000):
        if len(action_order) >= max_count:
            break

        # 라운드 마커 체크
        if round_marker_gauge >= COMBAT.ACTION_GAUGE_MAX:
            current_round += 1
            round_marker_gauge = max(0, round_marker_gauge - COMBAT.ACTION_GAUGE_COST)

        # 행동 가능한 엔티티
        ready = _find_ready_entities(player, context, gauges)

        if ready:
            actor = _select_actor(ready, UserClass)
            action_order.append((actor, current_round))
            gauges[id(actor)] = max(0, gauges.get(id(actor), 0) - COMBAT.ACTION_GAUGE_COST)
        else:
            # 게이지 충전
            _fill_simulation_gauges(player, context, gauges)
            round_marker_gauge += int(10 * COMBAT.ACTION_GAUGE_SPEED_MULTIPLIER)

    return action_order


def _find_ready_entities(player, context, gauges) -> list[tuple]:
    """게이지 MAX 이상인 엔티티 찾기"""
    ready = []
    user_gauge = gauges.get(id(player), 0)
    if user_gauge >= COMBAT.ACTION_GAUGE_MAX and player.now_hp > 0:
        ready.append((player, user_gauge))

    for monster in context.get_all_alive_monsters():
        gauge = gauges.get(id(monster), 0)
        if gauge >= COMBAT.ACTION_GAUGE_MAX:
            ready.append((monster, gauge))
    return ready


def _select_actor(ready_entities, user_class):
    """가장 높은 게이지의 엔티티 선택 (유저 우선)"""
    max_gauge = max(g for _, g in ready_entities)
    max_entities = [e for e, g in ready_entities if g == max_gauge]
    user_entities = [e for e in max_entities if isinstance(e, user_class)]
    return user_entities[0] if user_entities else max_entities[0]


def _fill_simulation_gauges(player, context, gauges) -> None:
    """시뮬레이션용 게이지 충전"""
    user_speed = player.get_stat()[UserStatEnum.SPEED]
    gauges[id(player)] = gauges.get(id(player), 0) + int(user_speed * COMBAT.ACTION_GAUGE_SPEED_MULTIPLIER)

    for monster in context.get_all_alive_monsters():
        gauges[id(monster)] = gauges.get(id(monster), 0) + int(monster.speed * COMBAT.ACTION_GAUGE_SPEED_MULTIPLIER)
