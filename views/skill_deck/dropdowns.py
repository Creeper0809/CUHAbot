"""
스킬 덱 드롭다운 컴포넌트

커스텀 프리셋 선택, 스킬 선택 드롭다운을 정의합니다.
"""
from __future__ import annotations

from typing import Dict, List, TYPE_CHECKING

import discord

from config import SKILL_ID
from models.repos.static_cache import skill_cache_by_id
from models.user_deck_preset import UserDeckPreset
from models.user_owned_skill import UserOwnedSkill

if TYPE_CHECKING:
    from views.skill_deck.main import SkillDeckView


class CustomPresetDropdown(discord.ui.Select):
    """커스텀 프리셋 선택 드롭다운"""

    def __init__(self, presets: List[UserDeckPreset]):
        self.presets = presets

        if not presets:
            options = [
                discord.SelectOption(
                    label="저장된 프리셋 없음",
                    description="아래 '💾 저장' 버튼으로 현재 덱을 저장하세요",
                    value="__none__"
                )
            ]
        else:
            options = []
            for preset in presets:
                deck = preset.get_deck_list()
                skill_names = []
                for sid in deck[:3]:
                    skill = skill_cache_by_id.get(sid)
                    if skill:
                        skill_names.append(skill.name)
                preview = ", ".join(skill_names) + "..." if skill_names else "덱 미리보기"

                options.append(
                    discord.SelectOption(
                        label=f"📁 {preset.name}",
                        description=preview[:50],
                        value=str(preset.id)
                    )
                )

        super().__init__(
            placeholder="📂 내 프리셋 불러오기",
            options=options,
            row=0
        )

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "__none__":
            await interaction.response.send_message(
                "💡 현재 덱을 저장하려면 '💾 저장' 버튼을 누르세요!",
                ephemeral=True
            )
            return

        view: SkillDeckView = self.view
        preset_id = int(self.values[0])

        preset = await UserDeckPreset.get_or_none(id=preset_id)
        if not preset:
            await interaction.response.send_message("프리셋을 찾을 수 없습니다.", ephemeral=True)
            return

        view.current_deck = preset.get_deck_list()
        view.changes_made = True

        view._update_slot_buttons()

        embed = view.create_embed()
        embed.add_field(
            name="✅ 프리셋 불러옴",
            value=f"**{preset.name}** 프리셋이 적용되었습니다.\n확정 버튼을 눌러 저장하세요.",
            inline=False
        )

        await interaction.response.edit_message(embed=embed, view=view)


class SkillSelectDropdown(discord.ui.Select):
    """스킬 선택 드롭다운 (필터링된 스킬 표시, 수량 포함)"""

    def __init__(self, skills: list, skill_quantities: Dict[int, UserOwnedSkill] = None):
        options = []
        skill_quantities = skill_quantities or {}

        if not skills:
            options.append(
                discord.SelectOption(
                    label="스킬 없음",
                    description="🔍 검색으로 필터링하세요",
                    value="0"
                )
            )
        else:
            for skill in skills[:25]:
                owned = skill_quantities.get(skill.id)
                if owned:
                    qty_info = f"[보유:{owned.quantity} 장착:{owned.equipped_count}] "
                else:
                    qty_info = "[미보유] "

                desc = skill.description[:40] if skill.description else "설명 없음"
                options.append(
                    discord.SelectOption(
                        label=skill.name,
                        description=f"{qty_info}{desc}"[:50],
                        value=str(skill.id)
                    )
                )

        super().__init__(
            placeholder=f"📜 스킬 선택 ({len(skills)}개)",
            options=options,
            row=1
        )

    async def callback(self, interaction: discord.Interaction):
        view: SkillDeckView = self.view
        skill_id = int(self.values[0])

        if skill_id == 0:
            await interaction.response.send_message(
                "💡 검색 버튼을 눌러 스킬을 필터링하세요!",
                ephemeral=True
            )
            return

        if not view.selected_slots:
            await interaction.response.send_message(
                "💡 먼저 슬롯 버튼을 클릭하세요! (여러 개 선택 가능)",
                ephemeral=True
            )
            return

        can_equip, error_msg = view._check_skill_availability(skill_id, len(view.selected_slots))
        if not can_equip:
            await interaction.response.send_message(
                f"⚠️ {error_msg}",
                ephemeral=True
            )
            return

        for slot in view.selected_slots:
            view.current_deck[slot] = skill_id
        view.changes_made = True

        skill_name = view._get_skill_name(skill_id)
        slot_count = len(view.selected_slots)
        slot_list = ", ".join(str(s + 1) for s in sorted(view.selected_slots))

        embed = view.create_embed()
        if slot_count == 1:
            embed.add_field(
                name="✅ 스킬 변경",
                value=f"슬롯 {slot_list}에 **{skill_name}** 장착!",
                inline=False
            )
        else:
            embed.add_field(
                name="✅ 스킬 일괄 변경",
                value=f"슬롯 [{slot_list}] ({slot_count}개)에 **{skill_name}** 장착!",
                inline=False
            )

        view.selected_slots.clear()
        view._update_slot_buttons()

        await interaction.response.edit_message(embed=embed, view=view)
