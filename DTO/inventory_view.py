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

            options.append(
                discord.SelectOption(
                    label=f"{inv.item.name}{enhance}{qty}",
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
            row=1
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

        # 선택된 아이템 정보 표시
        selected_inv = next(
            (inv for inv in view.inventory if inv.id == item_id),
            None
        )

        view.selected_inventory_item = selected_inv
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
        timeout: int = 120
    ):
        super().__init__(timeout=timeout)

        self.user = user
        self.db_user = db_user
        self.inventory = inventory
        self.page = 0
        self.items_per_page = UI.ITEMS_PER_PAGE
        self.total_pages = max(1, (len(inventory) + self.items_per_page - 1) // self.items_per_page)
        self.message: Optional[discord.Message] = None
        self.selected_item_id: Optional[int] = None

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
        embed = discord.Embed(
            title="🎒 인벤토리",
            description=f"보유 아이템 목록입니다.",
            color=EmbedColor.DEFAULT
        )

        # 슬롯 정보
        total_items = len(self.inventory)
        embed.add_field(
            name="📦 슬롯",
            value=f"{total_items}/100",
            inline=True
        )

        embed.add_field(
            name="📄 페이지",
            value=f"{self.page + 1}/{self.total_pages}",
            inline=True
        )

        embed.add_field(name="\u200b", value="\u200b", inline=True)

        # 아이템 목록
        page_items = self._get_page_items()

        if not page_items:
            embed.add_field(
                name="아이템 없음",
                value="인벤토리가 비어있습니다.\n던전에서 아이템을 획득하거나 상점에서 구매하세요!",
                inline=False
            )
        else:
            # 장비류
            equipment = [inv for inv in page_items if inv.item.type == ItemType.EQUIP]
            consumables = [inv for inv in page_items if inv.item.type == ItemType.CONSUME]
            others = [inv for inv in page_items if inv.item.type not in (ItemType.EQUIP, ItemType.CONSUME, ItemType.SKILL)]

            if equipment:
                equip_text = []
                for inv in equipment:
                    enhance = f" +{inv.enhancement_level}" if inv.enhancement_level > 0 else ""
                    equip_text.append(f"⚔️ **{inv.item.name}**{enhance}")
                embed.add_field(
                    name="🗡️ 장비",
                    value="\n".join(equip_text),
                    inline=True
                )

            if consumables:
                consume_text = []
                for inv in consumables:
                    consume_text.append(f"🧪 **{inv.item.name}** x{inv.quantity}")
                embed.add_field(
                    name="🧪 소비",
                    value="\n".join(consume_text),
                    inline=True
                )

            if others:
                other_text = []
                for inv in others:
                    other_text.append(f"📦 **{inv.item.name}** x{inv.quantity}")
                embed.add_field(
                    name="📦 기타",
                    value="\n".join(other_text),
                    inline=True
                )

        embed.set_footer(text="아이템 사용 버튼 → 선택 창에서 사용")

        return embed

    async def refresh_message(self) -> None:
        """인벤토리 새로고침"""
        self.inventory = await UserInventory.filter(
            user=self.db_user
        ).prefetch_related("item")
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

    @discord.ui.button(label="◀", style=discord.ButtonStyle.secondary, row=0)
    async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        """이전 페이지"""
        if self.page > 0:
            self.page -= 1
        else:
            self.page = self.total_pages - 1  # 순환

        embed = self.create_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="▶", style=discord.ButtonStyle.secondary, row=0)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        """다음 페이지"""
        if self.page < self.total_pages - 1:
            self.page += 1
        else:
            self.page = 0  # 순환

        embed = self.create_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="사용", style=discord.ButtonStyle.success, emoji="✅", row=0)
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

    @discord.ui.button(label="닫기", style=discord.ButtonStyle.danger, emoji="❌", row=0)
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
        usable_items = [inv for inv in self.inventory if inv.item.type != ItemType.SKILL]
        if usable_items:
            self.add_item(ItemSelectDropdown(usable_items))
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
            embed.add_field(
                name=f"✅ 선택됨: {item.name}",
                value=(
                    f"**종류**: {item_type}\n"
                    f"**설명**: {item.description or '없음'}\n"
                    f"**수량**: {self.selected_inventory_item.quantity}\n"
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


class InventoryUseButton(discord.ui.Button):
    """아이템 사용 버튼"""

    def __init__(self):
        super().__init__(label="사용", style=discord.ButtonStyle.success, emoji="✅", row=2)

    async def callback(self, interaction: discord.Interaction):
        view: InventorySelectView = self.view
        if not view.selected_inventory_item:
            await interaction.response.send_message("먼저 아이템을 선택하세요!", ephemeral=True)
            return

        try:
            result = await ItemUseService.use_item(view.db_user, view.selected_inventory_item.id)
            if result.success:
                if view.list_view:
                    await view.list_view.refresh_message()
                await view.refresh_items()
                view.selected_item_id = None
                view.selected_inventory_item = None
                embed = view.create_embed()
                embed.add_field(
                    name="✅ 사용 완료!",
                    value=f"{result.item_name}\n{result.effect_description or ''}",
                    inline=False
                )
                await interaction.response.edit_message(embed=embed, view=view)
            else:
                await interaction.response.send_message(
                    f"⚠️ {result.message}",
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
        super().__init__(label="닫기", style=discord.ButtonStyle.danger, emoji="❌", row=2)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.edit_message(content="선택 창을 닫았습니다.", embed=None, view=None)


class InventorySelectButton(discord.ui.Button):
    """아이템 사용 버튼 (선택 창 열기)"""

    def __init__(self):
        super().__init__(label="아이템 사용", style=discord.ButtonStyle.success, emoji="✅", row=0)

    async def callback(self, interaction: discord.Interaction):
        view: InventoryView = self.view
        select_view = InventorySelectView(
            user=interaction.user,
            db_user=view.db_user,
            list_view=view
        )
        embed = select_view.create_embed()
        await interaction.response.send_message(embed=embed, view=select_view, ephemeral=True)
