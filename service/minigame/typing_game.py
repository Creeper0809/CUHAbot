"""
타이핑 게임 (Modal 기반)

주어진 문장을 빠르고 정확하게 입력하는 게임
"""
import discord
import random
import time
from .base_minigame import BaseMinigame, MinigameResult


class TypingModal(discord.ui.Modal, title="⚡ 타이핑 게임"):
    """타이핑 입력 Modal"""

    def __init__(self, target_text: str, game_instance):
        super().__init__()
        self.target_text = target_text
        self.game_instance = game_instance
        self.start_time = time.time()

        # 입력 필드
        self.answer = discord.ui.TextInput(
            label="아래 문장을 정확히 입력하세요!",
            placeholder=target_text,
            style=discord.TextStyle.short,
            required=True,
            max_length=len(target_text) + 10
        )
        self.add_item(self.answer)

    async def on_submit(self, interaction: discord.Interaction):
        elapsed = time.time() - self.start_time
        user_input = self.answer.value.strip()

        # 정확도 계산
        if user_input == self.target_text:
            accuracy = 100
            success = True
        else:
            # 레벤슈타인 거리 기반 유사도
            accuracy = self._calculate_similarity(user_input, self.target_text)
            success = accuracy >= 80

        # 점수 계산 (정확도 + 속도)
        if success:
            # 속도 보너스 (빠를수록 높은 점수)
            speed_bonus = max(0, 50 - int(elapsed * 5))
            score = int(accuracy * 0.5 + speed_bonus)
            score = min(score, 100)

            bonus_damage = score / 100 * 0.5  # 최대 50% 보너스
            message = f"✅ 정확도 {accuracy}% | 시간: {elapsed:.2f}초"
        else:
            score = 0
            bonus_damage = 0.0
            message = f"❌ 정확도 {accuracy}% (80% 이상 필요)"

        self.game_instance.result = MinigameResult(
            success=success,
            score=score,
            time_taken=elapsed,
            bonus_damage=bonus_damage,
            message=message
        )

        await interaction.response.send_message(message, ephemeral=True)

    def _calculate_similarity(self, s1: str, s2: str) -> int:
        """레벤슈타인 거리 기반 유사도 (0~100%)"""
        if len(s1) > len(s2):
            s1, s2 = s2, s1

        distances = range(len(s1) + 1)
        for i2, c2 in enumerate(s2):
            distances_ = [i2 + 1]
            for i1, c1 in enumerate(s1):
                if c1 == c2:
                    distances_.append(distances[i1])
                else:
                    distances_.append(1 + min((distances[i1], distances[i1 + 1], distances_[-1])))
            distances = distances_

        max_len = max(len(s1), len(s2))
        if max_len == 0:
            return 100

        similarity = (1 - distances[-1] / max_len) * 100
        return int(similarity)


class TypingGame(BaseMinigame):
    """타이핑 게임"""

    def __init__(self, difficulty: int = 1):
        super().__init__()
        self.name = "⌨️ 타이핑 게임"
        self.description = "주어진 문장을 빠르고 정확하게 입력하세요"
        self.difficulty = max(1, min(5, difficulty))
        self.timeout = 30.0
        self.result = None

        # 난이도별 문장
        self.sentences = {
            1: [
                "빠른 공격",
                "강력한 방어",
                "치명적인 일격"
            ],
            2: [
                "어둠의 힘이 깨어난다",
                "빛과 어둠의 전투",
                "최후의 결전이 시작된다"
            ],
            3: [
                "전설의 용사여 칼을 들어라",
                "어둠을 가르는 빛의 검",
                "운명의 시험이 그대를 기다린다"
            ],
            4: [
                "천년의 봉인이 깨지고 고대의 마왕이 부활했다",
                "빛과 어둠이 교차하는 운명의 전장에서 싸워라",
                "전설의 무기를 손에 쥐고 세계를 구원하라"
            ],
            5: [
                "태초의 혼돈 속에서 질서가 탄생했고 그 질서는 다시 혼돈으로 돌아가려 한다",
                "운명의 수레바퀴는 끊임없이 돌고 영웅과 악마는 영원히 싸운다",
                "세계의 균형을 지키는 자여 어둠의 심연으로부터 빛을 되찾아라"
            ]
        }

    async def start(self, interaction: discord.Interaction, **kwargs) -> MinigameResult:
        """게임 시작"""
        # 랜덤 문장 선택
        sentences = self.sentences.get(self.difficulty, self.sentences[1])
        target_text = random.choice(sentences)

        # Modal 표시
        modal = TypingModal(target_text, self)
        await interaction.response.send_modal(modal)

        # 타임아웃까지 대기
        await self._wait_for_result(self.timeout)

        if self.result is None:
            # 타임아웃
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
