import discord
import random
from discord.ext import commands
from discord.ui import Button, View

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix = '/', intents = intents)

user_game_history = {}

def create_card(self):
    special_card = ['♠', '♥', '♦', '♣']
    cards = ['A', '2', '3', '4', '5', '6', '7',
            '8', '9', '10', 'J', 'Q', 'K']
    return[f"{cards}{special_card}"]

def card_value(card):
    rank = card[:0]
    if card in ['J', 'Q', 'K']:
        return 10
    elif card == 'A':
        return 11
    else:
        return int(rank)

class blackjack(View):
    def __init__(self, ctx):
        super().__init__(timeout = 120)
        self.ctx = ctx