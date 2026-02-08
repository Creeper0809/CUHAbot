"""
스킬 덱 버튼 컴포넌트

슬롯 버튼, 프리셋 저장/삭제, 스킬 검색, 전체 선택/채우기, 확정/취소 버튼을 정의합니다.
"""
from __future__ import annotations

from typing import List, TYPE_CHECKING

import discord

from config import SKILL_DECK_SIZE, SKILL_ID
from models.user_deck_preset import UserDeckPreset

if TYPE_CHECKING:
    from views.skill_deck.main import SkillDeckView


class SlotButton(discord.ui.Button):
    """슬롯 선택 버튼 (토글 방식, 여러 개 선택 가능)"""

    def __init__(self, slot_index: int, skill_name: str, is_selected: bool = False):
        self.slot_index = slot_index
        style = discord.ButtonStyle.primary if is_selected else discord.ButtonStyle.secondary
        short_name = skill_name[:6] if len(skill_name) > 6 else skill_name

        super().__init__(
            label=f"{slot_index + 1}:{short_name}",
            style=style,
            row=2 + (slot_index // 5)
        )

    async def callback(self, interaction: discord.Interaction):
        view: SkillDeckView = self.view

        if self.slot_index in view.selected_slots:
            view.selected_slots.remove(self.slot_index)
        else:
            view.selected_slots.add(self.slot_index)

        view._update_slot_buttons()

        embed = view.create_embed()

        if view.selected_slots:
            slot_list = ", ".join(str(s + 1) for s in sorted(view.selected_slots))
            embed.add_field(
                name=f"📍 슬롯 {len(view.selected_slots)}개 선택됨",
                value=f"**[{slot_list}]** 선택됨. 위에서 스킬을 선택하세요.",
                inline=False
            )

        await interaction.response.edit_message(embed=embed, view=view)


class SavePresetButton(discord.ui.Button):
    """프리셋 저장 버튼"""

    def __init__(self):
        super().__init__(
            label="프리셋 저장",
            style=discord.ButtonStyle.secondary,
            emoji="💾",
            row=4
        )

    async def callback(self, interaction: discord.Interaction):
        from views.skill_deck.modals import PresetNameModal

        view: SkillDeckView = self.view

        for i in range(len(view.current_deck)):
            if view.current_deck[i] == 0:
                view.current_deck[i] = SKILL_ID.BASIC_ATTACK_ID

        modal = PresetNameModal(view)
        await interaction.response.send_modal(modal)


class DeletePresetButton(discord.ui.Button):
    """프리셋 삭제 버튼"""

    def __init__(self):
        super().__init__(
            label="삭제",
            style=discord.ButtonStyle.secondary,
            emoji="🗑️",
            row=4
        )

    async def callback(self, interaction: discord.Interaction):
        from views.skill_deck.preset_view import DeletePresetView

        view: SkillDeckView = self.view

        presets = await UserDeckPreset.filter(user_id=view.db_user.id)

        if not presets:
            await interaction.response.send_message(
                "삭제할 프리셋이 없습니다.",
                ephemeral=True
            )
            return

        delete_view = DeletePresetView(view, list(presets))
        await interaction.response.send_message(
            "🗑️ 삭제할 프리셋을 선택하세요:",
            view=delete_view,
            ephemeral=True
        )


class SearchSkillButton(discord.ui.Button):
    """스킬 필터 버튼"""

    def __init__(self):
        super().__init__(
            label="검색",
            style=discord.ButtonStyle.secondary,
            emoji="🔍",
            row=4
        )

    async def callback(self, interaction: discord.Interaction):
        from views.skill_deck.modals import SkillFilterModal

        view: SkillDeckView = self.view
        modal = SkillFilterModal(view)
        await interaction.response.send_modal(modal)


class SelectAllButton(discord.ui.Button):
    """전체 선택/해제 토글"""

    def __init__(self):
        super().__init__(
            label="전체",
            style=discord.ButtonStyle.secondary,
            emoji="☑️",
            row=4
        )

    async def callback(self, interaction: discord.Interaction):
        view: SkillDeckView = self.view

        if len(view.selected_slots) == SKILL_DECK_SIZE:
            view.selected_slots.clear()
            msg = "모든 슬롯 선택 해제"
        else:
            view.selected_slots = set(range(SKILL_DECK_SIZE))
            msg = "모든 슬롯 선택됨 (스킬을 선택하면 일괄 적용)"

        view._update_slot_buttons()

        embed = view.create_embed()
        embed.add_field(name="☑️ " + msg, value="\u200b", inline=False)

        await interaction.response.edit_message(embed=embed, view=view)


class FillAllButton(discord.ui.Button):
    """선택한 스킬로 전체 채우기"""

    def __init__(self):
        super().__init__(
            label="전체 채우기",
            style=discord.ButtonStyle.secondary,
            emoji="📋",
            row=4
        )

    async def callback(self, interaction: discord.Interaction):
        view: SkillDeckView = self.view

        if view.selected_slots:
            first_slot = min(view.selected_slots)
            skill_id = view.current_deck[first_slot]
            if skill_id != 0:
                view.current_deck = [skill_id] * SKILL_DECK_SIZE
                view.changes_made = True
                view.selected_slots.clear()
                view._update_slot_buttons()

                skill_name = view._get_skill_name(skill_id)
                embed = view.create_embed()
                embed.add_field(
                    name="📋 전체 채우기 완료",
                    value=f"모든 슬롯을 **{skill_name}**으로 채웠습니다.",
                    inline=False
                )
                await interaction.response.edit_message(embed=embed, view=view)
                return

        await interaction.response.send_message(
            "💡 먼저 슬롯을 선택하세요. 해당 슬롯의 스킬로 전체를 채웁니다.",
            ephemeral=True
        )


class SaveDeckButton(discord.ui.Button):
    """덱 확정 버튼"""

    def __init__(self):
        super().__init__(
            label="확정",
            style=discord.ButtonStyle.success,
            emoji="✅",
            row=4
        )

    async def callback(self, interaction: discord.Interaction):
        from service.session import get_session

        view: SkillDeckView = self.view

        session = get_session(interaction.user.id)
        if session and session.in_combat:
            await interaction.response.send_message(
                "⚠️ 전투 중에는 덱을 변경할 수 없습니다!",
                ephemeral=True
            )
            return

        filled_count = 0
        for i in range(len(view.current_deck)):
            if view.current_deck[i] == 0:
                view.current_deck[i] = SKILL_ID.BASIC_ATTACK_ID
                filled_count += 1

        view.saved = True
        view.stop()

        message = "✅ 스킬 덱이 저장되었습니다!"
        if filled_count > 0:
            message += f"\n💡 빈 슬롯 {filled_count}개를 기본 스킬(강타)로 채웠습니다."

        await interaction.response.edit_message(
            content=message,
            embed=None,
            view=None
        )


class CancelButton(discord.ui.Button):
    """취소 버튼"""

    def __init__(self):
        super().__init__(
            label="취소",
            style=discord.ButtonStyle.danger,
            emoji="❌",
            row=4
        )

    async def callback(self, interaction: discord.Interaction):
        view: SkillDeckView = self.view
        view.saved = False
        view.stop()

        await interaction.response.edit_message(
            content="❌ 덱 편집이 취소되었습니다.",
            embed=None,
            view=None
        )
