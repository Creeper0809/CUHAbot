"""
관전자 View

관전자 DM에 표시되는 View로, "관전 종료" 버튼을 제공합니다.
"""
import discord
import logging

logger = logging.getLogger(__name__)


class SpectatorView(discord.ui.View):
    """관전자 제어 View (관전 종료 버튼)"""

    def __init__(
        self,
        spectator: discord.User,
        target_session,
        timeout: int = None
    ):
        """
        Args:
            spectator: 관전자 Discord User
            target_session: 관전 대상의 DungeonSession
            timeout: View 타임아웃 (None = 무제한)
        """
        super().__init__(timeout=timeout)
        self.spectator = spectator
        self.target_session = target_session
        self.message: discord.Message = None

    @discord.ui.button(
        label="🚪 관전 종료",
        style=discord.ButtonStyle.secondary,
        custom_id="stop_spectate_button"
    )
    async def stop_spectate_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        """관전 종료 버튼 콜백"""
        try:
            from service.spectator.spectator_service import SpectatorService

            await SpectatorService.stop_spectating(self.spectator.id)

            await interaction.response.send_message(
                "✅ 관전을 종료했습니다.",
                ephemeral=True
            )

            # 메시지 삭제
            if self.message:
                try:
                    await self.message.delete()
                except discord.NotFound:
                    pass

        except Exception as e:
            logger.error(f"Failed to stop spectating: {e}", exc_info=True)
            await interaction.response.send_message(
                "❌ 관전 종료 중 오류가 발생했습니다.",
                ephemeral=True
            )

    async def interaction_check(
        self,
        interaction: discord.Interaction
    ) -> bool:
        """관전자만 버튼 클릭 가능"""
        return interaction.user.id == self.spectator.id
