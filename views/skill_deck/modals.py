"""
스킬 덱 Modal 컴포넌트

프리셋 이름 입력, 스킬 검색 필터 등의 Modal을 정의합니다.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import discord

from config import SKILL_ID
from models.user_deck_preset import UserDeckPreset

if TYPE_CHECKING:
    from views.skill_deck.main import SkillDeckView


class PresetNameModal(discord.ui.Modal):
    """프리셋 이름 입력 Modal"""

    name_input = discord.ui.TextInput(
        label="프리셋 이름",
        placeholder="예: 보스전용, 파밍덱",
        min_length=1,
        max_length=20,
        required=True
    )

    def __init__(self, view: SkillDeckView):
        super().__init__(title="💾 프리셋 저장")
        self.deck_view = view

    async def on_submit(self, interaction: discord.Interaction):
        preset_name = self.name_input.value.strip()

        existing_count = await UserDeckPreset.filter(
            user_id=self.deck_view.db_user.id
        ).count()

        max_presets = UserDeckPreset.get_max_presets()

        existing = await UserDeckPreset.get_or_none(
            user_id=self.deck_view.db_user.id,
            name=preset_name
        )

        if existing:
            for i, skill_id in enumerate(self.deck_view.current_deck):
                setattr(existing, f"slot_{i}", skill_id)
            await existing.save()
            message = f"✅ **{preset_name}** 프리셋을 덮어썼습니다!"
        elif existing_count >= max_presets:
            await interaction.response.send_message(
                f"⚠️ 프리셋은 최대 {max_presets}개까지 저장 가능합니다.\n"
                f"기존 프리셋을 삭제하거나 같은 이름으로 덮어쓰세요.",
                ephemeral=True
            )
            return
        else:
            await UserDeckPreset.create_from_deck(
                user=self.deck_view.db_user,
                name=preset_name,
                deck=self.deck_view.current_deck
            )
            message = f"✅ **{preset_name}** 프리셋이 저장되었습니다!"

        await self.deck_view._refresh_preset_dropdown()

        embed = self.deck_view.create_embed()
        embed.add_field(name="저장 완료", value=message, inline=False)

        await interaction.response.edit_message(embed=embed, view=self.deck_view)


class SkillFilterModal(discord.ui.Modal):
    """스킬 필터링 Modal"""

    search_input = discord.ui.TextInput(
        label="스킬 이름 검색",
        placeholder="검색어 입력 (예: 강타, 회복) - 비우면 전체 표시",
        min_length=0,
        max_length=50,
        required=False
    )

    def __init__(self, view: SkillDeckView):
        super().__init__(title="🔍 스킬 필터")
        self.deck_view = view

    async def on_submit(self, interaction: discord.Interaction):
        search_term = self.search_input.value.strip().lower()

        if search_term:
            filtered = [
                skill for skill in self.deck_view.available_skills
                if search_term in skill.name.lower()
            ]
        else:
            filtered = self.deck_view.available_skills

        if not filtered:
            await interaction.response.send_message(
                f"❌ '{self.search_input.value}'와 일치하는 스킬이 없습니다.",
                ephemeral=True
            )
            return

        self.deck_view.filtered_skills = filtered
        self.deck_view._update_skill_dropdown()

        embed = self.deck_view.create_embed()
        filter_text = f"'{self.search_input.value}'" if search_term else "전체"
        embed.add_field(
            name="🔍 필터 적용",
            value=f"{filter_text} 검색: {len(filtered)}개 스킬",
            inline=False
        )

        await interaction.response.edit_message(embed=embed, view=self.deck_view)
