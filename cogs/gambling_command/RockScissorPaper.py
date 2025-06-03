import discord
import random
from discord.ext import commands
from discord.ui import Button, View

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="/", intents=intents)

def result(user, bot):
    if user == bot:
        return "무승부"
    elif (user == "가위" and bot == "보") or \
         (user == "바위" and bot == "가위") or \
         (user == "보" and bot == "바위"):
        return "승리"
    else:
        return "패배"

class ButtonView(View):
    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx

    @discord.ui.button(label="가위", style=discord.ButtonStyle.green, emoji="✌️")
    async def scissors(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(interaction.user.mention, ephemeral=True)

    @discord.ui.button(label="바위", style=discord.ButtonStyle.blurple, emoji="✊")
    async def rock(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_result(interaction, "바위")

    @discord.ui.button(label="보", style=discord.ButtonStyle.red, emoji="🖐️")
    async def paper(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_result(interaction, "보")

    async def process_result(self, interaction: discord.Interaction, user_choice):
        bot_choice = random.choice(["가위", "바위", "보"])
        result_text = result(user_choice, bot_choice)

        embed = discord.Embed(title="가위바위보", color=0x00ff00)
        embed.add_field(name=f"당신의 선택", value=f"{user_choice}", inline=False)
        embed.add_field(name="총 합", value=f"{bot}", inline=False)
        embed.add_field(name=f"{self.ctx.author.name}의 결과", value=f"{result_text}", inline=False)
        await interaction.response.edit_message(embed=embed, view=self)