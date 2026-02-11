"""
타이밍 게임 - 정확한 타이밍에 버튼 누르기

프로그레스 바가 움직이고, 녹색 구간에서 버튼을 누르면 성공
"""
import asyncio
import discord
import time
from discord.ui import View, Button

from .base_minigame import BaseMinigame, MinigameResult


class TimingGameView(View):
    """타이밍 게임 UI"""

    def __init__(self, user: discord.User, target_range: tuple[int, int]):
        super().__init__(timeout=10)
        self.user = user
        self.target_range = target_range  # (시작, 끝) 0~100
        self.result = None
        self.pressed_at = None
        self.start_time = time.time()

    @discord.ui.button(label="🎯 지금!", style=discord.ButtonStyle.danger)
    async def timing_button(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ 당신의 게임이 아닙니다!", ephemeral=True)
            return

        self.pressed_at = time.time()
        self.result = True
        self.stop()
        await interaction.response.defer()


class TimingGame(BaseMinigame):
    """타이밍 게임 구현"""

    def __init__(self, difficulty: int = 1):
        super().__init__()
        self.name = "⏱️ 타이밍 게임"
        self.description = "녹색 구간에서 버튼을 누르세요!"
        self.difficulty = difficulty
        self.timeout = 10.0

        # 난이도별 타겟 구간 크기
        target_sizes = {1: 30, 2: 25, 3: 20, 4: 15, 5: 10}
        self.target_size = target_sizes.get(difficulty, 20)

    async def start(self, interaction: discord.Interaction, **kwargs) -> MinigameResult:
        """게임 시작"""
        # 타겟 구간 설정 (랜덤 위치)
        import random
        target_start = random.randint(0, 100 - self.target_size)
        target_end = target_start + self.target_size
        target_range = (target_start, target_end)

        # 초기 임베드
        embed = discord.Embed(
            title="⏱️ 타이밍 게임",
            description=f"**녹색 구간**에서 버튼을 누르세요!\n\n난이도: {'⭐' * self.difficulty}",
            color=discord.Color.blue()
        )

        view = TimingGameView(interaction.user, target_range)
        await interaction.followup.send(embed=embed, view=view)

        start_time = time.time()

        # 프로그레스 바 업데이트 (0.5초마다)
        for i in range(20):
            if view.result is not None:
                break

            progress = (i + 1) * 5  # 0 ~ 100
            bar = self._create_progress_bar(progress, target_range)

            embed.description = (
                f"**녹색 구간**에서 버튼을 누르세요!\n\n"
                f"난이도: {'⭐' * self.difficulty}\n\n"
                f"{bar}"
            )

            try:
                await interaction.edit_original_response(embed=embed)
            except:
                pass

            await asyncio.sleep(0.5)

        # 타임아웃 대기
        await view.wait()

        # 결과 계산
        if view.pressed_at is None:
            # 타임아웃
            return MinigameResult(
                success=False,
                score=0,
                time_taken=self.timeout,
                message="⏱️ 시간 초과!"
            )

        time_taken = view.pressed_at - start_time
        # 눌린 시점의 프로그레스 계산
        pressed_progress = int((time_taken / self.timeout) * 100)

        # 타겟 구간에 있는지 확인
        if target_range[0] <= pressed_progress <= target_range[1]:
            # 성공! 중앙에 가까울수록 높은 점수
            target_center = (target_range[0] + target_range[1]) / 2
            distance = abs(pressed_progress - target_center)
            max_distance = self.target_size / 2
            score = int(100 * (1 - distance / max_distance))

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
            result_embed = discord.Embed(
                title="❌ 실패!",
                description="타겟 구간을 벗어났습니다!",
                color=discord.Color.red()
            )
            await interaction.edit_original_response(embed=result_embed, view=None)

            return MinigameResult(
                success=False,
                score=0,
                time_taken=time_taken,
                message="❌ 실패! 타겟 벗어남"
            )

    def _create_progress_bar(self, progress: int, target_range: tuple[int, int]) -> str:
        """프로그레스 바 생성"""
        bar = ""
        for i in range(0, 101, 5):
            if target_range[0] <= i <= target_range[1]:
                # 타겟 구간 (녹색)
                if i <= progress:
                    bar += "🟩"
                else:
                    bar += "🟢"
            else:
                # 일반 구간
                if i <= progress:
                    bar += "🟦"
                else:
                    bar += "⬜"

        return bar + f" {progress}%"
