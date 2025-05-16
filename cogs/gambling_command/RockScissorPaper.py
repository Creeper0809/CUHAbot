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
    def __init__(self):
        super().__init__()
        self.add_item(Button(label="가위", style=discord.ButtonStyle.green))
        self.add_item(Button(label="바위", style=discord.ButtonStyle.blurple))
        self.add_item(Button(label="보", style=discord.ButtonStyle.red))

@bot.event
async def on_ready():
    print("봇 준비 완료")

@bot.tree.command(name="가위바위보")
async def rsp(interaction: discord.Interaction, user_choice: str):
    await interaction.response.send_message("가위, 바위, 보 중 하나를 선택해주세요.", view=ButtonView())

@bot.event
async def on_button_click(interaction: discord.Interaction, get_result=None):
    if interaction.type == discord.InteractionType.component:
        user_choice_list = { "Rock: 가위", "Paper: 바위", "Scissor: 보" }

        user_choice = user_choice_list.get(interaction.data["custom_id"].split(": "))
        bot_choice = random.choice(["가위", "바위", "보"])
        result = get_result(user_choice, bot_choice)

    await interaction.response.send_message(f'당신의 선택: {user_choice}\n'
                                            f'쿠하 봇의 선택: {bot_choice}\n'
                                            f'결과: {result}')
