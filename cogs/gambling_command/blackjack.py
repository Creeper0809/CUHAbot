import discord
import random
from discord.ext import commands

intents = discord.Intents.default()
bot = commands.Bot(command_prefix = '/', intents = intents)

user_game_history = {}

class BlackJack:
    def __init__(self):
        self.card = self.create_card()
        random.shuffle(self.card)
        self.player_hand = []
        self.dealer_hand = []
        self.player_score = 0
        self.dealer_score = 0
        self.player_status = "playing"
        self.dealer_status = "playing"

    def create_card(self):
        special_card = ['♠', '♥', '♦', '♣']
        cards = ['A', '2', '3', '4', '5', '6', '7',
                 '8', '9', '10', 'J', 'Q', 'K']
        return[f"{cards}{special_card}"]

    def deal_card(self, target):
        card = self.card.pop()
        if target == "player":
            self.player_hand.append(card)
        elif target == 'dealer':
            self.dealer_hand.append(card)
        else:
            raise ValueError("'player' 혹은 'dealer'가 대상이어야 합니다.")

    def score_cal(self, hand):
        score = 0
        aces = 0
        for card in hand:
            if card in hand:
                cards = card[:-1]
                if cards in ['J', 'Q', 'K']:
                    score += 10
                elif cards == 'A':
                    aces += 1
                else:
                    score += int(cards)
@bot.command(name="블랙잭")
async def blackjack(ctx):
    blackjack = BlackJack()
    user_game_history[ctx.author.id] = blackjack

    await ctx.send("🃏2장의 카드를 뽑습니다.🃏")

    for _ in range(2):
        blackjack.deal_card('player')
        blackjack.deal_card('dealer')

    player_score = blackjack.score_cal(blackjack.player_hand)
    await ctx.send(f"🃏당신의 카드: {', '.join(blackjack.player_hand)} (총합: {player_score})\n"
                   f"🃏딜러의 카드: {', '.join(blackjack.dealer_hand)} (총합: ??)\n"
                   f"🃏/hit, /stand으로 카드 추가, /stand으로 중단할 수 있습니다.")

@bot.command(name="hit")
async def hit(ctx):
    if ctx.author.id not in user_game_history:
        await ctx.send("먼저 블랙잭을 시작하세요.")
        return

    blackjack = user_game_history[ctx.author.id]
    blackjack.deal_card('player')
    score = blackjack.score_cal(blackjack.player_hand)
    await ctx.send(f"카드가 추가 지급되었습니다. {', '.join(blackjack.player_hand)} (총합: {score}")

    