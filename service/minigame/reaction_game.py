"""
반응속도 게임 - 신호가 나타나면 빠르게 버튼 누르기

신호(이모지)가 나타나면 최대한 빠르게 버튼을 눌러야 함
"""
import asyncio
import discord
import time
import random
from discord.ui import View, Button

from .base_minigame import BaseMinigame, MinigameResult


class ReactionView(View):
    """반응속도 UI"""

    def __init__(self, user: discord.User):
        super().__init__(timeout=5)
        self.user = user
        self.result = None
        self.reaction_time = None

    @discord.ui.button(label="🔴 대기 중...", style=discord.ButtonStyle.gray, disabled=True)
    async def reaction_button(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ 당신의 게임이 아닙니다!", ephemeral=True)
            return

        self.reaction_time = time.time()
        self.result = True
        self.stop()
        await interaction.response.defer()

    def enable_button(self):
        """버튼 활성화"""
        self.reaction_button.label = "⚡ 지금 클릭!"
        self.reaction_button.style = discord.ButtonStyle.green
        self.reaction_button.disabled = False


class ReactionGame(BaseMinigame):
    """반응속도 게임 구현"""

    def __init__(self, difficulty: int = 1):
        super().__init__()
        self.name = "⚡ 반응속도"
        self.description = "신호가 나타나면 빠르게 클릭!"
        self.difficulty = difficulty
        self.timeout = 5.0

        # 난이도에 따라 대기 시간 랜덤 범위
        self.wait_range = (2.0, 4.0 - difficulty * 0.3)

    async def start(self, interaction: discord.Interaction, **kwargs) -> MinigameResult:
        """게임 시작"""
        # 초기 임베드
        embed = discord.Embed(
            title="⚡ 반응속도 게임",
            description=f"🔴 **대기 중...**\n\n신호가 나타나면 빠르게 버튼을 누르세요!\n난이도: {'⭐' * self.difficulty}",
            color=discord.Color.orange()
        )

        view = ReactionView(interaction.user)
        await interaction.followup.send(embed=embed, view=view)

        # 랜덤 대기 시간
        wait_time = random.uniform(*self.wait_range)
        await asyncio.sleep(wait_time)

        # 신호 표시
        embed.description = f"🟢 **지금!**\n\n빠르게 버튼을 누르세요!\n난이도: {'⭐' * self.difficulty}"
        embed.color = discord.Color.green()

        view.enable_button()
        signal_time = time.time()

        await interaction.edit_original_response(embed=embed, view=view)

        await view.wait()

        # 결과 처리
        if view.reaction_time is None:
            # 타임아웃
            result_embed = discord.Embed(
                title="⏱️ 시간 초과!",
                description="너무 느립니다!",
                color=discord.Color.red()
            )
            await interaction.edit_original_response(embed=result_embed, view=None)

            return MinigameResult(
                success=False,
                score=0,
                time_taken=self.timeout,
                message="⏱️ 시간 초과!"
            )

        # 반응 시간 계산
        reaction_time = view.reaction_time - signal_time

        # 너무 빠르면 부정행위 (신호 전에 클릭)
        if reaction_time < 0.05:
            result_embed = discord.Embed(
                title="❌ 너무 빠릅니다!",
                description="신호를 기다려주세요!",
                color=discord.Color.red()
            )
            await interaction.edit_original_response(embed=result_embed, view=None)

            return MinigameResult(
                success=False,
                score=0,
                time_taken=reaction_time,
                message="❌ 너무 빠름!"
            )

        # 점수 계산 (0.2초 이하 = 100점, 1초 = 50점)
        if reaction_time <= 0.2:
            score = 100
        elif reaction_time <= 1.0:
            score = int(100 - (reaction_time - 0.2) * 62.5)
        else:
            score = int(50 - (reaction_time - 1.0) * 10)
        score = max(20, min(100, score))

        bonus = self.calculate_bonus_damage(score, reaction_time)

        # 등급 표시
        if reaction_time <= 0.15:
            grade = "🏆 완벽!"
        elif reaction_time <= 0.25:
            grade = "⭐ 빠름!"
        elif reaction_time <= 0.5:
            grade = "✅ 좋음"
        else:
            grade = "💨 보통"

        result_embed = discord.Embed(
            title=f"✅ {grade}",
            description=f"**반응 시간: {reaction_time:.3f}초**\n점수: {score}점\n보너스 데미지: +{int(bonus * 100)}%",
            color=discord.Color.green()
        )
        await interaction.edit_original_response(embed=result_embed, view=None)

        return MinigameResult(
            success=True,
            score=score,
            time_taken=reaction_time,
            bonus_damage=bonus,
            message=f"✅ {reaction_time:.3f}초"
        )
