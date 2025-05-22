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
