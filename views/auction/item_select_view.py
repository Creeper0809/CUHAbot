"""
경매 등록용 아이템 선택 View

사용자가 인벤토리에서 경매에 등록할 아이템을 선택합니다.
"""
import discord
from typing import Optional

from models.users import User
from models.user_inventory import UserInventory
from models.item import ItemType
from service.item.inventory_service import InventoryService
from utils.grade_display import get_grade_emoji


class AuctionItemSelectDropdown(discord.ui.Select):
    """경매 등록용 아이템 선택 드롭다운"""

    def __init__(self, inventory_items: list[UserInventory]):
        options = []
        for inv_item in inventory_items[:25]:  # Discord 드롭다운 최대 25개
            item = inv_item.item

            # 라벨 생성
            label = item.name
            if inv_item.enhancement_level > 0:
                label += f" +{inv_item.enhancement_level}"

            # 설명 생성
            description = f"수량: {inv_item.quantity}"
            if inv_item.instance_grade > 0:
                grade_emoji = get_grade_emoji(inv_item.instance_grade)
                description = f"{grade_emoji} | {description}"

            options.append(
                discord.SelectOption(
                    label=label[:100],  # 최대 100자
                    description=description[:100],
                    value=str(inv_item.id),
                )
            )

        super().__init__(
            placeholder="경매에 등록할 아이템을 선택하세요",
            options=options,
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        """아이템 선택 시 부모 View에 알림"""
        parent_view: AuctionItemSelectView = self.view
        selected_id = int(self.values[0])

        # 선택된 아이템 찾기
        for inv_item in parent_view.inventory_items:
            if inv_item.id == selected_id:
                parent_view.selected_inventory_item = inv_item
                break

        # Embed 갱신
        embed = parent_view.create_embed()
        await interaction.response.edit_message(embed=embed, view=parent_view)


class AuctionItemSelectView(discord.ui.View):
    """경매 등록용 아이템 선택 View"""

    def __init__(
        self,
        user: discord.User,
        db_user: User,
        parent_view: "AuctionMainView",
        timeout: int = 60,
    ):
        super().__init__(timeout=timeout)
        self.user = user
        self.db_user = db_user
        self.parent_view = parent_view
        self.inventory_items: list[UserInventory] = []
        self.selected_inventory_item: Optional[UserInventory] = None
        self.message: Optional[discord.Message] = None

    async def initialize(self):
        """비동기 초기화 - 인벤토리 로드"""
        # 잠기지 않은 아이템만 가져오기
        all_inventory = await InventoryService.get_inventory(self.db_user)
        self.inventory_items = [
            inv for inv in all_inventory if not inv.is_locked and inv.item.type != ItemType.SKILL
        ]

        if self.inventory_items:
            self.add_item(AuctionItemSelectDropdown(self.inventory_items))

    def create_embed(self) -> discord.Embed:
        """Embed 생성"""
        embed = discord.Embed(
            title="📦 아이템 선택 - 경매 등록",
            description="경매에 등록할 아이템을 선택하세요.\n(잠긴 아이템은 표시되지 않습니다)",
            color=discord.Color.blue(),
        )

        if self.selected_inventory_item:
            item = self.selected_inventory_item.item
            inv = self.selected_inventory_item

            value_parts = [
                f"**종류**: {item.type.value}",
                f"**강화**: +{inv.enhancement_level}",
                f"**수량**: {inv.quantity}",
            ]

            if inv.instance_grade > 0:
                grade_emoji = get_grade_emoji(inv.instance_grade)
                value_parts.append(f"**등급**: {grade_emoji}")

            if inv.special_effects:
                effects_str = ", ".join(
                    f"{eff['type']} +{eff['value']}"
                    for eff in inv.special_effects
                )
                value_parts.append(f"**특수 효과**: {effects_str}")

            embed.add_field(
                name=f"✅ 선택됨: {item.name}",
                value="\n".join(value_parts) + "\n\n✅ '등록 진행' 버튼을 눌러 경매 설정을 입력하세요.",
                inline=False,
            )
        else:
            if not self.inventory_items:
                embed.add_field(
                    name="⚠️ 등록 가능한 아이템 없음",
                    value="경매에 등록할 수 있는 아이템이 없습니다.",
                    inline=False,
                )

        return embed

    @discord.ui.button(label="✅ 등록 진행", style=discord.ButtonStyle.success, row=1)
    async def confirm_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """선택 확인 및 CreateListingModal 표시"""
        if interaction.user != self.user:
            await interaction.response.send_message(
                "다른 사용자의 선택 화면입니다.", ephemeral=True
            )
            return

        if not self.selected_inventory_item:
            await interaction.response.send_message(
                "⚠️ 먼저 아이템을 선택해주세요.", ephemeral=True
            )
            return

        # CreateListingModal 표시
        from views.auction.create_listing_modal import CreateListingModal

        modal = CreateListingModal(
            inventory_item=self.selected_inventory_item,
            db_user=self.db_user,
            parent_view=self.parent_view,
        )
        await interaction.response.send_modal(modal)

        # 이 View 닫기
        if self.message:
            await self.message.delete()
        self.stop()

    @discord.ui.button(label="❌ 취소", style=discord.ButtonStyle.danger, row=1)
    async def cancel_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """선택 취소"""
        if interaction.user != self.user:
            await interaction.response.send_message(
                "다른 사용자의 선택 화면입니다.", ephemeral=True
            )
            return

        await interaction.response.edit_message(
            content="아이템 선택을 취소했습니다.", embed=None, view=None
        )
        self.stop()
