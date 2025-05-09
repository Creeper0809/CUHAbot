import discord
import random
from discord.ext import commands

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="/", intents=intents)

@bot.event
async def on_ready():
    print("봇 준비 완료")

@bot.tree.command(name="가위바위보")
async def rsp(interaction: discord.Interaction, user_choice: str):
    choices = ["가위", "바위", "보"]
    bot_choice = random.choice(choices)

    if user_choice == bot_choice:
        result = "무승부"
    elif (user_choice == "가위" and bot_choice == "보") or (user_choice == "바위" and bot_choice == "가위") or (
        user_choice == "보" and bot_choice == "바위"):
        result = "승리"
    else:
        result = "패배"

    await interaction.response.send_message(f'당신의 선택: {user_choice}\n'
                                            f'쿠하 봇의 선택: {bot_choice}\n'
                                            f'결과: {result}')