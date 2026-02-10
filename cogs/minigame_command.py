"""
미니게임 테스트 커맨드 (어드민 전용)

미니게임을 테스트하고 보스 페이즈 개발에 활용
"""
import discord
from discord import app_commands
from discord.ext import commands

from bot import GUILD_IDS
from service.minigame.minigame_manager import MinigameManager


class MinigameCommand(commands.Cog):
    """미니게임 테스트 커맨드"""

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="미니게임", description="[어드민] 미니게임 테스트")
    @app_commands.guilds(*GUILD_IDS)
    @app_commands.describe(
        게임="테스트할 미니게임 (생략 시 랜덤)",
        난이도="난이도 (1~5, 기본 1)"
    )
    @app_commands.choices(게임=[
        app_commands.Choice(name="⏱️ 타이밍 게임", value="timing"),
        app_commands.Choice(name="🔢 순서 게임", value="sequence"),
        app_commands.Choice(name="⚡ 반응속도", value="reaction"),
        app_commands.Choice(name="✊ 가위바위보", value="rps"),
        app_commands.Choice(name="⌨️ 타이핑 게임", value="typing"),
        app_commands.Choice(name="🔢 수학 게임", value="math"),
        app_commands.Choice(name="🃏 메모리 카드", value="memory"),
        app_commands.Choice(name="🎲 랜덤", value="random"),
    ])
    async def test_minigame(
        self,
        interaction: discord.Interaction,
        게임: app_commands.Choice[str] = None,
        난이도: int = 1
    ):
        """미니게임 테스트"""
        # 난이도 범위 체크
        난이도 = max(1, min(5, 난이도))

        # 미니게임 선택
        if 게임 is None or 게임.value == "random":
            minigame = MinigameManager.get_random_minigame(difficulty=난이도)
        else:
            minigame = MinigameManager.get_minigame(게임.value, difficulty=난이도)

        if not minigame:
            await interaction.response.send_message("❌ 미니게임을 찾을 수 없습니다!", ephemeral=True)
            return

        # 시작 메시지
        await interaction.response.send_message(
            f"🎮 **{minigame.name}** 시작!\n난이도: {'⭐' * 난이도}",
            ephemeral=False
        )

        # 미니게임 실행
        try:
            result = await minigame.start(
                interaction,
                boss_name="테스트 보스"
            )

            # 결과 요약
            if result.success:
                summary = (
                    f"✅ **성공!**\n"
                    f"점수: {result.score}\n"
                    f"소요 시간: {result.time_taken:.2f}초\n"
                    f"보너스 데미지: +{int(result.bonus_damage * 100)}%"
                )
                color = discord.Color.green()
            else:
                summary = (
                    f"❌ **실패!**\n"
                    f"{result.message}"
                )
                color = discord.Color.red()

            summary_embed = discord.Embed(
                title=f"📊 {minigame.name} 결과",
                description=summary,
                color=color
            )

            await interaction.followup.send(embed=summary_embed)

        except Exception as e:
            await interaction.followup.send(f"⚠️ 오류 발생: {e}", ephemeral=True)

    @app_commands.command(name="미니게임목록", description="[어드민] 사용 가능한 미니게임 목록")
    @app_commands.guilds(*GUILD_IDS)
    async def list_minigames(self, interaction: discord.Interaction):
        """미니게임 목록 조회"""
        games = MinigameManager.list_minigames()

        embed = discord.Embed(
            title="🎮 사용 가능한 미니게임",
            description="보스 페이즈에 사용할 수 있는 미니게임 목록입니다.",
            color=discord.Color.blue()
        )

        for game_id in games:
            info = MinigameManager.get_minigame_info(game_id)
            if info:
                embed.add_field(
                    name=f"{info['name']} (`{game_id}`)",
                    value=f"{info['description']}\n제한시간: {info['timeout']}초",
                    inline=False
                )

        embed.set_footer(text="사용법: /미니게임 [게임] [난이도]")

        await interaction.response.send_message(embed=embed, ephemeral=False)


async def setup(bot):
    await bot.add_cog(MinigameCommand(bot))
