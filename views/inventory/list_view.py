"""
인벤토리 리스트 View

아이템 목록을 페이지 단위로 표시하는 메인 인벤토리 View를 정의합니다.
"""
from typing import List, Optional

import discord

from config import EmbedColor, UI
from models import User
from models.user_inventory import UserInventory
from resources.item_emoji import ItemType
from service.item.item_use_service import ItemUseService
from exceptions import CombatRestrictionError, ItemNotFoundError, ItemNotEquippableError
from utils.grade_display import format_item_name

from views.inventory.components import (
    SortType, ItemSelectDropdown, TabButton, SortButton, SearchButton, DescriptionButton,
)

_STAT_LABELS = {
    "attack": "ATK", "ap_attack": "MATK", "hp": "HP",
    "ad_defense": "DEF", "ap_defense": "MDEF", "speed": "SPD",
}


def _get_main_stat_text(info: dict) -> str:
    """장비 정보에서 가장 높은 스탯 1개를 텍스트로 반환"""
    best_key, best_val = "", 0
    for key, label in _STAT_LABELS.items():
        val = info.get(key) or 0
        if val > best_val:
            best_key, best_val = key, val
    if best_val > 0:
        return f"{_STAT_LABELS[best_key]} {best_val}"
    return ""


class InventoryView(discord.ui.View):
    """
    인벤토리 View

    아이템 목록을 페이지 단위로 표시하고 사용할 수 있습니다.
    """

    def __init__(
        self,
        user: discord.User,
        db_user: User,
        inventory: List[UserInventory],
        owned_skills: List = None,
        timeout: int = 120
    ):
        super().__init__(timeout=timeout)

        self.user = user
        self.db_user = db_user
        self.all_inventory = inventory
        self.owned_skills = owned_skills or []
        self.current_tab = ItemType.CONSUME
        self.current_sort = SortType.NONE
        self.search_query: Optional[str] = None
        self.inventory = self._filter_and_sort()
        self.page = 0
        self.items_per_page = UI.ITEMS_PER_PAGE
        self.total_pages = max(1, (len(self.inventory) + self.items_per_page - 1) // self.items_per_page)
        self.message: Optional[discord.Message] = None
        self.selected_item_id: Optional[int] = None

        self._add_tab_buttons()
        self._add_sort_button()
        self._add_select_button()
        self._add_enhancement_button()
        self._remove_action_buttons()

    def _get_page_items(self) -> List[UserInventory]:
        """현재 페이지 아이템 목록"""
        start = self.page * self.items_per_page
        end = start + self.items_per_page
        return self.inventory[start:end]

    def _remove_action_buttons(self) -> None:
        """리스트 뷰에서 사용 버튼 제거"""
        to_remove = [
            child for child in self.children
            if isinstance(child, discord.ui.Button) and child.label == "사용"
        ]
        for child in to_remove:
            self.remove_item(child)

    def _filter_by_tab(self) -> List:
        """현재 탭에 맞는 아이템만 필터링"""
        if self.current_tab == ItemType.CONSUME:
            return [inv for inv in self.all_inventory if inv.item.type == ItemType.CONSUME]
        elif self.current_tab == ItemType.EQUIP:
            return [inv for inv in self.all_inventory if inv.item.type == ItemType.EQUIP]
        elif self.current_tab == ItemType.ETC:
            return [inv for inv in self.all_inventory if inv.item.type == ItemType.ETC]
        elif self.current_tab == ItemType.SKILL:
            return self.owned_skills
        return self.all_inventory

    def _filter_and_sort(self) -> List:
        """탭 필터링 + 검색 + 정렬"""
        items = self._filter_by_tab()

        if self.search_query:
            items = self._apply_search_filter(items)

        if self.current_tab != ItemType.SKILL:
            items = self._apply_sort(items)

        return items

    def _apply_search_filter(self, items: List) -> List:
        """검색 필터 적용"""
        query = self.search_query.lower()
        if self.current_tab == ItemType.SKILL:
            from models.repos.static_cache import skill_cache_by_id
            return [
                inv for inv in items
                if skill_cache_by_id.get(inv.skill_id) and
                query in skill_cache_by_id.get(inv.skill_id).name.lower()
            ]
        return [inv for inv in items if query in inv.item.name.lower()]

    def _apply_sort(self, items: List) -> List:
        """정렬 적용"""
        if self.current_sort == SortType.GRADE:
            items.sort(
                key=lambda inv: getattr(inv, 'instance_grade', 0) or 0,
                reverse=True
            )
        elif self.current_sort == SortType.NAME:
            items.sort(key=lambda inv: inv.item.name)
        elif self.current_sort == SortType.QUANTITY:
            items.sort(key=lambda inv: inv.quantity, reverse=True)
        return items

    def _add_tab_buttons(self) -> None:
        """탭 버튼 추가"""
        self.add_item(TabButton("🧪 소모품", ItemType.CONSUME, is_active=(self.current_tab == ItemType.CONSUME)))
        self.add_item(TabButton("⚔️ 장비", ItemType.EQUIP, is_active=(self.current_tab == ItemType.EQUIP)))
        self.add_item(TabButton("📦 기타", ItemType.ETC, is_active=(self.current_tab == ItemType.ETC)))
        self.add_item(TabButton("📜 스킬", ItemType.SKILL, is_active=(self.current_tab == ItemType.SKILL)))

    def _add_sort_button(self) -> None:
        """정렬, 검색, 설명 버튼 추가"""
        self.add_item(SortButton())
        self.add_item(SearchButton())
        self.add_item(DescriptionButton())

    def _add_select_button(self) -> None:
        """현재 탭에서 실행 가능한 동작만 추가한다."""
        from views.inventory.select_view import InventorySelectButton
        if self.current_tab in (ItemType.CONSUME, ItemType.EQUIP, ItemType.SKILL):
            self.add_item(InventorySelectButton(self.current_tab))

    def _add_enhancement_button(self) -> None:
        """장비 탭일 때 강화 버튼 추가"""
        from views.inventory.select_view import EnhancementSelectButton
        if self.current_tab == ItemType.EQUIP:
            self.add_item(EnhancementSelectButton())

    def _remove_enhancement_button(self) -> None:
        """강화 버튼 제거"""
        from views.inventory.select_view import EnhancementSelectButton
        to_remove = [c for c in self.children if isinstance(c, EnhancementSelectButton)]
        for c in to_remove:
            self.remove_item(c)

    def _update_select_button(self) -> None:
        """아이템 선택 버튼 업데이트 (탭에 따라 라벨 변경)"""
        from views.inventory.select_view import InventorySelectButton
        to_remove = [c for c in self.children if isinstance(c, InventorySelectButton)]
        for c in to_remove:
            self.remove_item(c)
        self._add_select_button()

    def _update_tab_buttons(self) -> None:
        """탭 버튼 업데이트 (선택된 탭 강조)"""
        to_remove = [item for item in self.children if isinstance(item, TabButton)]
        for item in to_remove:
            self.remove_item(item)
        self._add_tab_buttons()

    def _update_dropdown(self):
        """드롭다운 업데이트"""
        to_remove = [item for item in self.children if isinstance(item, ItemSelectDropdown)]
        for item in to_remove:
            self.remove_item(item)

        usable_items = [inv for inv in self.inventory if inv.item.type != ItemType.SKILL]
        if usable_items:
            new_dropdown = ItemSelectDropdown(usable_items)
            children_list = [new_dropdown] + [c for c in self.children if not isinstance(c, ItemSelectDropdown)]
            self.clear_items()
            for child in children_list:
                self.add_item(child)

    def create_embed(self) -> discord.Embed:
        """인벤토리 임베드 생성"""
        tab_titles = {
            ItemType.CONSUME: "🧪 소모품",
            ItemType.EQUIP: "⚔️ 장비",
            ItemType.ETC: "📦 기타",
            ItemType.SKILL: "📜 스킬"
        }
        tab_title = tab_titles.get(self.current_tab, "전체")

        embed = discord.Embed(
            title=f"🎒 인벤토리 - {tab_title}",
            description=f"보유 아이템 목록입니다.",
            color=EmbedColor.DEFAULT
        )

        total_items = len(self.inventory)
        all_items = len(self.all_inventory) + len(self.owned_skills)
        embed.add_field(name="📦 카테고리", value=f"{total_items}개", inline=True)
        embed.add_field(name="📦 전체", value=f"{all_items}/100", inline=True)
        embed.add_field(name="📄 페이지", value=f"{self.page + 1}/{self.total_pages}", inline=True)

        page_items = self._get_page_items()

        if not page_items:
            self._add_empty_message(embed)
        else:
            self._add_item_list(embed, page_items)

        footer = {
            ItemType.CONSUME: "아이템 사용 → 사용할 소모품과 수량 선택",
            ItemType.EQUIP: "장비 장착 → 장착할 장비 선택",
            ItemType.ETC: "재료는 제작·교환 콘텐츠에서 사용되며 직접 소비할 수 없습니다.",
            ItemType.SKILL: "스킬 장착 → 10칸 덱 편집",
        }
        embed.set_footer(text=footer.get(self.current_tab, "아이템 상세는 설명 버튼에서 확인"))
        return embed

    def _add_empty_message(self, embed: discord.Embed) -> None:
        """빈 목록 메시지"""
        empty_msg = {
            ItemType.CONSUME: "보유한 소모품이 없습니다.",
            ItemType.EQUIP: "보유한 장비가 없습니다.",
            ItemType.SKILL: "보유한 스킬이 없습니다."
        }
        embed.add_field(
            name="아이템 없음",
            value=empty_msg.get(self.current_tab, "인벤토리가 비어있습니다."),
            inline=False
        )

    def _add_item_list(self, embed: discord.Embed, page_items: list) -> None:
        """아이템 목록 3열 표시"""
        item_list = []
        for inv in page_items:
            if self.current_tab == ItemType.SKILL:
                item_list.append(self._format_skill_item(inv))
            elif self.current_tab == ItemType.EQUIP:
                item_list.append(self._format_equip_item(inv))
            elif self.current_tab == ItemType.CONSUME:
                item_list.append(self._format_consume_item(inv))
            elif self.current_tab == ItemType.ETC:
                item_list.append(self._format_material_item(inv))

        chunk_size = (len(item_list) + 2) // 3
        for i in range(3):
            start = i * chunk_size
            end = start + chunk_size
            chunk = item_list[start:end]
            if chunk:
                embed.add_field(
                    name=f"목록 ({start+1}-{min(end, len(item_list))})",
                    value="\n".join(chunk),
                    inline=True
                )

    @staticmethod
    def _format_skill_item(inv) -> str:
        """스킬 아이템 포맷"""
        from models.repos.static_cache import skill_cache_by_id
        from utils.grade_display import format_skill_name
        skill = skill_cache_by_id.get(inv.skill_id)
        if skill:
            grade_id = getattr(skill.skill_model, 'grade', None)
            formatted_name = format_skill_name(skill.name, grade_id)
            equipped_info = f" (장착: {inv.equipped_count})" if inv.equipped_count > 0 else ""
            return f"📜 **{formatted_name}** x{inv.quantity}{equipped_info}"
        return f"📜 ?? x{inv.quantity}"

    @staticmethod
    def _format_equip_item(inv) -> str:
        """장비 아이템 포맷 (등급, 강화, 렙제, 슬롯, 세트 표시)"""
        from models.repos.static_cache import get_equipment_info

        instance_grade = getattr(inv, 'instance_grade', 0)
        formatted_name = format_item_name(inv.item.name, instance_grade if instance_grade > 0 else None)
        enhance = f" +{inv.enhancement_level}" if inv.enhancement_level > 0 else ""

        # 축복/저주 상태
        status = ""
        if getattr(inv, 'is_blessed', False):
            status = " ✨"
        elif getattr(inv, 'is_cursed', False):
            status = " 💀"

        # 장비 캐시에서 상세 정보
        info = get_equipment_info(inv.item.id)
        meta_parts = []
        if info.get("require_level", 1) > 1:
            meta_parts.append(f"Lv{info['require_level']}")
        if info.get("equip_pos"):
            meta_parts.append(info["equip_pos"])
        if info.get("set_name"):
            meta_parts.append(info["set_name"])

        # 주요 스탯 (가장 높은 스탯 1개)
        stat_display = _get_main_stat_text(info)
        if stat_display:
            meta_parts.append(stat_display)

        meta = f"\n└ {' · '.join(meta_parts)}" if meta_parts else ""
        return f"⚔️ **{formatted_name}**{enhance}{status}{meta}"

    @staticmethod
    def _format_consume_item(inv) -> str:
        """소모품 아이템 포맷"""
        grade_id = getattr(inv.item, 'grade_id', None)
        formatted_name = format_item_name(inv.item.name, grade_id)
        # 상자 아이템이면 저장된 던전 레벨 범위 표시
        from config import BOX_CONFIGS
        instance_grade = getattr(inv, 'instance_grade', 0)
        if inv.item.id in BOX_CONFIGS and instance_grade > 0:
            from models.repos.static_cache import get_previous_dungeon_level
            prev_level = get_previous_dungeon_level(instance_grade)
            formatted_name = f"{formatted_name}({prev_level}~{instance_grade}Lv)"
        return f"🧪 **{formatted_name}** x{inv.quantity}"

    @staticmethod
    def _format_material_item(inv) -> str:
        """직접 사용하는 소모품과 구분되는 제작/교환 재료."""
        return f"📦 **{inv.item.name}** x{inv.quantity} · 재료"

    async def refresh_message(self) -> None:
        """인벤토리 새로고침"""
        self.all_inventory = await UserInventory.filter(
            user=self.db_user
        ).prefetch_related("item")

        from service.skill.skill_ownership_service import SkillOwnershipService
        self.owned_skills = await SkillOwnershipService.get_all_owned_skills(self.db_user)

        self.inventory = self._filter_and_sort()
        self.total_pages = max(1, (len(self.inventory) + self.items_per_page - 1) // self.items_per_page)
        if self.message:
            embed = self.create_embed()
            await self.message.edit(embed=embed, view=self)

    @discord.ui.button(label="◀", style=discord.ButtonStyle.secondary, row=2)
    async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        """이전 페이지"""
        if self.page > 0:
            self.page -= 1
        else:
            self.page = self.total_pages - 1

        embed = self.create_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="▶", style=discord.ButtonStyle.secondary, row=2)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        """다음 페이지"""
        if self.page < self.total_pages - 1:
            self.page += 1
        else:
            self.page = 0

        embed = self.create_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="닫기", style=discord.ButtonStyle.danger, emoji="❌", row=2)
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        """닫기"""
        self.stop()
        await interaction.response.edit_message(content="인벤토리를 닫았습니다.", embed=None, view=None)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.user:
            await interaction.response.send_message("이 인벤토리는 다른 사용자의 것입니다.", ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        if self.message:
            try:
                await self.message.edit(view=None)
            except discord.NotFound:
                pass
