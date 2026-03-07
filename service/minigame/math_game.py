"""
수학 게임 (Modal 기반)

계산 문제를 풀어서 답을 입력하는 게임
"""
import discord
import random
import time
from .base_minigame import BaseMinigame, MinigameResult, build_e2e_result, e2e_autopilot_enabled


class MathModal(discord.ui.Modal, title="🔢 수학 게임"):
    """수학 문제 입력 Modal"""

    def __init__(self, question: str, correct_answer: int, game_instance):
        super().__init__()
        self.question = question
        self.correct_answer = correct_answer
        self.game_instance = game_instance
        self.start_time = time.time()

        # 입력 필드
        self.answer = discord.ui.TextInput(
            label=f"문제: {question}",
            placeholder="답을 숫자로 입력하세요",
            style=discord.TextStyle.short,
            required=True,
            max_length=10
        )
        self.add_item(self.answer)

    async def on_submit(self, interaction: discord.Interaction):
        elapsed = time.time() - self.start_time

        try:
            user_answer = int(self.answer.value.strip())

            if user_answer == self.correct_answer:
                # 정답
                success = True
                # 속도 보너스
                speed_bonus = max(0, 100 - int(elapsed * 10))
                score = max(50, speed_bonus)
                bonus_damage = score / 100 * 0.4  # 최대 40% 보너스
                message = f"✅ 정답! ({elapsed:.2f}초)"
            else:
                # 오답
                success = False
                score = 0
                bonus_damage = 0.0
                message = f"❌ 오답! 정답은 {self.correct_answer}"

        except ValueError:
            # 숫자가 아닌 입력
            success = False
            score = 0
            bonus_damage = 0.0
            message = "❌ 숫자를 입력해주세요!"

        self.game_instance.result = MinigameResult(
            success=success,
            score=score,
            time_taken=elapsed,
            bonus_damage=bonus_damage,
            message=message
        )

        await interaction.response.send_message(message, ephemeral=True)


class MathGame(BaseMinigame):
    """수학 게임"""

    def __init__(self, difficulty: int = 1):
        super().__init__()
        self.name = "🔢 수학 게임"
        self.description = "계산 문제를 빠르게 풀어보세요"
        self.difficulty = max(1, min(5, difficulty))
        self.timeout = 20.0
        self.result = None

    async def start(self, interaction: discord.Interaction, **kwargs) -> MinigameResult:
        """게임 시작"""
        if e2e_autopilot_enabled():
            return build_e2e_result()
        # 난이도별 문제 생성
        question, answer = self._generate_problem()

        # Modal 표시
        modal = MathModal(question, answer, self)
        await interaction.response.send_modal(modal)

        # 타임아웃까지 대기
        await self._wait_for_result(self.timeout)

        if self.result is None:
            # 타임아웃
            self.result = MinigameResult(
                success=False,
                score=0,
                time_taken=self.timeout,
                message=f"⏰ 시간 초과! 정답은 {answer}"
            )

        return self.result

    def _generate_problem(self) -> tuple[str, int]:
        """난이도별 문제 생성"""
        if self.difficulty == 1:
            # 한 자리 수 덧셈/뺄셈
            a, b = random.randint(1, 9), random.randint(1, 9)
            op = random.choice(["+", "-"])
            if op == "+":
                return f"{a} + {b}", a + b
            else:
                if a < b:
                    a, b = b, a
                return f"{a} - {b}", a - b

        elif self.difficulty == 2:
            # 두 자리 수 덧셈/뺄셈
            a, b = random.randint(10, 50), random.randint(10, 50)
            op = random.choice(["+", "-"])
            if op == "+":
                return f"{a} + {b}", a + b
            else:
                if a < b:
                    a, b = b, a
                return f"{a} - {b}", a - b

        elif self.difficulty == 3:
            # 두 자리 수 곱셈 or 세 수 연산
            if random.random() < 0.5:
                a, b = random.randint(5, 15), random.randint(2, 9)
                return f"{a} × {b}", a * b
            else:
                a, b, c = random.randint(10, 30), random.randint(5, 20), random.randint(5, 15)
                return f"{a} + {b} - {c}", a + b - c

        elif self.difficulty == 4:
            # 복잡한 연산
            a, b, c = random.randint(10, 30), random.randint(2, 9), random.randint(5, 20)
            op = random.choice([
                (f"{a} × {b} + {c}", a * b + c),
                (f"{a} × {b} - {c}", a * b - c),
                (f"({a} + {b}) × {c}", (a + b) * c),
            ])
            return op

        else:  # difficulty == 5
            # 매우 복잡한 연산
            a, b, c, d = random.randint(10, 30), random.randint(2, 9), random.randint(5, 20), random.randint(2, 5)
            op = random.choice([
                (f"{a} × {b} + {c} × {d}", a * b + c * d),
                (f"({a} + {b}) × {c} - {d}", (a + b) * c - d),
                (f"{a} × {b} - {c} × {d}", a * b - c * d),
            ])
            return op

    async def _wait_for_result(self, timeout: float):
        """결과 대기"""
        import asyncio
        start = time.time()
        while self.result is None and (time.time() - start) < timeout:
            await asyncio.sleep(0.1)
