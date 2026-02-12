import discord
from discord import app_commands
from discord.ext import commands

from bot import GUILD_IDS
from decorator.account import requires_account
from models.repos.users_repo import find_account_by_discordid
from service.session import create_session, end_session
from service.skill.skill_deck_service import SkillDeckService
from service.skill.ultimate_service import load_ultimate_to_user
from service.item.equipment_service import EquipmentService
from service.player.healing_service import HealingService
from service.tower.tower_service import initialize_tower_session, run_tower
from service.tower.tower_season_service import get_current_season
from views.tower_view import TowerEntryView


class TowerCommand(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @requires_account()
    @app_commands.command(
        name="주간타워",
        description="주간 타워에 도전합니다"
    )
    @app_commands.guilds(*GUILD_IDS)
    async def weekly_tower(self, interaction: discord.Interaction):
        session = await create_session(interaction.user.id)
        if session is None:
            await interaction.response.send_message("이미 던전 탐험중입니다.", ephemeral=True)
            return

        user = await find_account_by_discordid(interaction.user.id)
        if not user:
            await interaction.response.send_message(
                "등록된 계정이 없습니다. `/등록`을 먼저 해주세요.",
                ephemeral=True
            )
            await end_session(interaction.user.id)
            return

        await HealingService.apply_natural_regen(user)
        await SkillDeckService.load_deck_to_user(user)
        await load_ultimate_to_user(user)
        await EquipmentService.apply_equipment_stats(user)

        try:
            progress = await initialize_tower_session(user, session)
        except RuntimeError as e:
            await interaction.response.send_message(
                f"⚠️ {e}",
                ephemeral=True
            )
            await end_session(interaction.user.id)
            return
        season_id = get_current_season()

        entry_view = TowerEntryView(interaction.user)
        embed = entry_view.create_embed(season_id, progress)
        await interaction.response.send_message(embed=embed, view=entry_view, ephemeral=True)
        await entry_view.wait()

        if entry_view.action != "enter":
            await end_session(interaction.user.id)
            return

        await interaction.followup.send("🗼 주간 타워를 시작합니다!", ephemeral=True)
        await run_tower(session, interaction)


async def setup(bot: commands.Bot):
    await bot.add_cog(TowerCommand(bot))
