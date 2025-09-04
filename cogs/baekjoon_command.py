import discord
from discord import app_commands
from discord.ext import commands

from DTO.solved_ac_profile_pagination import ProfilePagination
from bot import GUILD_ID
from decorator.account import requires_registration
from models import User
from models.repos import find_account_by_discordid
from service.user_service import get_profile_embed, get_solved_items, SolvedACError


class BaekjoonCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="백준계정등록",
        description="백준 계정을 등록합니다.")
    @app_commands.describe(username = "백준 아이디")
    @requires_registration()
    @app_commands.guilds(GUILD_ID)
    async def register_baekjoon(self, interaction: discord.Interaction,username : str):
        user : User = await find_account_by_discordid(interaction.user.id)
        user.baekjoon_id = username
        await user.save()
        await interaction.response.send_message(f"{username}으로 등록이 되었습니다", ephemeral = True)

    @app_commands.command(
        name="백준프로필보기",
        description="백준 프로필을 봅니다"
    )
    @app_commands.guilds(GUILD_ID)
    @app_commands.describe(username="백준 아이디 or 멘션 or 입력 X(자기 프로필)")
    async def baekjoon_profile(self,interaction: discord.Interaction,username : str = None):
        if not username:
            user = await find_account_by_discordid(interaction.user.id)
            baekjoon_id = user.baekjoon_id
        elif username.startswith("<@") and username.endswith(">"):
            user = await find_account_by_discordid(username.strip("<@!>"))
            baekjoon_id = user.baekjoon_id
        else:
            baekjoon_id = username

        try:
            profile_embed = await get_profile_embed(baekjoon_id,self.bot)
            solved_items = await get_solved_items(baekjoon_id)
            view = ProfilePagination(profile_embed, solved_items, self.bot,baekjoon_id)
            await interaction.response.send_message(embed=profile_embed, view=view)
        except SolvedACError as e:
            await interaction.response.send_message(f"❌ 오류: {e}", ephemeral = True)


async def setup(bot: commands.Bot):
    await bot.add_cog(BaekjoonCommands(bot))
