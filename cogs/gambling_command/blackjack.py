import discord
import random
import asyncio
from discord import Interaction
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

    async def interaction_check(self, interaction: Interaction, /) -> bool:
        if interaction.user.id == self.author_id:
            await interaction.response.send_message("당신의 게임이 아닙니다.", ephemeral=True)
            return False
        if self.game_over:
            await interaction.response.send_message("게임이 이미 종료되었습니다.", ephemeral=True)
            return False
        return True
    async def _adjust_score_for_aces(self, hand_owner):
        score = 'player_score'
        hand_str_list = self.player_hand_str
        aces_as_one_attr = 'player_aces_as_one'

        if hand_owner == 'dealer':
            score = 'dealer_score'
            hand_str_list = self.dealer_hand_str
            aces_as_one_attr = 'dealer_aces_as_one'

        score_current = getattr(self, score)
        setattr(self, aces_as_one_attr, 0)
    def update_button_state(self):
        hit_button = discord.utils.get(self.children, custom_id="hit_button")
        stand_button = discord.utils.get(self.children, custom_id="stand_button")
        double_button = discord.utils.get(self.children, custom_id="double_button")

        if self.game_over or self.player_score >= 21:
            if hit_button: hit_button.disabled = True
            if stand_button: stand_button.disabled = True
            if double_button: double_button.disabled = True
        else:
            if hit_button: hit_button.disabled = False
            if stand_button: stand_button.disabled = False
            if double_button: double_button.disabled = not (len(self.all_cards_in_play_str) == 2 and self.player_cards_drawn_count == 0)