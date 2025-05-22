import discord
import random
from discord.ext import commands
from discord.ui import Button, View

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix = '/', intents = intents)

user_game_history = {}

def create_card():
    suits = ['♠', '♥', '♦', '♣']
    ranks = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']
    return [f"{rank}{suit}" for suit in suits for rank in ranks]

def card_value(card):
    rank = card[:-1]
    if card in ['J', 'Q', 'K']:
        return 10
    elif card == 'A':
        return 11
    else:
        return int(rank)

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

class BlackJackGame(View):
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

    @discord.ui.button(label = "히트", style = discord.ButtonStyle.green, emoji="🔥")
    async def hit(self, interaction: discord.Interaction):
        if interaction.user != self.ctx.author:
            await interaction.response.send_message("다른 사람의 차례입니다.", ephemeral = True)
            return
        self.card += 1
        self.my_hand[0] += self.sum_list[self.card + 4]
        self.my_hand[1] += f" | {self.selected[self.card + 4]}"
        await self.hand_update()
        await interaction.response.defer()

    @discord.ui.button(label="스탠드", style=discord.ButtonStyle.success, emoji="✅")
    async def stand(self, interaction: discord.Interaction):
        if interaction.user != self.ctx.author:
            await interaction.response.send_message("당신의 차례가 아닙니다!", ephemeral=True)
            return
        await interaction.response.defer()
        self.stop()

    @discord.ui.button(label="더블다운", style=discord.ButtonStyle.danger, emoji="🌟")
    async def double_down(self, interaction: discord.Interaction):
        if interaction.user != self.ctx.author:
            await interaction.response.send_message("당신의 차례가 아닙니다!", ephemeral=True)
            return
        self.card += 1
        self.my_hand[0] += self.sum_list[self.card + 4]
        self.my_hand[1] += f" | {self.selected[self.card + 4]}"
        await self.update_hand()
        self.stop()
        await interaction.response.defer()
