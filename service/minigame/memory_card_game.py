"""
메모리 카드 게임 (View 기반)

카드를 뒤집어서 같은 그림 찾기
"""
import discord
import random
import time
from .base_minigame import BaseMinigame, MinigameResult


class MemoryCardView(discord.ui.View):
    """메모리 카드 게임 View"""

    def __init__(self, game_instance, pairs: int):
        super().__init__(timeout=30.0)
        self.game_instance = game_instance
        self.pairs = pairs
        self.total_cards = pairs * 2

        # 카드 생성 (이모지 사용)
        self.emojis = ["🔥", "❄️", "⚡", "💧", "🌟", "🌙", "☀️", "🍀"]
        selected_emojis = self.emojis[:pairs]
        self.cards = selected_emojis * 2
        random.shuffle(self.cards)

        # 게임 상태
        self.revealed = [False] * self.total_cards
        self.matched = [False] * self.total_cards
        self.first_card = None
        self.attempts = 0
        self.matches = 0
        self.start_time = time.time()
        self.message = None

        # 버튼 생성 (4x4 or 3x4 grid)
        cols = 4
        rows = (self.total_cards + cols - 1) // cols

        for i in range(self.total_cards):
            button = discord.ui.Button(
                style=discord.ButtonStyle.secondary,
                label="❓",
                row=i // cols,
                custom_id=f"card_{i}"
            )
            button.callback = self._make_callback(i)
            self.add_item(button)

    def _make_callback(self, index: int):
        """버튼 콜백 생성"""
        async def callback(interaction: discord.Interaction):
            await self._handle_card_click(interaction, index)
        return callback

    async def _handle_card_click(self, interaction: discord.Interaction, index: int):
        """카드 클릭 처리"""
        # 이미 매칭되었거나 공개된 카드는 무시
        if self.matched[index] or self.revealed[index]:
            await interaction.response.defer()
            return

        # 첫 번째 카드 선택
        if self.first_card is None:
            self.first_card = index
            self.revealed[index] = True
            await self._update_view(interaction)
            return

        # 같은 카드 다시 클릭
        if self.first_card == index:
            await interaction.response.defer()
            return

        # 두 번째 카드 선택
        second_card = index
        self.revealed[second_card] = True
        self.attempts += 1

        # 매칭 확인
        if self.cards[self.first_card] == self.cards[second_card]:
            # 매칭 성공
            self.matched[self.first_card] = True
            self.matched[second_card] = True
            self.matches += 1

            # 모든 카드 매칭 완료
            if self.matches == self.pairs:
                await self._game_over(interaction, success=True)
                return
        else:
            # 매칭 실패 - 잠시 보여주고 다시 숨김
            await self._update_view(interaction)
            await discord.utils.sleep_until(discord.utils.utcnow() + discord.timedelta(seconds=1))
            self.revealed[self.first_card] = False
            self.revealed[second_card] = False

        self.first_card = None
        await self._update_view(interaction)

    async def _update_view(self, interaction: discord.Interaction):
        """View 업데이트"""
        # 버튼 업데이트
        for i, button in enumerate(self.children):
            if self.matched[i]:
                button.style = discord.ButtonStyle.success
                button.label = self.cards[i]
                button.disabled = True
            elif self.revealed[i]:
                button.style = discord.ButtonStyle.primary
                button.label = self.cards[i]
            else:
                button.style = discord.ButtonStyle.secondary
                button.label = "❓"

        content = f"🃏 **메모리 카드 게임**\n시도: {self.attempts}회 | 매칭: {self.matches}/{self.pairs}"

        if interaction.response.is_done():
            await interaction.message.edit(content=content, view=self)
        else:
            await interaction.response.edit_message(content=content, view=self)

    async def _game_over(self, interaction: discord.Interaction, success: bool):
        """게임 종료"""
        elapsed = time.time() - self.start_time

        if success:
            # 점수 계산 (시도 횟수가 적을수록, 빠를수록 높은 점수)
            min_attempts = self.pairs  # 최소 시도 횟수
            attempt_score = max(0, 100 - (self.attempts - min_attempts) * 10)
            time_score = max(0, 100 - int(elapsed * 2))
            score = int((attempt_score + time_score) / 2)
            score = max(0, min(score, 100))

            bonus_damage = score / 100 * 0.5  # 최대 50% 보너스
            message = f"✅ 성공! {self.attempts}회 시도 | {elapsed:.1f}초"

            self.game_instance.result = MinigameResult(
                success=True,
                score=score,
                time_taken=elapsed,
                bonus_damage=bonus_damage,
                message=message
            )
        else:
            self.game_instance.result = MinigameResult(
                success=False,
                score=0,
                time_taken=elapsed,
                message="⏰ 시간 초과!"
            )

        # View 비활성화
        for button in self.children:
            button.disabled = True

        await interaction.response.edit_message(
            content=f"🃏 **게임 종료**\n{self.game_instance.result.message}",
            view=self
        )

    async def on_timeout(self):
        """타임아웃 처리"""
        if self.game_instance.result is None:
            elapsed = time.time() - self.start_time
            self.game_instance.result = MinigameResult(
                success=False,
                score=0,
                time_taken=elapsed,
                message="⏰ 시간 초과!"
            )

        if self.message:
            for button in self.children:
                button.disabled = True
            await self.message.edit(content="⏰ **시간 초과!**", view=self)


class MemoryCardGame(BaseMinigame):
    """메모리 카드 게임"""

    def __init__(self, difficulty: int = 1):
        super().__init__()
        self.name = "🃏 메모리 카드"
        self.description = "같은 카드를 찾아서 매칭하세요"
        self.difficulty = max(1, min(5, difficulty))
        self.timeout = 30.0
        self.result = None

        # 난이도별 카드 쌍 수
        self.pairs_by_difficulty = {
            1: 3,  # 6장
            2: 4,  # 8장
            3: 5,  # 10장
            4: 6,  # 12장
            5: 8,  # 16장
        }

    async def start(self, interaction: discord.Interaction, **kwargs) -> MinigameResult:
        """게임 시작"""
        pairs = self.pairs_by_difficulty.get(self.difficulty, 4)

        view = MemoryCardView(self, pairs)
        content = f"🃏 **메모리 카드 게임**\n카드 쌍: {pairs}개 | 제한시간: {self.timeout}초"

        await interaction.response.send_message(content=content, view=view)
        view.message = await interaction.original_response()

        # 타임아웃까지 대기
        await self._wait_for_result(self.timeout)

        if self.result is None:
            self.result = MinigameResult(
                success=False,
                score=0,
                time_taken=self.timeout,
                message="⏰ 시간 초과!"
            )

        return self.result

    async def _wait_for_result(self, timeout: float):
        """결과 대기"""
        import asyncio
        start = time.time()
        while self.result is None and (time.time() - start) < timeout:
            await asyncio.sleep(0.1)
