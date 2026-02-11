"""
경매 커맨드

경매장 UI를 제공합니다.
"""
import discord
from discord import app_commands
from discord.ext import commands

from bot import GUILD_IDS
from decorator.account import requires_account
from exceptions import CombatRestrictionError
from models.users import User
from service.session import get_session
from views.auction.main_view import AuctionMainView


class AuctionCommand(commands.Cog):
    """경매 커맨드"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="경매", description="🏛️ 경매장 열기")
    @app_commands.guilds(*GUILD_IDS)
    @requires_account()
    async def auction(self, interaction: discord.Interaction):
        """경매장 메인 UI 표시"""
        # 전투 중 체크
        session = get_session(interaction.user.id)
        if session and session.in_combat:
            await interaction.response.send_message(
                "⚠️ 전투 중에는 경매장을 이용할 수 없습니다.",
                ephemeral=True
            )
            return

        # DB 유저 가져오기
        user = await User.get(discord_id=interaction.user.id)

        # View 생성 및 초기화
        view = AuctionMainView(
            user=interaction.user,
            db_user=user
        )

        await view.initialize()

        # Embed 생성
        embed = view.create_embed()

        # 메시지 전송
        await interaction.response.send_message(
            embed=embed,
            view=view
        )

        view.message = await interaction.original_response()


async def setup(bot: commands.Bot):
    await bot.add_cog(AuctionCommand(bot))
