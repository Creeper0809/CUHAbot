import discord
import random
from discord.ext import commands

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix = '/', intents = intents)

user_game_history = {}

def create_card(self):
    special_card = ['♠', '♥', '♦', '♣']
    cards = ['A', '2', '3', '4', '5', '6', '7',
            '8', '9', '10', 'J', 'Q', 'K']
    return[f"{cards}{special_card}"]

    