"""
관전자 UI Embed 생성

관전 시스템에서 사용하는 Discord Embed를 생성합니다.
"""
import discord

from config import EmbedColor
from service.dungeon.dungeon_ui import create_battle_embed_multi


def create_combat_notification_embed(session) -> discord.Embed:
    """
    서버 채널용 전투 알림 Embed 생성

    Args:
        session: DungeonSession

    Returns:
        Discord Embed
    """
    user_name = session.user.get_name() if session.user else "알 수 없음"
    dungeon_name = session.dungeon.name if session.dungeon else "알 수 없음"

    # 현재 전투 중인 몬스터 정보
    if session.combat_context and session.combat_context.monsters:
        monster_names = [m.name for m in session.combat_context.monsters if not m.is_dead()]
        if len(monster_names) > 1:
            monster_display = f"{monster_names[0]} 외 {len(monster_names) - 1}마리"
        elif monster_names:
            monster_display = monster_names[0]
        else:
            monster_display = "몬스터"
    else:
        monster_display = "몬스터"

    embed = discord.Embed(
        title=f"⚔️ 전투 발생!",
        description=(
            f"**{user_name}**님이 **{dungeon_name}**에서\n"
            f"**{monster_display}**와(과) 전투 중입니다!\n\n"
            f"👀 아래 버튼을 눌러 실시간으로 관전하세요!"
        ),
        color=EmbedColor.COMBAT_NOTIFICATION
    )

    embed.add_field(
        name="📍 위치",
        value=f"{dungeon_name} (진행도: {session.exploration_step}/{session.max_steps})",
        inline=False
    )

    # 관전자 수 표시
    spectator_count = len(session.spectators)
    if spectator_count > 0:
        embed.add_field(
            name="👀 관전자",
            value=f"{spectator_count}명 관전 중",
            inline=False
        )

    embed.set_footer(text="💡 관전은 전투가 끝나면 자동으로 종료됩니다")

    return embed


def create_spectator_combat_embed(player, context) -> discord.Embed:
    """
    관전자 DM용 전투 화면 Embed 생성

    기존 전투 embed를 재사용하되 관전 모드임을 표시합니다.

    Args:
        player: 전투 중인 유저 (User)
        context: CombatContext

    Returns:
        Discord Embed
    """
    # 실제 전투 로그 사용 (context.combat_log)
    embed = create_battle_embed_multi(player, context, context.combat_log)

    # 색상 변경 (관전 모드 표시)
    embed.color = EmbedColor.SPECTATOR

    # Footer 수정
    embed.set_footer(text="👀 관전 중 | 실시간 업데이트")

    return embed
