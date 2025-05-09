import random
import discord
from discord.ext import commands
from discord import app_commands

from DTO.register_form import RegisterForm
from bot import GUILD_ID
from decorator.account import requires_registration
from models.repos import find_account_by_discordid, exists_account_by_discordid
from resources.itemdata import items, type_emoji, stat_emoji

user = app_commands.Group(
    name="user",
    description="유저 명령어",
    guild_ids=[GUILD_ID]
)

class ServerManageCommand(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="정보",
        description="아이템 정보 검색"
    )
    @app_commands.guilds(GUILD_ID)
    @app_commands.describe(item_name="검색할 아이템 이름")
    async def search_item(self, interaction: discord.Interaction, item_name: str):
        from resources.itemdata import items, type_emoji, stat_emoji

        item_data = items.get(item_name)

        if not item_data:
            await interaction.response.send_message(f"'{item_name}' 아이템을 찾을 수 없습니다.")
            return

        item_type = item_data.get('종류', '기타')
        type_icon = type_emoji.get(item_type, "📦")

        embed = discord.Embed(
            title=f"{item_data['이름']} {type_icon}",
            description=item_data['설명'],
            color=0x00ff00
        )

        image_path = f"resources/images/{item_name}.png"
        file = None

        try:
            file = discord.File(image_path, filename="image.png")
            embed.set_thumbnail(url="attachment://image.png")
        except FileNotFoundError:
            try:
                image_path = f"resources/images/{item_name}.jpg"
                file = discord.File(image_path, filename="image.jpg")
                embed.set_thumbnail(url="attachment://image.jpg")
            except FileNotFoundError:
                pass

        for key, value in item_data.items():
            if key not in ['이름', '설명', '종류']:
                emoji = stat_emoji.get(key, "📌")
                embed.add_field(name=f"{emoji} {key}", value=str(value), inline=True)

        if file:
            await interaction.response.send_message(file=file, embed=embed)
        else:
            await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="dice",
        description="주사위 굴리기",
    )
    @app_commands.guilds(GUILD_ID)
    async def roll_dice(self, interaction: discord.Interaction):
        n = random.randint(1, 6)
        await interaction.response.send_message(f"🎲 {n}")

    @app_commands.command(
        name="rsp",
        description="가위 바위 보"
    )
    @app_commands.guilds(GUILD_ID)
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

    @app_commands.command(
        name="register",
        description="회원가입하기"
    )
    @app_commands.guilds(GUILD_ID)
    async def register(self, interaction: discord.Interaction):
        if await exists_account_by_discordid(interaction.user.id):
            await interaction.response.send_message(f"{interaction.user.display_name}님은 이미 회원가입을 하셨습니다.")
            return
        await interaction.response.send_modal(RegisterForm())

async def setup(bot: commands.Bot):
    bot.tree.add_command(user)
    await bot.add_cog(ServerManageCommand(bot))