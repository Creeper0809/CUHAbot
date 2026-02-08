"""
프리셋 삭제 View

프리셋 삭제 선택 UI를 정의합니다.
"""
from __future__ import annotations

from typing import List, TYPE_CHECKING

import discord

from models.user_deck_preset import UserDeckPreset

if TYPE_CHECKING:
    from views.skill_deck.main import SkillDeckView


class DeletePresetView(discord.ui.View):
    """프리셋 삭제 선택 View"""

    def __init__(self, parent_view: SkillDeckView, presets: List[UserDeckPreset]):
        super().__init__(timeout=30)
        self.parent_view = parent_view
        self.presets = presets

        options = [
            discord.SelectOption(
                label=preset.name,
                value=str(preset.id)
            )
            for preset in presets
        ]

        self.select = discord.ui.Select(
            placeholder="삭제할 프리셋 선택",
            options=options
        )
        self.select.callback = self.select_callback
        self.add_item(self.select)

    async def select_callback(self, interaction: discord.Interaction):
        preset_id = int(self.select.values[0])
        preset = await UserDeckPreset.get_or_none(id=preset_id)

        if preset:
            name = preset.name
            await preset.delete()

            await self.parent_view._refresh_preset_dropdown()

            await interaction.response.edit_message(
                content=f"🗑️ **{name}** 프리셋이 삭제되었습니다.",
                view=None
            )
        else:
            await interaction.response.edit_message(
                content="프리셋을 찾을 수 없습니다.",
                view=None
            )
