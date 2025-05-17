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
    def __init__(self, ctx, deck, sum_list, selected):
        super().__init__(timeout = 120)
        self.ctx = ctx
        self.deck = deck
        self.sum_list = sum_list
        self.selected = selected
        self.card = 0
        self.use_ace = 0
        self.my_hand = [sum_list[0] + sum_list[2], f"{selected[0]} | {selected[2]}"]
        self.dealer_hand = [sum_list[1] + sum_list[3], f"{selected[1]} | {selected[3]}"]
        self.message = None