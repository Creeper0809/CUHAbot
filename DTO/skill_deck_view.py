"""
스킬 덱 편집 UI

스킬 덱을 확인하고 편집할 수 있는 Discord View 컴포넌트입니다.
커스텀 프리셋 저장/불러오기 기능을 포함합니다.
"""
import discord
from typing import Optional, List, Set

from config import SKILL_DECK_SIZE, EmbedColor
from models.repos.static_cache import skill_cache_by_id
from models.user_deck_preset import UserDeckPreset
from service.session import get_session


# =============================================================================
# 프리셋 이름 입력 Modal
# =============================================================================

class PresetNameModal(discord.ui.Modal):
    """프리셋 이름 입력 Modal"""

    name_input = discord.ui.TextInput(
        label="프리셋 이름",
        placeholder="예: 보스전용, 파밍덱",
        min_length=1,
        max_length=20,
        required=True
    )

    def __init__(self, view: "SkillDeckView"):
        super().__init__(title="💾 프리셋 저장")
        self.deck_view = view

    async def on_submit(self, interaction: discord.Interaction):
        preset_name = self.name_input.value.strip()

        # 프리셋 개수 체크
        existing_count = await UserDeckPreset.filter(
            user_id=self.deck_view.db_user.id
        ).count()

        max_presets = UserDeckPreset.get_max_presets()

        # 같은 이름 있으면 덮어쓰기
        existing = await UserDeckPreset.get_or_none(
            user_id=self.deck_view.db_user.id,
            name=preset_name
        )

        if existing:
            # 덮어쓰기
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
            # 새로 생성
            await UserDeckPreset.create_from_deck(
                user=self.deck_view.db_user,
                name=preset_name,
                deck=self.deck_view.current_deck
            )
            message = f"✅ **{preset_name}** 프리셋이 저장되었습니다!"

        # 프리셋 드롭다운 업데이트
        await self.deck_view._refresh_preset_dropdown()

        embed = self.deck_view.create_embed()
        embed.add_field(name="저장 완료", value=message, inline=False)

        await interaction.response.edit_message(embed=embed, view=self.deck_view)


# =============================================================================
# 커스텀 프리셋 드롭다운
# =============================================================================

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

        # 프리셋 적용
        view.current_deck = preset.get_deck_list()
        view.changes_made = True

        # UI 업데이트
        view._update_slot_buttons()

        embed = view.create_embed()
        embed.add_field(
            name="✅ 프리셋 불러옴",
            value=f"**{preset.name}** 프리셋이 적용되었습니다.\n확정 버튼을 눌러 저장하세요.",
            inline=False
        )

        await interaction.response.edit_message(embed=embed, view=view)


# =============================================================================
# 스킬 선택 드롭다운
# =============================================================================

class SkillSelectDropdown(discord.ui.Select):
    """스킬 선택 드롭다운"""

    def __init__(self, available_skills: list):
        options = []

        if not available_skills:
            options.append(
                discord.SelectOption(
                    label="스킬 없음",
                    description="등록된 스킬이 없습니다",
                    value="0"
                )
            )
        else:
            for skill in available_skills[:25]:
                options.append(
                    discord.SelectOption(
                        label=skill.name,
                        description=skill.description[:50] if skill.description else "설명 없음",
                        value=str(skill.id)
                    )
                )

        super().__init__(
            placeholder="🔧 스킬 선택 (선택한 슬롯에 적용)",
            options=options,
            row=1
        )

    async def callback(self, interaction: discord.Interaction):
        view: SkillDeckView = self.view
        skill_id = int(self.values[0])

        if not view.selected_slots:
            await interaction.response.send_message(
                "💡 먼저 슬롯 버튼을 클릭하세요! (여러 개 선택 가능)",
                ephemeral=True
            )
            return

        # 선택된 모든 슬롯에 스킬 적용
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


# =============================================================================
# 슬롯 버튼 (1~10)
# =============================================================================

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

        # 토글 방식: 이미 선택되어 있으면 해제, 아니면 추가
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


# =============================================================================
# 액션 버튼들
# =============================================================================

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
        view: SkillDeckView = self.view

        # 빈 슬롯 체크
        empty_slots = sum(1 for s in view.current_deck if s == 0)
        if empty_slots > 0:
            await interaction.response.send_message(
                f"⚠️ 모든 슬롯을 채운 후 저장하세요! (빈 슬롯: {empty_slots}개)",
                ephemeral=True
            )
            return

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
        view: SkillDeckView = self.view

        # 삭제할 프리셋 선택 view 표시
        presets = await UserDeckPreset.filter(user_id=view.db_user.id)

        if not presets:
            await interaction.response.send_message(
                "삭제할 프리셋이 없습니다.",
                ephemeral=True
            )
            return

        # 삭제 선택 드롭다운
        delete_view = DeletePresetView(view, list(presets))
        await interaction.response.send_message(
            "🗑️ 삭제할 프리셋을 선택하세요:",
            view=delete_view,
            ephemeral=True
        )


class SelectAllButton(discord.ui.Button):
    """전체 선택/해제 토글"""

    def __init__(self):
        super().__init__(
            label="전체 선택",
            style=discord.ButtonStyle.secondary,
            emoji="☑️",
            row=4
        )

    async def callback(self, interaction: discord.Interaction):
        view: SkillDeckView = self.view

        # 전부 선택되어 있으면 해제, 아니면 전체 선택
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
            # 첫 번째 선택된 슬롯의 스킬로 전체 채우기
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
        view: SkillDeckView = self.view

        session = get_session(interaction.user.id)
        if session and session.in_combat:
            await interaction.response.send_message(
                "⚠️ 전투 중에는 덱을 변경할 수 없습니다!",
                ephemeral=True
            )
            return

        empty_slots = sum(1 for s in view.current_deck if s == 0)
        if empty_slots > 0:
            await interaction.response.send_message(
                f"⚠️ 모든 슬롯을 채워야 합니다! (빈 슬롯: {empty_slots}개)",
                ephemeral=True
            )
            return

        view.saved = True
        view.stop()

        await interaction.response.edit_message(
            content="✅ 스킬 덱이 저장되었습니다!",
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


# =============================================================================
# 프리셋 삭제 View
# =============================================================================

class DeletePresetView(discord.ui.View):
    """프리셋 삭제 선택 View"""

    def __init__(self, parent_view: "SkillDeckView", presets: List[UserDeckPreset]):
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

            # 부모 view 업데이트
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


# =============================================================================
# 메인 View
# =============================================================================

class SkillDeckView(discord.ui.View):
    """
    스킬 덱 편집 View

    기능:
    - 커스텀 프리셋 저장/불러오기/삭제
    - 슬롯 버튼으로 빠른 선택
    - 전체 채우기
    """

    def __init__(
        self,
        user: discord.User,
        current_deck: list[int],
        available_skills: list,
        db_user=None,
        timeout: int = 180
    ):
        super().__init__(timeout=timeout)

        self.user = user
        self.db_user = db_user
        self.current_deck = current_deck.copy()

        while len(self.current_deck) < SKILL_DECK_SIZE:
            self.current_deck.append(0)

        self.available_skills = available_skills
        self.selected_slots: Set[int] = set()  # 멀티 선택 지원
        self.saved = False
        self.changes_made = False
        self.message: Optional[discord.Message] = None
        self.presets: List[UserDeckPreset] = []

    async def initialize(self):
        """비동기 초기화 (프리셋 로드)"""
        if self.db_user:
            self.presets = list(await UserDeckPreset.filter(user_id=self.db_user.id))

        # 컴포넌트 추가
        self.add_item(CustomPresetDropdown(self.presets))
        self.add_item(SkillSelectDropdown(self.available_skills))
        self._add_slot_buttons()
        # Row 4: 5개 버튼
        self.add_item(SelectAllButton())   # 전체 선택
        self.add_item(FillAllButton())     # 전체 채우기
        self.add_item(SavePresetButton())  # 프리셋 저장
        self.add_item(SaveDeckButton())    # 확정
        self.add_item(CancelButton())      # 취소

    async def _refresh_preset_dropdown(self):
        """프리셋 드롭다운 새로고침"""
        if self.db_user:
            self.presets = list(await UserDeckPreset.filter(user_id=self.db_user.id))

        # 기존 프리셋 드롭다운 제거
        to_remove = [item for item in self.children if isinstance(item, CustomPresetDropdown)]
        for item in to_remove:
            self.remove_item(item)

        # 새 드롭다운을 맨 앞에 추가하기 위해 전체 재구성
        new_children = [CustomPresetDropdown(self.presets)]
        for child in self.children:
            new_children.append(child)

        self.clear_items()
        for child in new_children:
            self.add_item(child)

    def _add_slot_buttons(self):
        """슬롯 버튼 추가"""
        for i in range(SKILL_DECK_SIZE):
            skill_name = self._get_skill_name(self.current_deck[i])
            is_selected = (i in self.selected_slots)
            self.add_item(SlotButton(i, skill_name, is_selected))

    def _update_slot_buttons(self):
        """슬롯 버튼 업데이트"""
        to_remove = [item for item in self.children if isinstance(item, SlotButton)]
        for item in to_remove:
            self.remove_item(item)
        self._add_slot_buttons()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.user:
            await interaction.response.send_message(
                "이 덱은 다른 사용자의 것입니다.",
                ephemeral=True
            )
            return False

        session = get_session(interaction.user.id)
        if session and session.in_combat:
            await interaction.response.send_message(
                "⚠️ 전투 중에는 덱을 변경할 수 없습니다!",
                ephemeral=True
            )
            return False

        return True

    def create_embed(self) -> discord.Embed:
        """현재 덱 상태 임베드 생성"""
        embed = discord.Embed(
            title="⚔️ 스킬 덱 편집",
            description=(
                "**프리셋**: 드롭다운에서 불러오기 / 💾버튼으로 저장\n"
                "**개별 편집**: 슬롯 버튼 클릭 (여러 개 선택 가능) → 스킬 선택\n"
                "**전체 채우기**: 슬롯 선택 후 📋버튼"
            ),
            color=EmbedColor.DEFAULT
        )

        # 저장된 프리셋 개수 표시
        preset_count = len(self.presets)
        max_presets = UserDeckPreset.get_max_presets()
        embed.add_field(
            name="📁 내 프리셋",
            value=f"{preset_count}/{max_presets}개 저장됨",
            inline=True
        )

        # 선택된 슬롯 표시
        if self.selected_slots:
            slot_list = ", ".join(str(s + 1) for s in sorted(self.selected_slots))
            embed.add_field(
                name="🎯 선택됨",
                value=f"[{slot_list}]",
                inline=True
            )
        else:
            embed.add_field(name="\u200b", value="\u200b", inline=True)

        embed.add_field(name="\u200b", value="\u200b", inline=True)

        # 덱 시각화
        left_deck = []
        right_deck = []
        skill_counts = {}

        for i, skill_id in enumerate(self.current_deck):
            skill_name = self._get_skill_name(skill_id)
            marker = "▶ " if i in self.selected_slots else ""
            line = f"`{i + 1:2d}` {marker}{skill_name}"

            if i < 5:
                left_deck.append(line)
            else:
                right_deck.append(line)

            if skill_id != 0:
                skill_counts[skill_name] = skill_counts.get(skill_name, 0) + 1

        embed.add_field(
            name="슬롯 1-5",
            value="\n".join(left_deck),
            inline=True
        )

        embed.add_field(
            name="슬롯 6-10",
            value="\n".join(right_deck),
            inline=True
        )

        # 발동 확률
        if skill_counts:
            prob_display = []
            for name, count in sorted(skill_counts.items(), key=lambda x: -x[1]):
                prob = count * 10
                bar = "█" * count + "░" * (10 - count)
                prob_display.append(f"{bar} {name}: **{prob}%**")

            embed.add_field(
                name="🎲 발동 확률",
                value="\n".join(prob_display[:5]),
                inline=False
            )

        return embed

    def _get_skill_name(self, skill_id: int) -> str:
        if skill_id == 0:
            return "❌ 비어있음"
        skill = skill_cache_by_id.get(skill_id)
        return skill.name if skill else f"?? (#{skill_id})"

    async def on_timeout(self):
        if self.message:
            try:
                await self.message.edit(
                    content="⏰ 시간 초과로 덱 편집이 취소되었습니다.",
                    embed=None,
                    view=None
                )
            except discord.NotFound:
                pass
