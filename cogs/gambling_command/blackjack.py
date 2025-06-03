from csv import excel

import discord
import random
import asyncio
from discord.ext import commands
from discord.ui import Button, button, View

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='/', intents=intents)

user_game_history = {}

def create_card():
    suits = ['♠', '♥', '♦', '♣']
    ranks = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']
    deck =  [f"{rank}{suit}" for suit in suits for rank in ranks]
    random.shuffle(deck)
    return deck

def card_value(card):
    rank = card[:-1]
    if card in ['J', 'Q', 'K']:
        return 10
    elif card == 'A':
        return 11
    else:
        try:
            return int(rank)
        except ValueError:
            print("오류")
            return 0


class BlackJackGame(View):
    def __init__(self, ctx, pre_selected_cards):
        super().__init__
        self.ctx = ctx
        self.author_id = ctx.author.id

        self.all_cards_in_play_str = pre_selected_cards
        self.all_cards_in_play_val = [card_value(card) for card in pre_selected_cards]

        self.player_cards_drawn_count = 0  # 플레이어가 "히트"로 가져간 카드 수
        self.player_aces_as_one = 0  # 플레이어의 에이스 중 현재 1로 계산되는 수

        self.dealer_aces_as_one = 0  # 딜러의 에이스 중 현재 1로 계산되는 수

        # 초기 패 분배
        self.player_hand_str = [self.all_cards_in_play_str[0], self.all_cards_in_play_str[2]]
        self.player_score = card_value(self.player_hand_str[0]) + card_value(self.player_hand_str[1])

        self.dealer_hand_str = [self.all_cards_in_play_str[1], self.all_cards_in_play_str[3]]
        self.dealer_score = card_value(self.dealer_hand_str[0]) + card_value(self.dealer_hand_str[1])

        self.message = None  # 이 뷰가 첨부된 메시지를 저장할 변수
        self.game_over = False

        self._adjust_score_for_aces('player')
        self._adjust_score_for_aces('dealer')


@bot.command()
async def blackjack(ctx):
    deck = create_card()
    random.shuffle(deck)
    pick = random.sample(range(0, 52), 20)
    selected = [deck[i] for i in pick]
    sum_list = [card_value(card) for card in selected]

    game_view = BlackJackGame(ctx, deck, sum_list, selected)
    user_game_history[ctx.author.id] = game_view
    await game_view.send_embed()

    async def send_embed(self):
        embed = discord.Embed(title = "Blackjack", color = 0x00ff00)
        embed.add_field(name = f"{self.ctx.author.name}의 패", value = f"{self.my_hand[1]}\n 합계: {self.my_hand[0]}", inline = False)
        embed.add_field(name = "총 합", value = f"{self.sum_list[0]} | {self.sum_list[2]}\n{self.sum_list[1]} | {self.sum_list[3]}", inline = False)
        embed.add_field(name = "딜러의 패", value = f"{self.selected[1]} | ❔", inline = False)
        embed.add_field(name = f"{self.ctx.author.name}의 차례입니다.", value = "버튼을 눌러주세요.", inline = False)

        if self.message:
            await self.message.edit(embed = embed, view = self)
        else:
            self.message = await self.ctx.send(embed = embed, view = self)

    async def hand_update(self):
        if self.my_hand[0] == 21 and self.card:
            self.my_hand[0] = "블랙잭"
            await self.send_embed()
            self.stop()
        elif isinstance(self.my_hand[0], int) and self.my_hand[0] >= 22:
            if self.my_hand[1].count("A") - self.use_ace >= 1:
                self.my_hand[0] -= 10
                self.use_ace += 1
                await self.send_embed()
            else:
                self.my_hand[0] = "버스트"
                await self.send_embed()
                self.stop()
        else:
            await self.send_embed()
