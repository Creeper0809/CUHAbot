"""
상점 UI

NPC 상점 인터페이스를 제공하는 Discord View 컴포넌트입니다.
"""
import asyncio

import discord
from typing import Optional, List

from config import EmbedColor
from models import User
from service.shop_service import ShopService, ShopItem, ShopItemType
from exceptions import InsufficientGoldError, ItemNotFoundError, SkillNotFoundError


class ShopItemDropdown(discord.ui.Select):
    """상점 아이템 선택 드롭다운"""

    def __init__(self, items: List[ShopItem], user_gold: int):
        options = []

        for item in items[:25]:
            affordable = "✅" if user_gold >= item.price else "❌"
            type_emoji = self._get_type_emoji(item.item_type)

            options.append(
                discord.SelectOption(
                    label=f"{type_emoji} {item.name}",
                    description=f"{affordable} {item.price}G - {item.description[:30]}",
                    value=str(item.id)
                )
            )

        if not options:
            options.append(
                discord.SelectOption(
                    label="판매 중인 상품 없음",
                    value="0"
                )
            )

        super().__init__(
            placeholder="🛒 구매할 아이템 선택",
            options=options,
            row=0
        )

    @staticmethod
    def _get_type_emoji(item_type: ShopItemType) -> str:
        """아이템 타입별 이모지"""
        if item_type == ShopItemType.EQUIPMENT:
            return "⚔️"
        elif item_type == ShopItemType.CONSUMABLE:
            return "🧪"
        elif item_type == ShopItemType.SKILL:
            return "✨"
        return "📦"

    async def callback(self, interaction: discord.Interaction):
        view: ShopView = self.view
        item_id = int(self.values[0])

        if item_id == 0:
            await interaction.response.send_message(
                "구매할 상품이 없습니다.",
                ephemeral=True
            )
            return

        view.selected_item_id = item_id
        shop_item = ShopService.get_shop_item_from_list(view.shop_items, item_id)
        view.selected_item = shop_item

        embed = view.create_embed()
        if shop_item:
            type_name = {
                ShopItemType.EQUIPMENT: "장비",
                ShopItemType.CONSUMABLE: "소비",
                ShopItemType.SKILL: "스킬"
            }.get(shop_item.item_type, "기타")

            embed.add_field(
                name=f"🛒 선택됨: {shop_item.name}",
                value=(
                    f"**종류**: {type_name}\n"
                    f"**가격**: {shop_item.price}G\n"
                    f"**설명**: {shop_item.description}"
                ),
                inline=False
            )

        await interaction.response.edit_message(embed=embed, view=view)

        if shop_item:
            purchase_view = ShopPurchaseView(
                user=interaction.user,
                db_user=view.db_user,
                shop_item=shop_item,
                parent_view=view
            )
            purchase_embed = purchase_view.create_embed()
            await interaction.followup.send(embed=purchase_embed, view=purchase_view, ephemeral=True)


class PurchaseQuantityButton(discord.ui.Button):
    """수량 조절 버튼"""

    def __init__(self, label: str, delta: int, row: int = 1):
        self.delta = delta
        super().__init__(
            label=label,
            style=discord.ButtonStyle.secondary,
            row=row
        )

    async def callback(self, interaction: discord.Interaction):
        view: ShopPurchaseView = self.view
        view.quantity = max(1, view.quantity + self.delta)
        embed = view.create_embed()
        await interaction.response.edit_message(embed=embed, view=view)


class PurchaseBuyButton(discord.ui.Button):
    """구매 버튼"""

    def __init__(self):
        super().__init__(
            label="구매",
            style=discord.ButtonStyle.success,
            emoji="💰",
            row=2
        )

    async def callback(self, interaction: discord.Interaction):
        view: ShopPurchaseView = self.view
        try:
            result = await ShopService.purchase_shop_item(
                view.db_user,
                view.shop_item,
                view.quantity
            )

            view.parent_view.user_gold = result.remaining_gold
            await view.parent_view.refresh_message()

            embed = view.create_embed()
            embed.add_field(
                name="✅ 구매 완료!",
                value=(
                    f"**{result.item_name}** x{result.quantity} 구매!\n"
                    f"💰 -{result.total_cost}G\n"
                    f"💵 남은 골드: {result.remaining_gold}G"
                ),
                inline=False
            )
            await interaction.response.edit_message(embed=embed, view=None)

        except InsufficientGoldError as e:
            await interaction.response.send_message(
                f"⚠️ 골드가 부족합니다! (필요: {e.required}G, 보유: {e.current}G)",
                ephemeral=True
            )
        except (ItemNotFoundError, SkillNotFoundError) as e:
            await interaction.response.send_message(
                f"⚠️ {e.message}",
                ephemeral=True
            )


class CloseButton(discord.ui.Button):
    """상점 닫기 버튼"""

    def __init__(self):
        super().__init__(
            label="닫기",
            style=discord.ButtonStyle.danger,
            emoji="❌",
            row=2
        )

    async def callback(self, interaction: discord.Interaction):
        view: ShopView = self.view
        view.stop()

        await interaction.response.edit_message(
            content="👋 상점을 이용해주셔서 감사합니다!",
            embed=None,
            view=None
        )

        # 잠시 후 메시지 삭제
        await asyncio.sleep(1.5)
        try:
            await interaction.delete_original_response()
        except discord.NotFound:
            pass


class ShopView(discord.ui.View):
    """
    상점 View

    NPC 상점에서 아이템/스킬 구매 UI를 제공합니다.
    """

    def __init__(
        self,
        user: discord.User,
        db_user: User,
        user_gold: int,
        shop_items: Optional[List[ShopItem]] = None,
        timeout: int = 120
    ):
        super().__init__(timeout=timeout)

        self.user = user
        self.db_user = db_user
        self.user_gold = user_gold
        self.selected_item_id: Optional[int] = None
        self.selected_item: Optional[ShopItem] = None
        self.quantity = 1
        self.shop_items = shop_items or ShopService.get_shop_items()
        self.message: Optional[discord.Message] = None

        # 컴포넌트 추가
        self.add_item(ShopItemDropdown(self.shop_items, user_gold))
        self.add_item(CloseButton())

    def _update_dropdown(self):
        """드롭다운 업데이트"""
        to_remove = [item for item in self.children if isinstance(item, ShopItemDropdown)]
        for item in to_remove:
            self.remove_item(item)

        # 새 드롭다운을 맨 앞에 추가
        new_dropdown = ShopItemDropdown(self.shop_items, self.user_gold)
        children_list = [new_dropdown] + list(self.children)

        self.clear_items()
        for child in children_list:
            self.add_item(child)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.user:
            await interaction.response.send_message(
                "이 상점은 다른 사용자의 것입니다.",
                ephemeral=True
            )
            return False
        return True

    def create_embed(self) -> discord.Embed:
        """상점 임베드 생성"""
        embed = discord.Embed(
            title="🏪 NPC 상점",
            description=(
                "던전에서 만난 상인입니다.\n"
                "장비, 포션, 스킬을 구매할 수 있습니다."
            ),
            color=EmbedColor.DEFAULT
        )

        embed.add_field(
            name="💵 보유 골드",
            value=f"**{self.user_gold:,}G**",
            inline=True
        )

        embed.add_field(
            name="📌 안내",
            value="아이템 선택 후 구매 창이 열립니다.",
            inline=True
        )

        # 판매 목록
        skill_items = [i for i in self.shop_items if i.item_type == ShopItemType.SKILL]
        equip_items = [i for i in self.shop_items if i.item_type == ShopItemType.EQUIPMENT]
        consumable_items = [i for i in self.shop_items if i.item_type == ShopItemType.CONSUMABLE]

        if skill_items:
            skill_text = "\n".join([
                f"✨ **{i.name}** - {i.price}G"
                for i in skill_items[:5]
            ])
            embed.add_field(
                name="📜 스킬",
                value=skill_text or "없음",
                inline=False
            )

        if equip_items:
            equip_text = "\n".join([
                f"⚔️ **{i.name}** - {i.price}G"
                for i in equip_items[:5]
            ])
            embed.add_field(
                name="🗡️ 장비",
                value=equip_text or "없음",
                inline=True
            )

        if consumable_items:
            consumable_text = "\n".join([
                f"🧪 **{i.name}** - {i.price}G"
                for i in consumable_items[:5]
            ])
            embed.add_field(
                name="🧪 소비",
                value=consumable_text or "없음",
                inline=True
            )

        embed.set_footer(text="드롭다운에서 아이템 선택 → 구매 창에서 수량/구매")

        return embed

    async def refresh_message(self) -> None:
        """상점 메시지 갱신"""
        if self.message:
            self._update_dropdown()
            embed = self.create_embed()
            await self.message.edit(embed=embed, view=self)


class ShopPurchaseView(discord.ui.View):
    """구매 액션 View"""

    def __init__(
        self,
        user: discord.User,
        db_user: User,
        shop_item: ShopItem,
        parent_view: ShopView,
        timeout: int = 60
    ):
        super().__init__(timeout=timeout)
        self.user = user
        self.db_user = db_user
        self.shop_item = shop_item
        self.parent_view = parent_view
        self.quantity = 1
        self.message: Optional[discord.Message] = None

        self.add_item(PurchaseQuantityButton("-5", -5))
        self.add_item(PurchaseQuantityButton("-1", -1))
        self.add_item(PurchaseQuantityButton("+1", +1))
        self.add_item(PurchaseQuantityButton("+5", +5))
        self.add_item(PurchaseBuyButton())
        self.add_item(CloseButton())

    def create_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="🧾 구매 확인",
            description=f"**{self.shop_item.name}**",
            color=EmbedColor.DEFAULT
        )
        embed.add_field(
            name="수량",
            value=f"{self.quantity}개",
            inline=True
        )
        total = self.shop_item.price * self.quantity
        affordable = "✅" if self.parent_view.user_gold >= total else "❌"
        embed.add_field(
            name="총 가격",
            value=f"{affordable} **{total:,}G**",
            inline=True
        )
        embed.add_field(
            name="보유 골드",
            value=f"{self.parent_view.user_gold:,}G",
            inline=True
        )
        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user == self.user

    async def on_timeout(self):
        if self.message:
            try:
                await self.message.edit(
                    content="⏰ 상점이 닫혔습니다.",
                    embed=None,
                    view=None
                )
                # 잠시 후 메시지 삭제
                await asyncio.sleep(1.5)
                await self.message.delete()
            except discord.NotFound:
                pass
