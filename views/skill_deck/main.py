"""
스킬 덱 편집 메인 View

SkillDeckView 클래스를 정의합니다.
"""
from typing import Dict, List, Optional, Set

import discord

from config import SKILL_DECK_SIZE, SKILL_ID, EmbedColor
from models.repos.static_cache import skill_cache_by_id
from models.user_deck_preset import UserDeckPreset
from models.user_owned_skill import UserOwnedSkill
from service.session import get_session
from service.tower.tower_restriction import enforce_skill_change_restriction
from utils.grade_display import format_skill_name

from views.skill_deck.dropdowns import CustomPresetDropdown, SkillSelectDropdown
from views.skill_deck.buttons import (
    SlotButton, SearchSkillButton, SelectAllButton,
    SavePresetButton, SaveDeckButton, CancelButton,
)


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
        skill_quantities: Dict[int, UserOwnedSkill] = None,
        timeout: int = 180
    ):
        super().__init__(timeout=timeout)

        self.user = user
        self.db_user = db_user
        self.current_deck = current_deck.copy()
        self.original_deck = current_deck.copy()

        while len(self.current_deck) < SKILL_DECK_SIZE:
            self.current_deck.append(0)

        self.available_skills = available_skills
        self.filtered_skills = available_skills[:25]
        self.skill_quantities = skill_quantities or {}
        self.selected_slots: Set[int] = set()
        self.saved = False
        self.changes_made = False
        self.message: Optional[discord.Message] = None
        self.presets: List[UserDeckPreset] = []

    async def initialize(self):
        """비동기 초기화 (프리셋 로드)"""
        if self.db_user:
            self.presets = list(await UserDeckPreset.filter(user_id=self.db_user.id))

        self.add_item(CustomPresetDropdown(self.presets))
        self.add_item(SkillSelectDropdown(self.filtered_skills, self.skill_quantities))
        self._add_slot_buttons()
        self.add_item(SearchSkillButton())
        self.add_item(SelectAllButton())
        self.add_item(SavePresetButton())
        self.add_item(SaveDeckButton())
        self.add_item(CancelButton())

    def _update_skill_dropdown(self):
        """스킬 드롭다운 업데이트 (필터링 적용)"""
        to_remove = [item for item in self.children if isinstance(item, SkillSelectDropdown)]
        for item in to_remove:
            self.remove_item(item)

        new_dropdown = SkillSelectDropdown(self.filtered_skills[:25], self.skill_quantities)

        preset_idx = 0
        for i, child in enumerate(self.children):
            if isinstance(child, CustomPresetDropdown):
                preset_idx = i + 1
                break

        children_list = list(self.children)
        children_list.insert(preset_idx, new_dropdown)

        self.clear_items()
        for child in children_list:
            self.add_item(child)

    async def _refresh_preset_dropdown(self):
        """프리셋 드롭다운 새로고침"""
        if self.db_user:
            self.presets = list(await UserDeckPreset.filter(user_id=self.db_user.id))

        to_remove = [item for item in self.children if isinstance(item, CustomPresetDropdown)]
        for item in to_remove:
            self.remove_item(item)

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

        try:
            enforce_skill_change_restriction(session)
        except Exception as e:
            await interaction.response.send_message(f"⚠️ {e}", ephemeral=True)
            return False

        return True

    def create_embed(self) -> discord.Embed:
        """현재 덱 상태 임베드 생성"""
        embed = discord.Embed(
            title="⚔️ 스킬 덱 편집",
            description=(
                "**스킬 장착**: 슬롯 클릭 → 드롭다운에서 스킬 선택\n"
                "**스킬 검색**: 🔍검색 버튼으로 드롭다운 필터링\n"
                "**일괄 장착**: ☑️전체 선택 → 스킬 선택"
            ),
            color=EmbedColor.DEFAULT
        )

        self._add_preset_info(embed)
        self._add_filter_info(embed)
        self._add_selected_slots_info(embed)
        self._add_deck_visualization(embed)
        self._add_link_probability_info(embed)
        self._add_synergy_info(embed)

        return embed

    def _add_preset_info(self, embed: discord.Embed) -> None:
        """프리셋 정보 필드"""
        preset_count = len(self.presets)
        max_presets = UserDeckPreset.get_max_presets()
        embed.add_field(
            name="📁 내 프리셋",
            value=f"{preset_count}/{max_presets}개 저장됨",
            inline=True
        )

    def _add_filter_info(self, embed: discord.Embed) -> None:
        """필터링 정보 필드"""
        embed.add_field(
            name="📜 스킬",
            value=f"{len(self.filtered_skills)}/{len(self.available_skills)}개 표시",
            inline=True
        )

    def _add_selected_slots_info(self, embed: discord.Embed) -> None:
        """선택된 슬롯 필드"""
        if self.selected_slots:
            slot_list = ", ".join(str(s + 1) for s in sorted(self.selected_slots))
            embed.add_field(name="🎯 선택됨", value=f"[{slot_list}]", inline=True)
        else:
            embed.add_field(name="\u200b", value="\u200b", inline=True)

    def _add_deck_visualization(self, embed: discord.Embed) -> None:
        """덱 시각화 + 발동 확률 (패시브 제외)"""
        left_deck = []
        right_deck = []
        skill_counts = {}
        active_slot_count = 0

        for i, skill_id in enumerate(self.current_deck):
            skill_name = self._get_skill_name(skill_id)
            marker = "▶ " if i in self.selected_slots else ""
            line = f"`{i + 1:2d}` {marker}{skill_name}"

            if i < 5:
                left_deck.append(line)
            else:
                right_deck.append(line)

            if skill_id != 0:
                skill = skill_cache_by_id.get(skill_id)
                if skill and skill.is_passive:
                    continue
                skill_counts[skill_name] = skill_counts.get(skill_name, 0) + 1
                active_slot_count += 1

        embed.add_field(name="슬롯 1-5", value="\n".join(left_deck), inline=True)
        embed.add_field(name="슬롯 6-10", value="\n".join(right_deck), inline=True)

        if skill_counts:
            prob_display = []
            for name, count in sorted(skill_counts.items(), key=lambda x: -x[1]):
                prob = (count / active_slot_count * 100) if active_slot_count > 0 else 0
                bar_filled = round(count / active_slot_count * 10) if active_slot_count > 0 else 0
                bar = "█" * bar_filled + "░" * (10 - bar_filled)
                prob_display.append(f"{bar} {name}: **{prob:.0f}%**")

            embed.add_field(
                name="🎲 발동 확률",
                value="\n".join(prob_display[:5]),
                inline=False
            )

    def _add_link_probability_info(self, embed: discord.Embed) -> None:
        """Show shuffle-bag setup/payoff odds without changing player order."""
        from service.skill.design_v3 import deck_link_summary

        configs = {
            skill_id: skill.skill_model.config or {}
            for skill_id, skill in skill_cache_by_id.items()
        }
        links = deck_link_summary(self.current_deck, configs)
        if not links:
            return
        lines = []
        for link in links[:8]:
            setup = link["setup_copies"]
            payoff = link["payoff_copies"]
            if setup and payoff:
                chance = link["first_link_probability"] * 100
                lines.append(f"• **{link['tag']}** 생성 {setup} / 소비 {payoff} · 첫 연계 {chance:.0f}%")
            elif setup:
                lines.append(f"• **{link['tag']}** 생성 {setup} / 소비기 없음")
            else:
                lines.append(f"• **{link['tag']}** 생성기 없음 / 소비 {payoff} ⚠️")
        embed.add_field(
            name="🔗 셔플 연계 구성",
            value="\n".join(lines),
            inline=False,
        )

    def _add_synergy_info(self, embed: discord.Embed) -> None:
        """시너지 요약 필드"""
        from config import ATTRIBUTE_SYNERGIES, EFFECT_SYNERGIES
        from service.skill.synergy_service import SynergyService
        active_synergies = SynergyService.get_active_synergies(self.current_deck)

        if not active_synergies:
            return

        attr_keys = set(ATTRIBUTE_SYNERGIES.keys())
        effect_keys = set(EFFECT_SYNERGIES.keys())
        attr_lines = []
        effect_lines = []
        combo_lines = []

        for synergy in active_synergies:
            if synergy.combo:
                combo_lines.append(f"• {synergy.name}: {synergy.description}")
                continue

            key = synergy.name.split(" ×", 1)[0]
            line = f"• {synergy.name}: {synergy.description}"
            if key in attr_keys:
                attr_lines.append(line)
            elif key in effect_keys:
                effect_lines.append(line)
            else:
                combo_lines.append(line)

        summary_lines = []
        if attr_lines:
            summary_lines.append("**속성 밀도**")
            summary_lines.extend(attr_lines[:4])
        if effect_lines:
            summary_lines.append("**효과 밀도**")
            summary_lines.extend(effect_lines[:4])
        if combo_lines:
            summary_lines.append("**조합 시너지**")
            summary_lines.extend(combo_lines[:4])

        embed.add_field(
            name=f"🔮 시너지 ({len(active_synergies)}개)",
            value="\n".join(summary_lines[:14]),
            inline=False,
        )

    def _get_skill_name(self, skill_id: int) -> str:
        if skill_id == 0:
            return "❌ 비어있음"
        skill = skill_cache_by_id.get(skill_id)
        if skill:
            grade_id = skill.skill_model.grade
            return format_skill_name(skill.name, grade_id)
        return f"?? (#{skill_id})"

    def _check_skill_availability(self, skill_id: int, slots_needed: int) -> tuple[bool, str]:
        """스킬 장착 가능 여부 확인"""
        if skill_id == SKILL_ID.BASIC_ATTACK_ID:
            return True, ""

        selected_skill = skill_cache_by_id.get(skill_id)
        if selected_skill and selected_skill.is_passive:
            non_selected_passives = sum(
                1 for i, sid in enumerate(self.current_deck)
                if sid == skill_id and i not in self.selected_slots
            )
            if non_selected_passives:
                return False, "같은 패시브는 중복 적용되지 않아 한 장만 편성할 수 있습니다."

        owned = self.skill_quantities.get(skill_id)
        if not owned:
            skill_name = self._get_skill_name(skill_id)
            return False, f"'{skill_name}' 스킬을 보유하고 있지 않습니다."

        non_selected_usage = sum(
            1 for i, sid in enumerate(self.current_deck)
            if sid == skill_id and i not in self.selected_slots
        )

        available = owned.quantity - non_selected_usage

        if available < slots_needed:
            skill_name = self._get_skill_name(skill_id)
            return False, (
                f"'{skill_name}' 스킬이 부족합니다.\n"
                f"필요: {slots_needed}개, 사용 가능: {available}개"
            )

        return True, ""

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
