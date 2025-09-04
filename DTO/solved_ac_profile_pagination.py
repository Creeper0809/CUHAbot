import discord
from discord.ui import Button, View

from service.user_service import build_problem_embed


class ProfilePagination(View):
    def __init__(self, profile_embed, solved_items, bot, handle):
        super().__init__(timeout=60)
        self.page = 1
        self.profile_embed = profile_embed
        self.solved_items = solved_items
        self.bot = bot
        self.handle = handle
        self.max_page = 1 + (len(solved_items) - 1) // 10

    async def update_message(self, interaction: discord.Interaction):
        if self.page == 1:
            await interaction.response.edit_message(
                embed=self.profile_embed,
                view=self
            )
        else:
            embed = build_problem_embed(self.solved_items, self.page, self.bot, self.handle)
            await interaction.response.edit_message(
                embed=embed,
                attachments=[],
                view=self
            )

        self.prev_page.disabled = self.page == 1
        self.next_page.disabled = self.page >= self.max_page

    @discord.ui.button(label="◀️ 이전", style=discord.ButtonStyle.secondary)
    async def prev_page(self, interaction: discord.Interaction, button: Button):
        if self.page > 1:
            self.page -= 1
            await self.update_message(interaction)

    @discord.ui.button(label="다음 ▶️", style=discord.ButtonStyle.secondary)
    async def next_page(self, interaction: discord.Interaction, button: Button):
        if self.page < self.max_page:
            self.page += 1
            await self.update_message(interaction)
