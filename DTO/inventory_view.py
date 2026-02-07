"""
인벤토리 UI

사용자의 인벤토리를 확인하고 아이템을 사용할 수 있는 Discord View 컴포넌트입니다.
"""
import discord
from typing import Optional, List

from config import EmbedColor, UI
from models import User
from models.user_inventory import UserInventory
from resources.item_emoji import ItemType
from service.item_use_service import ItemUseService
from exceptions import CombatRestrictionError, ItemNotFoundError, ItemNotEquippableError
from utility.grade_display import format_item_name


class ItemSelectDropdown(discord.ui.Select):
    """아이템 선택 드롭다운"""

    def __init__(self, items: List[UserInventory]):
        options = []

        # 스킬 타입 제외하고 옵션 생성
        for inv in items[:25]:
            if inv.item.type == ItemType.SKILL:
                continue

            emoji = self._get_type_emoji(inv.item.type)
            enhance = f" +{inv.enhancement_level}" if inv.enhancement_level > 0 else ""
            qty = f" x{inv.quantity}" if inv.quantity > 1 else ""

            # 등급별 색상 적용
            grade_id = getattr(inv.item, 'grade_id', None)
            formatted_name = format_item_name(inv.item.name, grade_id)

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

        # 선택된 아이템 정보 표시 (DB에서 직접 가져와서 item 관계 로드)
        selected_inv = await UserInventory.get_or_none(id=item_id).prefetch_related("item")

        view.selected_inventory_item = selected_inv
        embed = view.create_embed()
        await interaction.response.edit_message(embed=embed, view=view)


class TabButton(discord.ui.Button):
    """탭 전환 버튼"""

    def __init__(self, label: str, tab_type: ItemType, is_active: bool = False):
        style = discord.ButtonStyle.primary if is_active else discord.ButtonStyle.secondary
        super().__init__(
            label=label,
            style=style,
            row=0
        )
        self.tab_type = tab_type

    async def callback(self, interaction: discord.Interaction):
        view: InventoryView = self.view

        # 탭 변경
        view.current_tab = self.tab_type
        view.inventory = view._filter_by_tab()
        view.page = 0  # 페이지 초기화
        view.total_pages = max(1, (len(view.inventory) + view.items_per_page - 1) // view.items_per_page)

        # 버튼 스타일 업데이트
        view._update_tab_buttons()

        embed = view.create_embed()
        await interaction.response.edit_message(embed=embed, view=view)


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
        self.all_inventory = inventory  # 전체 인벤토리
        self.owned_skills = owned_skills or []  # 보유 스킬
        self.current_tab = ItemType.CONSUME  # 기본 탭: 소모품
        self.inventory = self._filter_by_tab()  # 탭별 필터링된 인벤토리
        self.page = 0
        self.items_per_page = UI.ITEMS_PER_PAGE
        self.total_pages = max(1, (len(self.inventory) + self.items_per_page - 1) // self.items_per_page)
        self.message: Optional[discord.Message] = None
        self.selected_item_id: Optional[int] = None

        self._add_tab_buttons()
        self.add_item(InventorySelectButton())
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
        elif self.current_tab == ItemType.SKILL:
            return self.owned_skills  # 스킬은 UserOwnedSkill에서 가져옴
        else:
            return self.all_inventory

    def _add_tab_buttons(self) -> None:
        """탭 버튼 추가"""
        self.add_item(TabButton("🧪 소모품", ItemType.CONSUME, is_active=(self.current_tab == ItemType.CONSUME)))
        self.add_item(TabButton("⚔️ 장비", ItemType.EQUIP, is_active=(self.current_tab == ItemType.EQUIP)))
        self.add_item(TabButton("📜 스킬", ItemType.SKILL, is_active=(self.current_tab == ItemType.SKILL)))

    def _update_tab_buttons(self) -> None:
        """탭 버튼 업데이트 (선택된 탭 강조)"""
        to_remove = [item for item in self.children if isinstance(item, TabButton)]
        for item in to_remove:
            self.remove_item(item)
        self._add_tab_buttons()

    def _get_item_type_emoji(self, item_type: str) -> str:
        """아이템 타입별 이모지"""
        type_map = {
            "WEAPON": "⚔️",
            "ARMOR": "🛡️",
            "ACCESSORY": "💍",
            "CONSUME": "🧪",
            "MATERIAL": "📦",
            "ETC": "📜"
        }
        return type_map.get(item_type, "📦")

    def create_embed(self) -> discord.Embed:
        """인벤토리 임베드 생성"""
        # 탭별 타이틀
        tab_titles = {
            ItemType.CONSUME: "🧪 소모품",
            ItemType.EQUIP: "⚔️ 장비",
            ItemType.SKILL: "📜 스킬"
        }
        tab_title = tab_titles.get(self.current_tab, "전체")

        embed = discord.Embed(
            title=f"🎒 인벤토리 - {tab_title}",
            description=f"보유 아이템 목록입니다.",
            color=EmbedColor.DEFAULT
        )

        # 슬롯 정보
        total_items = len(self.inventory)
        all_items = len(self.all_inventory) + len(self.owned_skills)  # 전체 아이템 + 스킬
        embed.add_field(
            name="📦 카테고리",
            value=f"{total_items}개",
            inline=True
        )

        embed.add_field(
            name="📦 전체",
            value=f"{all_items}/100",
            inline=True
        )

        embed.add_field(
            name="📄 페이지",
            value=f"{self.page + 1}/{self.total_pages}",
            inline=True
        )

        # 아이템 목록
        page_items = self._get_page_items()

        if not page_items:
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
        else:
            # 탭에 따라 다른 표시 방식
            item_list = []
            for inv in page_items:
                if self.current_tab == ItemType.SKILL:
                    # UserOwnedSkill 객체 처리
                    from models.repos.static_cache import skill_cache_by_id
                    skill = skill_cache_by_id.get(inv.skill_id)
                    if skill:
                        grade_id = getattr(skill.skill_model, 'grade', None)
                        from utility.grade_display import format_skill_name
                        formatted_name = format_skill_name(skill.name, grade_id)
                        # 장착 수량 정보 표시
                        equipped_info = f" (장착: {inv.equipped_count})" if inv.equipped_count > 0 else ""
                        item_list.append(f"📜 **{formatted_name}** x{inv.quantity}{equipped_info}")
                else:
                    # UserInventory 객체 처리
                    grade_id = getattr(inv.item, 'grade_id', None)
                    formatted_name = format_item_name(inv.item.name, grade_id)

                    if self.current_tab == ItemType.EQUIP:
                        enhance = f" +{inv.enhancement_level}" if inv.enhancement_level > 0 else ""
                        item_list.append(f"⚔️ **{formatted_name}**{enhance}")
                    elif self.current_tab == ItemType.CONSUME:
                        item_list.append(f"🧪 **{formatted_name}** x{inv.quantity}")

            # 3열로 분할 표시
            chunk_size = (len(item_list) + 2) // 3  # 3등분
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

        embed.set_footer(text="아이템 사용 버튼 → 선택 창에서 사용")

        return embed

    async def refresh_message(self) -> None:
        """인벤토리 새로고침"""
        self.all_inventory = await UserInventory.filter(
            user=self.db_user
        ).prefetch_related("item")

        # 스킬도 새로고침
        from service.skill_ownership_service import SkillOwnershipService
        self.owned_skills = await SkillOwnershipService.get_all_owned_skills(self.db_user)

        self.inventory = self._filter_by_tab()
        self.total_pages = max(1, (len(self.inventory) + self.items_per_page - 1) // self.items_per_page)
        if self.message:
            embed = self.create_embed()
            await self.message.edit(embed=embed, view=self)

    def _update_dropdown(self):
        """드롭다운 업데이트"""
        # 기존 드롭다운 제거
        to_remove = [item for item in self.children if isinstance(item, ItemSelectDropdown)]
        for item in to_remove:
            self.remove_item(item)

        # 스킬 제외한 아이템으로 새 드롭다운 생성
        usable_items = [inv for inv in self.inventory if inv.item.type != ItemType.SKILL]
        if usable_items:
            new_dropdown = ItemSelectDropdown(usable_items)
            # 드롭다운을 children 시작 부분에 삽입
            children_list = [new_dropdown] + [c for c in self.children if not isinstance(c, ItemSelectDropdown)]
            self.clear_items()
            for child in children_list:
                self.add_item(child)

    @discord.ui.button(label="◀", style=discord.ButtonStyle.secondary, row=1)
    async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        """이전 페이지"""
        if self.page > 0:
            self.page -= 1
        else:
            self.page = self.total_pages - 1  # 순환

        embed = self.create_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="▶", style=discord.ButtonStyle.secondary, row=1)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        """다음 페이지"""
        if self.page < self.total_pages - 1:
            self.page += 1
        else:
            self.page = 0  # 순환

        embed = self.create_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="사용", style=discord.ButtonStyle.success, emoji="✅", row=1)
    async def use_item(self, interaction: discord.Interaction, button: discord.ui.Button):
        """아이템 사용"""
        if not self.selected_item_id:
            await interaction.response.send_message(
                "먼저 아이템을 선택하세요!",
                ephemeral=True
            )
            return

        try:
            result = await ItemUseService.use_item(self.db_user, self.selected_item_id)

            if result.success:
                # 인벤토리 갱신
                self.inventory = await UserInventory.filter(
                    user=self.db_user
                ).prefetch_related("item")

                self.selected_item_id = None
                self._update_dropdown()

                embed = self.create_embed()
                embed.add_field(
                    name="✅ 사용 완료!",
                    value=(
                        f"**{result.item_name}**\n"
                        f"{result.effect_description or ''}"
                    ),
                    inline=False
                )

                await interaction.response.edit_message(embed=embed, view=self)
            else:
                await interaction.response.send_message(
                    f"⚠️ {result.message}",
                    ephemeral=True
                )

        except CombatRestrictionError as e:
            await interaction.response.send_message(
                f"⚠️ 전투 중에는 아이템을 사용할 수 없습니다!",
                ephemeral=True
            )
        except ItemNotFoundError:
            await interaction.response.send_message(
                "⚠️ 아이템을 찾을 수 없습니다.",
                ephemeral=True
            )
        except ItemNotEquippableError as e:
            await interaction.response.send_message(
                f"⚠️ {e.message}",
                ephemeral=True
            )

    @discord.ui.button(label="닫기", style=discord.ButtonStyle.danger, emoji="❌", row=1)
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        """닫기"""
        self.stop()
        await interaction.response.edit_message(
            content="인벤토리를 닫았습니다.",
            embed=None,
            view=None
        )

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.user:
            await interaction.response.send_message(
                "이 인벤토리는 다른 사용자의 것입니다.",
                ephemeral=True
            )
            return False
        return True

    async def on_timeout(self):
        if self.message:
            try:
                await self.message.edit(view=None)
            except discord.NotFound:
                pass


class InventorySelectView(discord.ui.View):
    """아이템 선택 View"""

    def __init__(
        self,
        user: discord.User,
        db_user: User,
        list_view: InventoryView,
        timeout: int = 60
    ):
        super().__init__(timeout=timeout)
        self.user = user
        self.db_user = db_user
        self.list_view = list_view
        self.inventory = list_view.inventory
        self.selected_item_id: Optional[int] = None
        self.selected_inventory_item: Optional[UserInventory] = None
        self.use_quantity: int = 1  # 사용 개수
        usable_items = [inv for inv in self.inventory if inv.item.type != ItemType.SKILL]
        if usable_items:
            self.add_item(ItemSelectDropdown(usable_items))
        # 개수 조절 버튼 추가 (row 1에 모두 배치)
        self.add_item(QuantityButton("+1", 1, row=1))
        self.add_item(QuantityButton("+5", 5, row=1))
        self.add_item(QuantityButton("+10", 10, row=1))
        self.add_item(QuantityButton("-1", -1, row=1))
        self.add_item(QuantityButton("-5", -5, row=1))
        self.add_item(InventoryUseButton())
        self.add_item(InventorySelectCloseButton())

    def create_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="🎒 아이템 선택",
            description="사용할 아이템을 선택하세요.",
            color=EmbedColor.DEFAULT
        )
        if self.selected_inventory_item:
            item = self.selected_inventory_item.item
            item_type = "장비" if item.type == ItemType.EQUIP else "소모품"
            action = "장착" if item.type == ItemType.EQUIP else "사용"

            # 사용 가능 수량 제한
            max_quantity = self.selected_inventory_item.quantity if item.type == ItemType.CONSUME else 1
            self.use_quantity = max(1, min(self.use_quantity, max_quantity))

            embed.add_field(
                name=f"✅ 선택됨: {item.name}",
                value=(
                    f"**종류**: {item_type}\n"
                    f"**설명**: {item.description or '없음'}\n"
                    f"**보유 수량**: {self.selected_inventory_item.quantity}\n"
                    f"**사용 수량**: {self.use_quantity}\n"
                    f"'{action}' 버튼을 눌러 {action}하세요."
                ),
                inline=False
            )
        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user == self.user

    async def refresh_items(self) -> None:
        self.inventory = await UserInventory.filter(
            user=self.db_user
        ).prefetch_related("item")
        usable_items = [inv for inv in self.inventory if inv.item.type != ItemType.SKILL]
        to_remove = [child for child in self.children if isinstance(child, ItemSelectDropdown)]
        for child in to_remove:
            self.remove_item(child)
        if usable_items:
            self.add_item(ItemSelectDropdown(usable_items))


class QuantityButton(discord.ui.Button):
    """수량 조절 버튼"""

    def __init__(self, label: str, delta: int, row: int = 1):
        style = discord.ButtonStyle.primary if delta > 0 else discord.ButtonStyle.secondary
        super().__init__(label=label, style=style, row=row)
        self.delta = delta

    async def callback(self, interaction: discord.Interaction):
        view: InventorySelectView = self.view
        if not view.selected_inventory_item:
            await interaction.response.send_message("먼저 아이템을 선택하세요!", ephemeral=True)
            return

        # 장비는 개수 조절 불가
        if view.selected_inventory_item.item.type == ItemType.EQUIP:
            await interaction.response.send_message("장비는 개수 조절이 불가능합니다!", ephemeral=True)
            return

        # 개수 조절
        max_quantity = view.selected_inventory_item.quantity
        view.use_quantity = max(1, min(view.use_quantity + self.delta, max_quantity))

        embed = view.create_embed()
        await interaction.response.edit_message(embed=embed, view=view)


class InventoryUseButton(discord.ui.Button):
    """아이템 사용 버튼"""

    def __init__(self):
        super().__init__(label="사용", style=discord.ButtonStyle.success, emoji="✅", row=3)

    async def callback(self, interaction: discord.Interaction):
        view: InventorySelectView = self.view
        if not view.selected_inventory_item:
            await interaction.response.send_message("먼저 아이템을 선택하세요!", ephemeral=True)
            return

        try:
            # 여러 개 사용
            success_count = 0
            last_result = None

            for _ in range(view.use_quantity):
                # 인벤토리 새로고침 (매번 최신 정보 확인)
                current_inv = await UserInventory.get_or_none(id=view.selected_inventory_item.id)
                if not current_inv or current_inv.quantity <= 0:
                    break

                result = await ItemUseService.use_item(view.db_user, current_inv.id)
                if result.success:
                    success_count += 1
                    last_result = result
                else:
                    break

            if success_count > 0:
                # 인벤토리 갱신
                if view.list_view:
                    await view.list_view.refresh_message()
                await view.refresh_items()

                # 선택 유지 (아이템이 남아있는 경우)
                updated_inv = await UserInventory.get_or_none(id=view.selected_inventory_item.id).prefetch_related("item")
                if updated_inv and updated_inv.quantity > 0:
                    view.selected_inventory_item = updated_inv
                    view.use_quantity = 1  # 사용 개수 초기화
                else:
                    # 아이템 소진됨
                    view.selected_item_id = None
                    view.selected_inventory_item = None
                    view.use_quantity = 1

                embed = view.create_embed()
                embed.add_field(
                    name=f"✅ 사용 완료! (x{success_count})",
                    value=f"{last_result.item_name}\n{last_result.effect_description or ''}",
                    inline=False
                )
                await interaction.response.edit_message(embed=embed, view=view)
            else:
                await interaction.response.send_message(
                    f"⚠️ 아이템을 사용할 수 없습니다.",
                    ephemeral=True
                )

        except CombatRestrictionError:
            await interaction.response.send_message(
                "⚠️ 전투 중에는 아이템을 사용할 수 없습니다!",
                ephemeral=True
            )
        except ItemNotFoundError:
            await interaction.response.send_message(
                "⚠️ 아이템을 찾을 수 없습니다.",
                ephemeral=True
            )
        except ItemNotEquippableError as e:
            await interaction.response.send_message(
                f"⚠️ {e.message}",
                ephemeral=True
            )


class InventorySelectCloseButton(discord.ui.Button):
    """선택 창 닫기"""

    def __init__(self):
        super().__init__(label="닫기", style=discord.ButtonStyle.danger, emoji="❌", row=3)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.edit_message(content="선택 창을 닫았습니다.", embed=None, view=None)


class InventorySelectButton(discord.ui.Button):
    """아이템 사용 버튼 (선택 창 열기)"""

    def __init__(self):
        super().__init__(label="아이템 사용", style=discord.ButtonStyle.success, emoji="✅", row=1)

    async def callback(self, interaction: discord.Interaction):
        view: InventoryView = self.view
        select_view = InventorySelectView(
            user=interaction.user,
            db_user=view.db_user,
            list_view=view
        )
        embed = select_view.create_embed()
        await interaction.response.send_message(embed=embed, view=select_view, ephemeral=True)
