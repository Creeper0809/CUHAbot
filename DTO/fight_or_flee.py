import discord


class FightOrFleeView(discord.ui.View):
    def __init__(self, user: discord.User, timeout=15):
        super().__init__(timeout=timeout)
        self.user = user
        self.result = None
        self.message = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user == self.user

    @discord.ui.button(label="⚔️ 싸운다", style=discord.ButtonStyle.danger)
    async def fight(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.result = True
        self.stop()
        await interaction.response.defer()
        if self.message:
            await self.message.edit(view=None)

    @discord.ui.button(label="🏃 도망간다", style=discord.ButtonStyle.secondary)
    async def flee(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.result = False
        self.stop()
        await interaction.response.defer()
        if self.message:
            await self.message.edit(view=None)

    async def on_timeout(self):
        if self.message:
            try:
                await self.message.edit(view=None)
            except discord.NotFound:
                pass
