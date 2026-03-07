"""
가위바위보 게임 - 보스와 가위바위보

3판 2선승제 또는 1판 승부
"""
import asyncio
import discord
import time
import random
from discord.ui import View, Button

from .base_minigame import BaseMinigame, MinigameResult, build_e2e_result, e2e_autopilot_enabled


class RPSView(View):
    """가위바위보 UI"""

    def __init__(self, user: discord.User):
        super().__init__(timeout=8)
        self.user = user
        self.choice = None

    @discord.ui.button(label="✊ 바위", style=discord.ButtonStyle.gray)
    async def rock_button(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ 당신의 게임이 아닙니다!", ephemeral=True)
            return
        self.choice = "rock"
        self.stop()
        await interaction.response.defer()

    @discord.ui.button(label="✋ 보", style=discord.ButtonStyle.blurple)
    async def paper_button(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ 당신의 게임이 아닙니다!", ephemeral=True)
            return
        self.choice = "paper"
        self.stop()
        await interaction.response.defer()

    @discord.ui.button(label="✌️ 가위", style=discord.ButtonStyle.green)
    async def scissors_button(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ 당신의 게임이 아닙니다!", ephemeral=True)
            return
        self.choice = "scissors"
        self.stop()
        await interaction.response.defer()


class RPSGame(BaseMinigame):
    """가위바위보 게임 구현"""

    EMOJIS = {
        "rock": "✊",
        "paper": "✋",
        "scissors": "✌️"
    }

    NAMES = {
        "rock": "바위",
        "paper": "보",
        "scissors": "가위"
    }

    def __init__(self, difficulty: int = 1):
        super().__init__()
        self.name = "✊ 가위바위보"
        self.description = "보스와 가위바위보 대결!"
        self.difficulty = difficulty
        self.timeout = 8.0

        # 난이도에 따라 라운드 수
        self.rounds = min(3, 1 + difficulty)

    async def start(self, interaction: discord.Interaction, **kwargs) -> MinigameResult:
        """게임 시작"""
        if e2e_autopilot_enabled():
            return build_e2e_result()
        wins = 0
        losses = 0
        draws = 0

        boss_name = kwargs.get("boss_name", "보스")

        # 라운드 진행
        for round_num in range(self.rounds):
            embed = discord.Embed(
                title="✊ 가위바위보",
                description=(
                    f"**{boss_name}**와 대결!\n\n"
                    f"라운드 {round_num + 1}/{self.rounds}\n"
                    f"점수: {wins}승 {losses}패 {draws}무\n\n"
                    f"가위, 바위, 보 중 하나를 선택하세요!"
                ),
                color=discord.Color.blue()
            )

            view = RPSView(interaction.user)

            if round_num == 0:
                await interaction.followup.send(embed=embed, view=view)
            else:
                await interaction.edit_original_response(embed=embed, view=view)

            await view.wait()

            if view.choice is None:
                # 타임아웃
                result_embed = discord.Embed(
                    title="⏱️ 시간 초과!",
                    description=f"최종 점수: {wins}승 {losses}패 {draws}무",
                    color=discord.Color.orange()
                )
                await interaction.edit_original_response(embed=result_embed, view=None)

                return MinigameResult(
                    success=False,
                    score=0,
                    time_taken=self.timeout,
                    message="⏱️ 시간 초과!"
                )

            # 보스 선택 (랜덤)
            boss_choice = random.choice(["rock", "paper", "scissors"])
            player_choice = view.choice

            # 결과 판정
            result = self._judge(player_choice, boss_choice)

            if result == "win":
                wins += 1
                result_text = "✅ 승리!"
                result_color = discord.Color.green()
            elif result == "lose":
                losses += 1
                result_text = "❌ 패배!"
                result_color = discord.Color.red()
            else:
                draws += 1
                result_text = "🤝 무승부!"
                result_color = discord.Color.greyple()

            # 라운드 결과 표시
            round_result_embed = discord.Embed(
                title=result_text,
                description=(
                    f"당신: {self.EMOJIS[player_choice]} {self.NAMES[player_choice]}\n"
                    f"{boss_name}: {self.EMOJIS[boss_choice]} {self.NAMES[boss_choice]}\n\n"
                    f"점수: {wins}승 {losses}패 {draws}무"
                ),
                color=result_color
            )
            await interaction.edit_original_response(embed=round_result_embed, view=None)

            if round_num < self.rounds - 1:
                await asyncio.sleep(2)

        # 최종 결과
        final_success = wins > losses

        if final_success:
            score = int((wins / self.rounds) * 100)
            bonus = self.calculate_bonus_damage(score, 0)

            final_embed = discord.Embed(
                title="🏆 승리!",
                description=f"최종 점수: {wins}승 {losses}패 {draws}무\n점수: {score}점\n보너스 데미지: +{int(bonus * 100)}%",
                color=discord.Color.gold()
            )
            await interaction.edit_original_response(embed=final_embed)

            return MinigameResult(
                success=True,
                score=score,
                time_taken=0,
                bonus_damage=bonus,
                message=f"🏆 승리! {wins}승"
            )
        else:
            final_embed = discord.Embed(
                title="💀 패배!",
                description=f"최종 점수: {wins}승 {losses}패 {draws}무",
                color=discord.Color.red()
            )
            await interaction.edit_original_response(embed=final_embed)

            return MinigameResult(
                success=False,
                score=0,
                time_taken=0,
                message=f"💀 패배! {losses}패"
            )

    def _judge(self, player: str, boss: str) -> str:
        """승패 판정"""
        if player == boss:
            return "draw"

        win_conditions = {
            "rock": "scissors",
            "scissors": "paper",
            "paper": "rock"
        }

        if win_conditions[player] == boss:
            return "win"
        else:
            return "lose"
