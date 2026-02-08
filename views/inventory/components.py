"""
인벤토리 공통 컴포넌트

정렬 타입, 아이템 드롭다운, 탭/정렬/검색 버튼 등 공통 UI 컴포넌트를 정의합니다.
"""
from __future__ import annotations

from enum import Enum
from typing import List, Optional, TYPE_CHECKING

import discord

from models.user_inventory import UserInventory
from resources.item_emoji import ItemType
from utils.grade_display import format_item_name

if TYPE_CHECKING:
    from views.inventory.list_view import InventoryView
    from views.inventory.select_view import InventorySelectView


class SortType(Enum):
    """정렬 타입"""
    GRADE = "등급"
    NAME = "이름"
    QUANTITY = "수량"
    NONE = "기본"


class ItemSelectDropdown(discord.ui.Select):
    """아이템 선택 드롭다운"""

    def __init__(self, items: List[UserInventory]):
        options = []

        for inv in items[:25]:
            if inv.item.type == ItemType.SKILL:
                continue

            emoji = self._get_type_emoji(inv.item.type)
            enhance = f" +{inv.enhancement_level}" if inv.enhancement_level > 0 else ""
            qty = f" x{inv.quantity}" if inv.quantity > 1 else ""

            instance_grade = getattr(inv, 'instance_grade', 0)
            formatted_name = format_item_name(inv.item.name, instance_grade if instance_grade > 0 else None)

            # 상자 아이템이면 저장된 던전 레벨 범위 표시
            from config import BOX_CONFIGS
            if inv.item.id in BOX_CONFIGS and instance_grade > 0:
                from models.repos.static_cache import get_previous_dungeon_level
                prev_level = get_previous_dungeon_level(instance_grade)
                formatted_name = f"{formatted_name}({prev_level}~{instance_grade}Lv)"

            options.append(
                discord.SelectOption(
                    label=f"{formatted_name}{enhance}{qty}",
                    description=inv.item.description[:50] if inv.item.description else "설명 없음",
                    value=str(inv.id),
                    emoji=emoji
                )
            )

        if not options:
            options.append(
                discord.SelectOption(
                    label="사용 가능한 아이템 없음",
                    value="0"
                )
            )

        super().__init__(
            placeholder="🎒 아이템 선택",
            options=options,
            row=0
        )

    @staticmethod
    def _get_type_emoji(item_type) -> str:
        """아이템 타입별 이모지"""
        if item_type == ItemType.EQUIP:
            return "⚔️"
        elif item_type == ItemType.CONSUME:
            return "🧪"
        return "📦"

    async def callback(self, interaction: discord.Interaction):
        view: InventorySelectView = self.view
        item_id = int(self.values[0])

        if item_id == 0:
            await interaction.response.send_message(
                "사용 가능한 아이템이 없습니다.",
                ephemeral=True
            )
            return

        view.selected_item_id = item_id

        selected_inv = await UserInventory.get_or_none(id=item_id).prefetch_related("item")

        view.selected_inventory_item = selected_inv
        embed = view.create_embed()
        await interaction.response.edit_message(embed=embed, view=view)


class TabButton(discord.ui.Button):
    """탭 전환 버튼"""

    def __init__(self, label: str, tab_type: ItemType, is_active: bool = False):
        style = discord.ButtonStyle.primary if is_active else discord.ButtonStyle.secondary
        super().__init__(label=label, style=style, row=0)
        self.tab_type = tab_type

    async def callback(self, interaction: discord.Interaction):
        view: InventoryView = self.view

        view.current_tab = self.tab_type
        view.inventory = view._filter_and_sort()
        view.page = 0
        view.total_pages = max(1, (len(view.inventory) + view.items_per_page - 1) // view.items_per_page)

        view._update_tab_buttons()

        embed = view.create_embed()
        await interaction.response.edit_message(embed=embed, view=view)


class SortButton(discord.ui.Button):
    """정렬 버튼 (클릭 시 순환)"""

    def __init__(self):
        super().__init__(
            label="정렬: 기본",
            style=discord.ButtonStyle.secondary,
            emoji="🔄",
            row=0
        )

    async def callback(self, interaction: discord.Interaction):
        view: InventoryView = self.view

        sort_cycle = [SortType.NONE, SortType.GRADE, SortType.NAME, SortType.QUANTITY]
        current_index = sort_cycle.index(view.current_sort)
        next_index = (current_index + 1) % len(sort_cycle)
        view.current_sort = sort_cycle[next_index]

        view.inventory = view._filter_and_sort()
        view.page = 0
        view.total_pages = max(1, (len(view.inventory) + view.items_per_page - 1) // view.items_per_page)

        self.label = f"정렬: {view.current_sort.value}"

        embed = view.create_embed()
        await interaction.response.edit_message(embed=embed, view=view)


class SearchButton(discord.ui.Button):
    """검색 버튼 (모달 열기)"""

    def __init__(self):
        super().__init__(
            label="검색",
            style=discord.ButtonStyle.secondary,
            emoji="🔍",
            row=0
        )

    async def callback(self, interaction: discord.Interaction):
        modal = SearchModal(self.view)
        await interaction.response.send_modal(modal)


class SearchModal(discord.ui.Modal, title="아이템 검색"):
    """검색 모달"""

    search_input = discord.ui.TextInput(
        label="검색어",
        placeholder="아이템 이름을 입력하세요 (비우면 검색 해제)",
        required=False,
        max_length=50
    )

    def __init__(self, view: InventoryView):
        super().__init__()
        self.view = view
        if view.search_query:
            self.search_input.default = view.search_query

    async def on_submit(self, interaction: discord.Interaction):
        query = self.search_input.value.strip()
        self.view.search_query = query if query else None

        self.view.inventory = self.view._filter_and_sort()
        self.view.page = 0
        self.view.total_pages = max(1, (len(self.view.inventory) + self.view.items_per_page - 1) // self.view.items_per_page)

        embed = self.view.create_embed()
        if query:
            embed.set_footer(text=f"🔍 검색: '{query}' | 아이템 사용 버튼 → 선택 창에서 사용")
        await interaction.response.edit_message(embed=embed, view=self.view)
