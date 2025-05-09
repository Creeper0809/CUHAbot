import discord
from discord import app_commands
from discord.ext import commands

import models.repos.static_cache
from DTO.dungeon_select_view import DungeonSelectView
from bot import GUILD_ID
from decorator.account import requires_registration
from models.repos import find_account_by_discordid
from models.repos.dungeon_repo import find_all_dungeon, find_all_dungeon_spawn_monster_by
from models.repos.static_cache import dungeon_cache
from service.dungeon_service import start_dungeon
from service.session import is_in_session, create_session, end_session
from models import User


class DungeonCommand(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @requires_registration()
    @app_commands.command(
        name="던전입장",
        description="던전에 입장합니다"
    )
    @app_commands.guilds(GUILD_ID)
    async def enter_dungeon(self, interaction: discord.Interaction):
        if is_in_session(interaction.user.id):
            await interaction.response.send_message("이미 던전 탐험중입니다.")
        session = create_session(interaction.user.id)

        user: User = await find_account_by_discordid(session.user_id)
        session.user = user

        dungeons = find_all_dungeon()
        if not dungeons:
            await interaction.response.send_message("등록된 던전이 없습니다.")
            return
        embed = discord.Embed(
            title="🎯 던전을 선택하세요",
            description="드롭다운에서 던전을 선택한 후 입장하거나 취소하세요.",
            color=discord.Color.blurple()
        )
        view = DungeonSelectView(interaction.user, dungeons, session)
        message = await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()
        await view.wait()
        if view.selected_dungeon is None:
            await interaction.followup.send("던전 입장이 취소되었습니다.")
            return
        await interaction.followup.send(f"{view.selected_dungeon.name} 던전에 입장합니다!")

        session.dungeon = view.selected_dungeon

        ended = await start_dungeon(session, interaction)

        await interaction.followup.send(f"던전에서 탈출했습니다")
        await end_session(user_id=interaction.user.id)


async def setup(bot: commands.Bot):
    await bot.add_cog(DungeonCommand(bot))
