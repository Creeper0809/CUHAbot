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
        view: InventoryView = self.view
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

        embed = view.create_embed()
        if selected_inv:
            item_type = "장비" if selected_inv.item.type == ItemType.EQUIP else "소모품"
            action = "장착" if selected_inv.item.type == ItemType.EQUIP else "사용"

            embed.add_field(
                name=f"✅ 선택됨: {selected_inv.item.name}",
                value=(
                    f"**종류**: {item_type}\n"
                    f"**설명**: {selected_inv.item.description or '없음'}\n"
                    f"'**{action}**' 버튼을 눌러 {action}하세요."
                ),
                inline=False
            )

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

        # 아이템 선택 드롭다운 추가 (스킬 제외)
        usable_items = [inv for inv in inventory if inv.item.type != ItemType.SKILL]
        if usable_items:
            self.add_item(ItemSelectDropdown(usable_items))

    def _get_page_items(self) -> List[UserInventory]:
        """현재 페이지 아이템 목록"""
        start = self.page * self.items_per_page
        end = start + self.items_per_page
        return self.inventory[start:end]

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

        embed.set_footer(text="드롭다운에서 아이템 선택 → 사용 버튼 클릭")

        return embed

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
