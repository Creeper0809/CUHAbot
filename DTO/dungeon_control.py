import discord

from service.session import DungeonSession, SessionType


class DungeonControlView(discord.ui.View):
    def __init__(self, session: DungeonSession, timeout=None):
        super().__init__(timeout=timeout)
        self.message = None
        self.session = session

    @discord.ui.button(label="🛑 던전 종료", style=discord.ButtonStyle.danger)
    async def stop_dungeon(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.session.status != SessionType.IDLE:
            return
        self.session.ended = True
        await interaction.response.send_message("던전이 종료 되었습니다.", ephemeral=True)
        await self.message.delete()

    @discord.ui.button(label="⏸️ 일시정지 (미구현)", style=discord.ButtonStyle.secondary, disabled=True)
    async def pause_dungeon(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("준비 중인 기능입니다.", ephemeral=True)
