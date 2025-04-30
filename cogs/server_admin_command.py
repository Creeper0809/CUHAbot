import discord
from discord.ext import commands
from discord import app_commands

from bot import GUILD_ID

admin = app_commands.Group(
    name="admin",
    description="관리자 전용 명령어",
    guild_ids=[GUILD_ID]
)

class ServerAdminCammand(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="clear",
        description="채널에서 최근 메시지 n개를 삭제합니다."
    )
    @app_commands.describe(amount="삭제할 메시지 수 (1~100)")
    @commands.has_permissions(administrator=True)
    async def clear(self, interaction: discord.Interaction, amount: int):

        if not interaction.channel.permissions_for(interaction.user).manage_messages:
            await interaction.response.send_message("메시지 관리 권한이 필요합니다.", ephemeral=True)
            return

        if not interaction.channel.permissions_for(interaction.guild.me).manage_messages:
            await interaction.response.send_message("봇에 메시지 관리 권한이 없습니다.", ephemeral=True)
            return

        if amount < 1 or amount > 100:
            await interaction.response.send_message("1부터 100 사이의 수를 입력해주세요.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        try:
            deleted = await interaction.channel.purge(limit=amount)
            await interaction.followup.send(f"{len(deleted)}개의 메시지를 삭제했습니다.", ephemeral=True)
        except discord.HTTPException as e:
            await interaction.followup.send(f"메시지 삭제 실패: {e}", ephemeral=True)

    @app_commands.command(
        name="reloadtree",
        description="이 서버의 슬래시 커맨드를 전부 삭제한 뒤, 코드 기준으로 재등록합니다."
    )
    @app_commands.guilds(GUILD_ID)
    @commands.has_permissions(administrator=True)
    async def reload_tree(self, interaction: discord.Interaction):

        self.bot.tree.clear_commands(guild=discord.Object(id=GUILD_ID))

        synced = await self.bot.tree.sync(guild=discord.Object(id=GUILD_ID))

        await interaction.response.send_message(
            f"{len(synced)}개의 슬래시 커맨드를 재등록했습니다:\n`{', '.join(c.name for c in synced)}`",
            ephemeral=True
        )
    @app_commands.command(
        name="checkdatabase",
        description="데베 연결 확인"
    )
    @commands.has_permissions(administrator=True)
    @app_commands.guilds(GUILD_ID)
    async def check_database(self,interaction: discord.Interaction):
        from db.models.account import User
        users = await User.all()
        await interaction.response.send_message(f"{len(users)}명이 데이터베이스에 존재합니다.")
async def setup(bot: commands.Bot):
    await bot.add_cog(ServerAdminCammand(bot))