import random
import discord
from discord.ext import commands
from discord import app_commands

from bot import GUILD_IDS

user = app_commands.Group(
    name="user",
    description="유저 명령어",
    guild_ids=GUILD_IDS
)

class ServerManageCommand(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="dice",
        description="주사위 굴리기",
    )
    @app_commands.guilds(*GUILD_IDS)
    async def roll_dice(self, interaction: discord.Interaction):
        n = random.randint(1, 6)
        await interaction.response.send_message(f"🎲 {n}")

    @app_commands.command(
        name="rsp",
        description="가위 바위 보"
    )
    @app_commands.guilds(*GUILD_IDS)
    @app_commands.describe(choice_rsp="가위/바위/보 택 1")
    @app_commands.choices(choice_rsp = [
        app_commands.Choice(name = "가위",value="가위"),
        app_commands.Choice(name = "바위",value="바위"),
        app_commands.Choice(name = "보",value="보"),
    ])
    async def rsp(self, interaction: discord.Interaction, choice_rsp : str):
        bot_choice = random.choice(["가위","바위","보"])
        result = (
            "비겼습니다"
            if choice_rsp == bot_choice
            else ("이겼습니다" if (choice_rsp, bot_choice) in [("가위", "보"), ("바위", "가위"), ("보", "바위")] else "졌습니다")
        )
        await interaction.response.send_message(f"쿠하 봇의 선택은? : {bot_choice} \n"+result)

async def setup(bot: commands.Bot):
    bot.tree.add_command(user)
    await bot.add_cog(ServerManageCommand(bot))
