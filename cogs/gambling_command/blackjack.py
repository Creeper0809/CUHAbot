import discord
import random
from discord.ext import commands
from discord.ui import View, Button, button
import asyncio

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='/', intents=intents)

user_game_history = {}


def create_card_deck():
    suits = ['♠', '♥', '♦', '♣']
    ranks = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']
    deck = [f"{rank}{suit}" for suit in suits for rank in ranks]
    random.shuffle(deck)
    return deck


def card_value(card_str):
    """카드 문자열(예: 'K♠', 'A♥')의 블랙잭 값을 결정합니다."""
    rank = card_str[:-1]
    if rank in ['J', 'Q', 'K']:
        return 10
    elif rank == 'A':
        return 11
    else:
        try:
            return int(rank)
        except ValueError:
            print(f"오류: 카드 '{card_str}'에서 랭크 '{rank}'를 파싱할 수 없습니다.")
            return 0

class BlackJackGame(View):
    def __init__(self, ctx, pre_selected_cards):
        super().__init__(timeout=180.0)
        self.ctx = ctx
        self.author_id = ctx.author.id

        self.all_cards_in_play_str = pre_selected_cards
        self.all_cards_in_play_val = [card_value(card) for card in pre_selected_cards]

        self.player_cards_drawn_count = 0
        self.player_aces_as_one = 0

        self.dealer_aces_as_one = 0

        # 초기 패 분배
        self.player_hand_str = [self.all_cards_in_play_str[0], self.all_cards_in_play_str[2]]
        self.player_score = card_value(self.player_hand_str[0]) + card_value(self.player_hand_str[1])

        self.dealer_hand_str = [self.all_cards_in_play_str[1], self.all_cards_in_play_str[3]]
        self.dealer_score = card_value(self.dealer_hand_str[0]) + card_value(self.dealer_hand_str[1])

        self.message = None
        self.game_over = False

        self._adjust_score_for_aces('player')
        self._adjust_score_for_aces('dealer')

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("이것은 당신의 게임이 아닙니다!", ephemeral=True)
            return False
        if self.game_over:
            await interaction.response.send_message("게임이 이미 종료되었습니다.", ephemeral=True)
            return False
        return True

    def _adjust_score_for_aces(self, hand_owner):
        score_attr = 'player_score'
        hand_str_list = self.player_hand_str
        aces_as_one_attr = 'player_aces_as_one'

        if hand_owner == 'dealer':
            score_attr = 'dealer_score'
            hand_str_list = self.dealer_hand_str
            aces_as_one_attr = 'dealer_aces_as_one'

        current_score = getattr(self, score_attr)
        setattr(self, aces_as_one_attr, 0)
        current_score = sum(card_value(c) for c in hand_str_list)

        aces_in_hand = sum(1 for card in hand_str_list if card.startswith('A'))
        temp_aces_counted_as_one = 0

        while current_score > 21 and temp_aces_counted_as_one < aces_in_hand:
            current_score -= 10
            temp_aces_counted_as_one += 1

        setattr(self, score_attr, current_score)
        setattr(self, aces_as_one_attr, temp_aces_counted_as_one)

    def _get_embed(self, status_message="", dealer_full_reveal=False, game_end_title=None):
        embed_title = game_end_title if game_end_title else " 블랙잭 "
        embed_color = discord.Color.dark_grey() if self.game_over else discord.Color.green()
        embed = discord.Embed(title=embed_title, color=embed_color)

        self._adjust_score_for_aces('player')
        self._adjust_score_for_aces('dealer')

        player_score_display = str(self.player_score)
        if self.player_score > 21:
            player_score_display = f"버스트! ({self.player_score})"
        elif self.player_score == 21 and len(self.player_hand_str) == 2 and self.player_cards_drawn_count == 0:
            player_score_display = "블랙잭!"
        elif self.player_score == 21:
            player_score_display = "21!"

        embed.add_field(name=f"{self.ctx.author.display_name}의 패 ({player_score_display})",
                        value=f"`{' | '.join(self.player_hand_str)}`",
                        inline=False)

        dealer_score_val_display = str(self.dealer_score)
        dealer_hand_cards_display = f"`{self.dealer_hand_str[0]} | ❔`"

        if dealer_full_reveal:
            dealer_hand_cards_display = f"`{' | '.join(self.dealer_hand_str)}`"
            if self.dealer_score > 21:
                dealer_score_val_display = f"버스트! ({self.dealer_score})"
            elif self.dealer_score == 21 and len(self.dealer_hand_str) == 2:
                dealer_score_val_display = "블랙잭!"
            elif self.dealer_score == 21:
                dealer_score_val_display = "21!"

        embed.add_field(name=f"딜러의 패 ({dealer_score_val_display if dealer_full_reveal else '?'})",
                        value=dealer_hand_cards_display,
                        inline=False)

        if status_message:
            embed.add_field(name="게임 상태", value=status_message, inline=False)
        elif self.game_over:
            pass
        elif not any(not child.disabled for child in self.children if
                     isinstance(child, Button)):  # 모든 버튼이 비활성화 되었다면 (플레이어 턴 종료)
            embed.add_field(name="딜러의 차례", value="딜러가 플레이합니다...", inline=False)
        else:
            embed.add_field(name="당신의 차례", value="버튼을 눌러주세요.", inline=False)
        return embed

    def _update_button_states(self):
        hit_btn = discord.utils.get(self.children, custom_id="blackjack_hit")
        stand_btn = discord.utils.get(self.children, custom_id="blackjack_stand")
        double_btn = discord.utils.get(self.children, custom_id="blackjack_double")

        if self.game_over or self.player_score >= 21:
            if hit_btn: hit_btn.disabled = True
            if stand_btn: stand_btn.disabled = True
            if double_btn: double_btn.disabled = True
        else:
            if hit_btn: hit_btn.disabled = False
            if stand_btn: stand_btn.disabled = False
            if double_btn:
                double_btn.disabled = not (len(self.player_hand_str) == 2 and self.player_cards_drawn_count == 0)

    async def send_initial_message(self):
        is_player_blackjack = self.player_score == 21 and len(self.player_hand_str) == 2

        status = ""
        if is_player_blackjack:
            status = "플레이어 블랙잭! 딜러의 패를 확인합니다..."

        self._update_button_states()  # 초기 버튼 상태 설정
        embed = self._get_embed(status_message=status)
        self.message = await self.ctx.send(embed=embed, view=self)

        if is_player_blackjack:
            self._disable_all_buttons()  # 플레이어 턴 즉시 종료
            await self.message.edit(view=self)  # 변경된 버튼 상태 반영
            await asyncio.sleep(1)
            await self._dealer_turn_and_resolve()

    def _get_next_card_deal_index(self, num_dealer_cards_this_turn=0):
        return 4 + self.player_cards_drawn_count + num_dealer_cards_this_turn

    def _disable_all_buttons(self):
        for child in self.children:
            if isinstance(child, Button):
                child.disabled = True

    def _end_game_cleanup(self):
        if self.game_over:  # 중복 호출 방지
            return
        self.game_over = True
        self._disable_all_buttons()
        self.stop()
        if self.author_id in user_game_history:
            del user_game_history[self.author_id]

    async def _dealer_turn_and_resolve(self, player_doubled_down=False):
        if self.game_over: return  # 이미 게임이 다른 이유로 종료된 경우 중단

        self._disable_all_buttons()
        await self.message.edit(embed=self._get_embed(status_message="딜러의 차례...", dealer_full_reveal=True), view=self)
        await asyncio.sleep(1)

        dealer_cards_drawn_this_turn = 0
        while self.dealer_score < 17:
            card_draw_index = self._get_next_card_deal_index(dealer_cards_drawn_this_turn)
            if card_draw_index >= len(self.all_cards_in_play_str):
                await self.message.edit(
                    embed=self._get_embed(status_message="딜러가 카드 부족으로 더 이상 뽑을 수 없습니다.", dealer_full_reveal=True),
                    view=self)
                break

            new_card_str = self.all_cards_in_play_str[card_draw_index]
            self.dealer_hand_str.append(new_card_str)
            self.dealer_score += card_value(new_card_str)  # 직접 값 추가
            dealer_cards_drawn_this_turn += 1
            self._adjust_score_for_aces('dealer')

            await self.message.edit(
                embed=self._get_embed(status_message=f"딜러가 히트하여 `{new_card_str}`를 받았습니다...", dealer_full_reveal=True),
                view=self)
            await asyncio.sleep(1.5)

        if self.dealer_score >= 17 and not self.game_over:
            await self.message.edit(embed=self._get_embed(status_message="딜러가 스탠드합니다.", dealer_full_reveal=True),
                                    view=self)
            await asyncio.sleep(1)

        player_final_score = self.player_score
        dealer_final_score = self.dealer_score
        is_player_busted = player_final_score > 21
        is_dealer_busted = dealer_final_score > 21
        player_has_blackjack = player_final_score == 21 and len(
            self.player_hand_str) == 2 and self.player_cards_drawn_count == 0 and not player_doubled_down
        dealer_has_blackjack = dealer_final_score == 21 and len(self.dealer_hand_str) == 2 and sum(
            1 for _ in range(dealer_cards_drawn_this_turn)) == 0

        winner_message = ""
        game_end_title = "게임 종료"

        if is_player_busted:
            winner_message = f"당신은 {player_final_score}점으로 버스트했습니다! 딜러 승리!"
            game_end_title += " - 당신의 버스트!"
        elif player_has_blackjack and dealer_has_blackjack:
            winner_message = "푸시! 둘 다 블랙잭입니다."
            game_end_title += " - 푸시!"
        elif player_has_blackjack:
            winner_message = "블랙잭! 당신의 승리입니다! 🎉"
            game_end_title += " - 당신의 승리 (블랙잭)!"
        elif dealer_has_blackjack:
            winner_message = "딜러 블랙잭! 딜러 승리!"
            game_end_title += " - 딜러 승리 (블랙잭)!"
        elif is_dealer_busted:
            winner_message = f"딜러가 {dealer_final_score}점으로 버스트했습니다! 당신의 승리입니다! 🎉"
            game_end_title += " - 당신의 승리!"
        elif dealer_final_score == player_final_score:
            winner_message = f"푸시! 둘 다 {player_final_score}점입니다."
            game_end_title += " - 푸시!"
        elif dealer_final_score > player_final_score:
            winner_message = f"딜러가 {dealer_final_score}점으로 당신의 {player_final_score}점을 이겼습니다. 딜러 승리!"
            game_end_title += " - 딜러 승리!"
        else:
            winner_message = f"당신이 {player_final_score}점으로 딜러의 {dealer_final_score}점을 이겼습니다! 당신의 승리입니다! 🎉"
            game_end_title += " - 당신의 승리!"

        self._end_game_cleanup()
        await self.message.edit(embed=self._get_embed(status_message=winner_message, dealer_full_reveal=True,
                                                      game_end_title=game_end_title), view=self)

    @button(label="히트", style=discord.ButtonStyle.green, emoji="🔥", custom_id="blackjack_hit")
    async def hit_button_ui(self, interaction: discord.Interaction, button_obj: Button):
        await interaction.response.defer()

        card_draw_index = self._get_next_card_deal_index()
        if card_draw_index >= len(self.all_cards_in_play_str):
            self._end_game_cleanup()
            await interaction.message.edit(embed=self._get_embed(status_message="오류: 게임을 위한 카드가 부족합니다."), view=self)
            return

        new_card_str = self.all_cards_in_play_str[card_draw_index]
        self.player_hand_str.append(new_card_str)
        self.player_cards_drawn_count += 1
        self._adjust_score_for_aces('player')

        self._update_button_states()

        if self.player_score > 21:
            status = f"당신은 `{new_card_str}`를 받고 {self.player_score}점으로 버스트했습니다! 딜러 승리!"
            self._end_game_cleanup()
            await interaction.message.edit(embed=self._get_embed(status_message=status, dealer_full_reveal=True,
                                                                 game_end_title="게임 종료 - 당신의 버스트!"), view=self)
        elif self.player_score == 21:
            status = f"당신은 `{new_card_str}`를 받고 21점이 되었습니다! 딜러의 차례."
            # _update_button_states가 버튼 비활성화 처리
            await interaction.message.edit(embed=self._get_embed(status_message=status), view=self)
            await asyncio.sleep(1)
            await self._dealer_turn_and_resolve()
        else:
            status = f"당신은 `{new_card_str}`를 받았습니다. 다음 행동은?"
            await interaction.message.edit(embed=self._get_embed(status_message=status), view=self)

    @button(label="스탠드", style=discord.ButtonStyle.primary, emoji="✅", custom_id="blackjack_stand")
    async def stand_button_ui(self, interaction: discord.Interaction, button_obj: Button):
        await interaction.response.defer()
        self._disable_all_buttons()  # 스탠드 시 모든 버튼 비활성화
        await interaction.message.edit(embed=self._get_embed(status_message="당신은 스탠드했습니다. 딜러의 차례."), view=self)
        await asyncio.sleep(1)
        await self._dealer_turn_and_resolve()

    @button(label="더블다운", style=discord.ButtonStyle.danger, emoji="🌟", custom_id="blackjack_double")
    async def double_down_button_ui(self, interaction: discord.Interaction, button_obj: Button):
        await interaction.response.defer()

        self._disable_all_buttons()

        card_draw_index = self._get_next_card_deal_index()
        if card_draw_index >= len(self.all_cards_in_play_str):
            self._end_game_cleanup()
            await interaction.message.edit(embed=self._get_embed(status_message="오류: 더블다운을 위한 카드가 부족합니다."), view=self)
            return

        new_card_str = self.all_cards_in_play_str[card_draw_index]
        self.player_hand_str.append(new_card_str)
        self._adjust_score_for_aces('player')

        status = f"더블다운하여 `{new_card_str}`를 받았습니다. 당신의 점수: {self.player_score}."
        await interaction.message.edit(embed=self._get_embed(status_message=status), view=self)
        await asyncio.sleep(1.5)

        if self.player_score > 21:
            status = f"더블다운 후 {self.player_score}점으로 버스트했습니다! 딜러 승리!"
            self._end_game_cleanup()
            await interaction.message.edit(embed=self._get_embed(status_message=status, dealer_full_reveal=True,
                                                                 game_end_title="게임 종료 - 더블다운 버스트!"), view=self)
        else:
            await self._dealer_turn_and_resolve(player_doubled_down=True)

@bot.event
async def on_ready():
    print(f'{bot.user.name} 온라인!')

@bot.tree.command(name='블랙잭')
async def blackjack_command_ui(ctx: commands.Context):
    if ctx.author.id in user_game_history:
        old_game_view = user_game_history[ctx.author.id]
        if old_game_view.message:
            await ctx.send(f"이미 진행 중인 게임이 있습니다! [여기]({old_game_view.message.jump_url})를 클릭하여 기존 게임으로 이동하세요.",
                           ephemeral=True)
            return
        else:
            await ctx.send("이미 진행 중인 게임이 있습니다! 이전 게임을 완료하거나 타임아웃될 때까지 기다려주세요.", ephemeral=True)
            return

    full_deck = create_card_deck()
    num_cards_to_select = 20
    if len(full_deck) < num_cards_to_select:
        await ctx.send("오류: 게임을 시작하기에 덱의 카드가 충분하지 않습니다.", ephemeral=True)
        return

    pre_selected_cards_for_game = full_deck[:num_cards_to_select]

    game_view = BlackJackGame(ctx, pre_selected_cards_for_game)
    user_game_history[ctx.author.id] = game_view

    try:
        await game_view.send_initial_message()
    except Exception as e:
        print(f"블랙잭 게임 시작 중 오류 발생: {e}")
        await ctx.send("게임 시작 중 오류가 발생했습니다. 다시 시도해주세요.", ephemeral=True)
        if ctx.author.id in user_game_history:
            del user_game_history[ctx.author.id]