"""
순서 게임 - 버튼을 순서대로 누르기 (사이먼 게임)

패턴이 표시되고, 같은 순서대로 버튼을 눌러야 함
"""
import asyncio
import discord
import time
import random
from discord.ui import View, Button

from .base_minigame import BaseMinigame, MinigameResult


class SequenceGameView(View):
    """순서 게임 UI"""

    def __init__(self, user: discord.User, sequence: list[int], difficulty: int):
        super().__init__(timeout=15)
        self.user = user
        self.sequence = sequence  # 정답 순서
        self.user_sequence = []  # 사용자 입력
        self.result = None
        self.start_time = time.time()

        # 난이도에 따라 버튼 개수 결정
        button_count = min(5, 3 + difficulty)
        colors = [
            discord.ButtonStyle.red,
            discord.ButtonStyle.green,
            discord.ButtonStyle.blurple,
            discord.ButtonStyle.gray,
            discord.ButtonStyle.secondary
        ]

        for i in range(button_count):
            button = Button(
                label=str(i + 1),
                style=colors[i % len(colors)],
                custom_id=f"seq_{i}"
            )
            button.callback = self._create_callback(i)
            self.add_item(button)

    def _create_callback(self, index: int):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.user.id:
                await interaction.response.send_message("❌ 당신의 게임이 아닙니다!", ephemeral=True)
                return

            self.user_sequence.append(index)

            # 현재까지 정답인지 확인
            if self.user_sequence != self.sequence[:len(self.user_sequence)]:
                # 틀림
                self.result = False
                self.stop()
                await interaction.response.defer()
                return

            # 완성했는지 확인
            if len(self.user_sequence) == len(self.sequence):
                # 성공!
                self.result = True
                self.stop()
                await interaction.response.defer()
                return

            # 계속 진행
            await interaction.response.send_message(
                f"✅ {len(self.user_sequence)}/{len(self.sequence)}",
                ephemeral=True,
                delete_after=1
            )

        return callback


class SequenceGame(BaseMinigame):
    """순서 게임 구현"""

    def __init__(self, difficulty: int = 1):
        super().__init__()
        self.name = "🔢 순서 게임"
        self.description = "패턴을 기억하고 순서대로 누르세요!"
        self.difficulty = difficulty
        self.timeout = 15.0

        # 난이도별 패턴 길이
        pattern_lengths = {1: 3, 2: 4, 3: 5, 4: 6, 5: 7}
        self.pattern_length = pattern_lengths.get(difficulty, 4)

    async def start(self, interaction: discord.Interaction, **kwargs) -> MinigameResult:
        """게임 시작"""
        button_count = min(5, 3 + self.difficulty)

        # 랜덤 패턴 생성
        sequence = [random.randint(0, button_count - 1) for _ in range(self.pattern_length)]

        # 패턴 표시
        pattern_str = " → ".join([str(i + 1) for i in sequence])
        embed = discord.Embed(
            title="🔢 순서 게임",
            description=f"**패턴을 기억하세요!**\n\n{pattern_str}\n\n난이도: {'⭐' * self.difficulty}",
            color=discord.Color.blue()
        )

        await interaction.followup.send(embed=embed)
        await asyncio.sleep(2 + self.difficulty)  # 난이도에 따라 시간 증가

        # 패턴 숨기기
        embed.description = f"**순서대로 버튼을 누르세요!**\n\n`[ ? → ? → ? ]`\n\n난이도: {'⭐' * self.difficulty}"
        view = SequenceGameView(interaction.user, sequence, self.difficulty)

        await interaction.edit_original_response(embed=embed, view=view)

        start_time = time.time()
        await view.wait()
        time_taken = time.time() - start_time

        # 결과 처리
        if view.result is None:
            # 타임아웃
            result_embed = discord.Embed(
                title="⏱️ 시간 초과!",
                description=f"정답: {pattern_str}",
                color=discord.Color.orange()
            )
            await interaction.edit_original_response(embed=result_embed, view=None)

            return MinigameResult(
                success=False,
                score=0,
                time_taken=self.timeout,
                message="⏱️ 시간 초과!"
            )

        if view.result:
            # 성공!
            score = int(100 * (1 - time_taken / self.timeout))
            score = max(50, min(100, score))  # 50~100점

            bonus = self.calculate_bonus_damage(score, time_taken)

            result_embed = discord.Embed(
                title="✅ 성공!",
                description=f"**Perfect!** 점수: {score}점\n보너스 데미지: +{int(bonus * 100)}%",
                color=discord.Color.green()
            )
            await interaction.edit_original_response(embed=result_embed, view=None)

            return MinigameResult(
                success=True,
                score=score,
                time_taken=time_taken,
                bonus_damage=bonus,
                message=f"✅ 성공! 점수: {score}"
            )
        else:
            # 실패
            user_pattern = " → ".join([str(i + 1) for i in view.user_sequence])
            result_embed = discord.Embed(
                title="❌ 실패!",
                description=f"입력: {user_pattern}\n정답: {pattern_str}",
                color=discord.Color.red()
            )
            await interaction.edit_original_response(embed=result_embed, view=None)

            return MinigameResult(
                success=False,
                score=0,
                time_taken=time_taken,
                message="❌ 실패! 순서 틀림"
            )
