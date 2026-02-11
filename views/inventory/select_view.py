"""
인벤토리 선택 View

아이템 선택 및 사용/삭제 UI를 정의합니다.
"""
from __future__ import annotations

from typing import Optional, TYPE_CHECKING

import discord

from config import EmbedColor
from models import User
from models.user_inventory import UserInventory
from resources.item_emoji import ItemType
from service.item.item_use_service import ItemUseService
from service.item.inventory_service import InventoryService
from service.item.grade_service import GradeService
from exceptions import (
    CombatRestrictionError,
    ItemNotFoundError,
    ItemNotEquippableError,
    LevelRequirementError,
    StatRequirementError,
    EquipmentSlotMismatchError
)

from views.inventory.components import ItemSelectDropdown

if TYPE_CHECKING:
    from views.inventory.list_view import InventoryView


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
        self.use_quantity: int = 1

        usable_items = [inv for inv in self.inventory if inv.item.type != ItemType.SKILL]
        if usable_items:
            self.add_item(ItemSelectDropdown(usable_items))

        self.add_item(QuantityButton("+1", 1, row=1))
        self.add_item(QuantityButton("+5", 5, row=1))
        self.add_item(QuantityButton("+10", 10, row=1))
        self.add_item(QuantityButton("-1", -1, row=1))
        self.add_item(QuantityButton("-5", -5, row=1))
        self.add_item(InventoryUseButton())
        self.add_item(InventoryDeleteButton())
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

            max_quantity = self.selected_inventory_item.quantity if item.type == ItemType.CONSUME else 1
            self.use_quantity = max(1, min(self.use_quantity, max_quantity))

            # 인스턴스 등급 표시 (장비만)
            grade_info = ""
            instance_grade = getattr(self.selected_inventory_item, 'instance_grade', 0)
            if instance_grade > 0:
                grade_display = GradeService.get_grade_display(instance_grade)
                grade_info = f"**등급**: {grade_display}\n"
                effects_text = GradeService.format_special_effects(
                    self.selected_inventory_item.special_effects
                )
                if effects_text:
                    grade_info += f"**특수 효과**:\n{effects_text}\n"

            embed.add_field(
                name=f"✅ 선택됨: {item.name}",
                value=(
                    f"**종류**: {item_type}\n"
                    f"{grade_info}"
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

        if view.selected_inventory_item.item.type == ItemType.EQUIP:
            await interaction.response.send_message("장비는 개수 조절이 불가능합니다!", ephemeral=True)
            return

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
            success_count, last_result = await self._use_items(view)

            if success_count > 0:
                await self._handle_success(view, interaction, success_count, last_result)
            else:
                await interaction.response.send_message("⚠️ 아이템을 사용할 수 없습니다.", ephemeral=True)

        except CombatRestrictionError:
            await interaction.response.send_message("⚠️ 전투 중에는 아이템을 사용할 수 없습니다!", ephemeral=True)
        except ItemNotFoundError:
            await interaction.response.send_message("⚠️ 아이템을 찾을 수 없습니다.", ephemeral=True)
        except ItemNotEquippableError as e:
            await interaction.response.send_message(f"⚠️ {e.message}", ephemeral=True)
        except LevelRequirementError as e:
            await interaction.response.send_message(f"⚠️ {str(e)}", ephemeral=True)
        except StatRequirementError as e:
            await interaction.response.send_message(f"⚠️ {str(e)}", ephemeral=True)
        except EquipmentSlotMismatchError as e:
            await interaction.response.send_message(f"⚠️ {str(e)}", ephemeral=True)
        except Exception as e:
            # 모든 예외를 UI에 표시
            error_msg = str(e) if str(e) else "알 수 없는 오류가 발생했습니다."
            await interaction.response.send_message(f"⚠️ {error_msg}", ephemeral=True)
            import traceback
            traceback.print_exc()  # 로그에도 출력

    @staticmethod
    async def _use_items(view: InventorySelectView) -> tuple:
        """아이템 여러 개 사용"""
        success_count = 0
        last_result = None

        for _ in range(view.use_quantity):
            current_inv = await UserInventory.get_or_none(id=view.selected_inventory_item.id)
            if not current_inv or current_inv.quantity <= 0:
                break

            result = await ItemUseService.use_item(view.db_user, current_inv.id)
            if result.success:
                success_count += 1
                last_result = result
            else:
                break

        return success_count, last_result

    @staticmethod
    async def _handle_success(view: InventorySelectView, interaction, success_count, last_result):
        """사용 성공 처리"""
        if view.list_view:
            await view.list_view.refresh_message()
        await view.refresh_items()

        updated_inv = await UserInventory.get_or_none(id=view.selected_inventory_item.id).prefetch_related("item")
        if updated_inv and updated_inv.quantity > 0:
            view.selected_inventory_item = updated_inv
            view.use_quantity = 1
        else:
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


class InventoryDeleteButton(discord.ui.Button):
    """아이템 삭제 버튼"""

    def __init__(self):
        super().__init__(label="삭제", style=discord.ButtonStyle.danger, emoji="🗑️", row=3)

    async def callback(self, interaction: discord.Interaction):
        view: InventorySelectView = self.view
        if not view.selected_inventory_item:
            await interaction.response.send_message("먼저 아이템을 선택하세요!", ephemeral=True)
            return

        modal = DeleteConfirmModal(view)
        await interaction.response.send_modal(modal)


class DeleteConfirmModal(discord.ui.Modal, title="아이템 삭제 확인"):
    """삭제 확인 모달"""

    confirm_input = discord.ui.TextInput(
        label="정말 삭제하시겠습니까? (예/아니오)",
        placeholder="'예'를 입력하면 삭제됩니다",
        required=True,
        max_length=10
    )

    def __init__(self, view: InventorySelectView):
        super().__init__()
        self.view = view

    async def on_submit(self, interaction: discord.Interaction):
        confirm = self.confirm_input.value.strip().lower()

        if confirm not in ["예", "yes", "y"]:
            await interaction.response.send_message("❌ 삭제가 취소되었습니다.", ephemeral=True)
            return

        try:
            item_name = self.view.selected_inventory_item.item.name
            inventory_id = self.view.selected_inventory_item.id

            await InventoryService.delete_inventory_item(
                self.view.db_user,
                inventory_id
            )

            if self.view.list_view:
                await self.view.list_view.refresh_message()
            await self.view.refresh_items()

            self.view.selected_item_id = None
            self.view.selected_inventory_item = None

            embed = self.view.create_embed()
            embed.add_field(
                name="🗑️ 삭제 완료",
                value=f"**{item_name}**을(를) 삭제했습니다.",
                inline=False
            )
            await interaction.response.edit_message(embed=embed, view=self.view)

        except ItemNotFoundError:
            await interaction.response.send_message("⚠️ 아이템을 찾을 수 없습니다.", ephemeral=True)


class InventorySelectCloseButton(discord.ui.Button):
    """선택 창 닫기"""

    def __init__(self):
        super().__init__(label="닫기", style=discord.ButtonStyle.secondary, emoji="❌", row=3)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.edit_message(content="선택 창을 닫았습니다.", embed=None, view=None)


class InventorySelectButton(discord.ui.Button):
    """아이템 사용 버튼 (선택 창 열기)"""

    def __init__(self, current_tab: ItemType = ItemType.CONSUME):
        # 장비 탭이면 "장비 장착", 아니면 "아이템 사용"
        label = "장비 장착" if current_tab == ItemType.EQUIP else "아이템 사용"
        super().__init__(label=label, style=discord.ButtonStyle.success, emoji="✅", row=2)

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        select_view = InventorySelectView(
            user=interaction.user,
            db_user=view.db_user,
            list_view=view
        )
        embed = select_view.create_embed()
        await interaction.response.send_message(embed=embed, view=select_view, ephemeral=True)


class EnhancementSelectButton(discord.ui.Button):
    """강화 버튼 (선택 창 열기) - 장비 탭에서만 표시"""

    def __init__(self):
        super().__init__(label="강화", style=discord.ButtonStyle.primary, emoji="⚒️", row=1)

    async def callback(self, interaction: discord.Interaction):
        from views.enhancement_view import EnhancementView

        view = self.view
        equipment_items = [inv for inv in view.inventory if inv.item.type == ItemType.EQUIP]

        enhance_view = EnhancementView(
            user=interaction.user,
            db_user=view.db_user,
            equipment_items=equipment_items,
            list_view=view,
        )
        embed = enhance_view.create_default_embed()
        await interaction.response.send_message(embed=embed, view=enhance_view, ephemeral=True)
