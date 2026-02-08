"""
강화 UI

아이템 강화 인터페이스를 제공합니다.
"""
import discord
from typing import List, Optional

from models import User
from models.user_inventory import UserInventory
from resources.item_emoji import ItemType
from service.enhancement_service import EnhancementService, EnhancementResult
from exceptions import ItemNotFoundError, InsufficientGoldError
from utility.grade_display import format_item_name


class EnhancementItemDropdown(discord.ui.Select):
    """강화할 아이템 선택 드롭다운"""

    def __init__(self, items: List[UserInventory]):
        options = []

        for inv in items[:25]:  # Discord 제한: 최대 25개
            item = inv.item
            enhance_text = f"+{inv.enhancement_level}" if inv.enhancement_level > 0 else ""

            # 등급별 색상 적용
            grade_id = getattr(item, 'grade_id', None)
            formatted_name = format_item_name(item.name, grade_id)

            label = f"{formatted_name} {enhance_text}".strip()
            if len(label) > 100:
                label = label[:97] + "..."

            options.append(
                discord.SelectOption(
                    label=label,
                    value=str(inv.id),
                    description=f"현재 강화: +{inv.enhancement_level}"
                )
            )

        if not options:
            options.append(
                discord.SelectOption(
                    label="강화 가능한 장비가 없습니다",
                    value="0"
                )
            )

        super().__init__(
            placeholder="강화할 장비를 선택하세요",
            options=options,
            row=0
        )

    async def callback(self, interaction: discord.Interaction):
        view: EnhancementView = self.view

        if self.values[0] == "0":
            await interaction.response.send_message(
                "강화 가능한 장비가 없습니다.",
                ephemeral=True
            )
            return

        selected_id = int(self.values[0])
        view.selected_inventory_id = selected_id

        # 강화 정보 조회
        info = await EnhancementService.get_enhancement_info(
            view.db_user,
            selected_id
        )

        embed = view.create_info_embed(info)
        await interaction.response.edit_message(embed=embed, view=view)


class EnhanceButton(discord.ui.Button):
    """강화 시도 버튼"""

    def __init__(self):
        super().__init__(
            label="강화 시도",
            style=discord.ButtonStyle.primary,
            emoji="⚒️",
            row=1
        )

    async def callback(self, interaction: discord.Interaction):
        view: EnhancementView = self.view

        if not view.selected_inventory_id:
            await interaction.response.send_message(
                "먼저 아이템을 선택하세요!",
                ephemeral=True
            )
            return

        try:
            # 강화 시도
            result = await EnhancementService.attempt_enhancement(
                view.db_user,
                view.selected_inventory_id
            )

            # 아이템이 파괴되었으면 선택 해제
            if result.item_destroyed:
                view.selected_inventory_id = None
                # 인벤토리 갱신
                await view.refresh_items()
                # 파괴된 경우 기본 화면으로
                embed = view.create_default_embed()
            else:
                # 인벤토리 갱신
                await view.refresh_items()
                # 강화 후 정보 다시 조회 (최신 레벨 반영)
                info = await EnhancementService.get_enhancement_info(
                    view.db_user,
                    view.selected_inventory_id
                )
                # 결과와 함께 정보 화면 표시
                embed = view.create_info_embed(info, result)

            await interaction.response.edit_message(embed=embed, view=view)

        except ItemNotFoundError:
            await interaction.response.send_message(
                "⚠️ 아이템을 찾을 수 없습니다.",
                ephemeral=True
            )
        except InsufficientGoldError as e:
            await interaction.response.send_message(
                f"⚠️ 골드가 부족합니다! ({e.message})",
                ephemeral=True
            )
        except ValueError as e:
            await interaction.response.send_message(
                f"⚠️ {str(e)}",
                ephemeral=True
            )


class RefreshButton(discord.ui.Button):
    """새로고침 버튼"""

    def __init__(self):
        super().__init__(
            label="새로고침",
            style=discord.ButtonStyle.secondary,
            emoji="🔄",
            row=1
        )

    async def callback(self, interaction: discord.Interaction):
        view: EnhancementView = self.view
        await view.refresh_items()

        if view.selected_inventory_id:
            info = await EnhancementService.get_enhancement_info(
                view.db_user,
                view.selected_inventory_id
            )
            embed = view.create_info_embed(info)
        else:
            embed = view.create_default_embed()

        await interaction.response.edit_message(embed=embed, view=view)


class EnhancementView(discord.ui.View):
    """강화 View"""

    def __init__(
        self,
        user: discord.User,
        db_user: User,
        equipment_items: List[UserInventory],
        timeout: int = 180
    ):
        super().__init__(timeout=timeout)

        self.user = user
        self.db_user = db_user
        self.equipment_items = equipment_items
        self.selected_inventory_id: Optional[int] = None

        # 드롭다운 및 버튼 추가 (장비가 없어도 드롭다운 표시)
        self.add_item(EnhancementItemDropdown(equipment_items))
        self.add_item(EnhanceButton())
        self.add_item(RefreshButton())

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """본인만 사용 가능"""
        if interaction.user.id != self.user.id:
            await interaction.response.send_message(
                "다른 사람의 강화 창은 조작할 수 없습니다.",
                ephemeral=True
            )
            return False
        return True

    async def refresh_items(self):
        """아이템 목록 새로고침"""
        self.equipment_items = await UserInventory.filter(
            user=self.db_user,
            item__type=ItemType.EQUIP
        ).prefetch_related("item")

        # 드롭다운 재생성
        to_remove = [item for item in self.children if isinstance(item, EnhancementItemDropdown)]
        for item in to_remove:
            self.remove_item(item)

        # 장비가 없어도 드롭다운 표시
        self.add_item(EnhancementItemDropdown(self.equipment_items))

    def create_default_embed(self) -> discord.Embed:
        """기본 임베드 (선택 전)"""
        embed = discord.Embed(
            title="⚒️ 아이템 강화",
            description="강화할 장비를 선택하세요.",
            color=discord.Color.blue()
        )

        embed.add_field(
            name="📊 강화 시스템",
            value=(
                "```\n"
                "+0~3  : 성공률 100% (실패 시 유지)\n"
                "+4~6  : 성공률 80%  (실패 시 유지)\n"
                "+7~9  : 성공률 60%  (실패 시 -1)\n"
                "+10~12: 성공률 40%  (실패 시 -2)\n"
                "+13~15: 성공률 20%  (실패 시 초기화, 20% 파괴)\n"
                "```"
            ),
            inline=False
        )

        embed.add_field(
            name="💡 강화 효과",
            value="```\n레벨당 모든 스탯 +5%\n+15 달성 시 최대 +75% 스탯\n```",
            inline=False
        )

        embed.set_footer(text="⬆️ 위 드롭다운에서 아이템을 선택하세요")
        return embed

    def create_info_embed(self, info: dict, result=None) -> discord.Embed:
        """강화 정보 임베드 (결과 포함 가능)"""
        item_name = info["item_name"]
        current_level = info["current_level"]
        cost = info["cost"]
        current_gold = info["current_gold"]

        # 등급별 색상 적용
        grade_id = info.get("grade_id", 3)
        formatted_name = format_item_name(item_name, grade_id)

        # 결과에 따라 타이틀과 색상 변경
        if result:
            if result.success:
                title = f"✅ 강화 성공!: {formatted_name} +{result.new_level}"
                color = discord.Color.green()
                result_text = f"**+{result.previous_level}** → **+{result.new_level}** 🎉"
            elif result.result_type == EnhancementResult.FAIL_MAINTAIN:
                title = f"❌ 강화 실패: {formatted_name} +{result.new_level}"
                color = discord.Color.orange()
                result_text = f"**+{result.previous_level}** (유지) 💫"
            elif result.result_type == EnhancementResult.FAIL_DECREASE:
                title = f"❌ 강화 실패: {formatted_name} +{result.new_level}"
                color = discord.Color.red()
                decrease = result.previous_level - result.new_level
                result_text = f"**+{result.previous_level}** → **+{result.new_level}** 📉 (-{decrease})"
            elif result.result_type == EnhancementResult.FAIL_RESET:
                title = f"❌ 강화 실패 - 초기화: {formatted_name}"
                color = discord.Color.dark_red()
                result_text = f"**+{result.previous_level}** → **+0** 💥"
            elif result.result_type == EnhancementResult.FAIL_DESTROY:
                title = f"💥 아이템 파괴!: {formatted_name}"
                color = discord.Color.from_rgb(0, 0, 0)
                result_text = f"**{item_name}**이(가) 파괴되었습니다... ☠️"
        else:
            title = f"⚒️ 강화: {formatted_name} +{current_level}"
            color = discord.Color.gold()
            result_text = None

        embed = discord.Embed(title=title, color=color)

        # 결과 표시 (있는 경우)
        if result_text:
            embed.add_field(
                name="📊 강화 결과",
                value=result_text,
                inline=False
            )

        # 강화 정보
        rate_desc = EnhancementService.get_success_rate_description(current_level)

        embed.add_field(
            name="📊 강화 정보",
            value=(
                f"```\n"
                f"현재 레벨 : +{current_level}\n"
                f"다음 레벨 : +{current_level + 1}\n"
                f"```"
            ),
            inline=True
        )

        embed.add_field(
            name="💰 비용",
            value=(
                f"```\n"
                f"필요 골드 : {cost:,}G\n"
                f"보유 골드 : {current_gold:,}G\n"
                f"```"
            ),
            inline=True
        )

        embed.add_field(
            name="🎲 성공률",
            value=f"```\n{rate_desc}\n```",
            inline=False
        )

        # 현재 보너스와 다음 보너스
        current_bonus = current_level * 5
        next_bonus = (current_level + 1) * 5

        embed.add_field(
            name="✨ 스탯 보너스",
            value=(
                f"```\n"
                f"현재: +{current_bonus}%\n"
                f"성공 시: +{next_bonus}%\n"
                f"```"
            ),
            inline=False
        )

        # Footer 설정
        if result:
            embed.add_field(
                name="💸 소모 골드",
                value=f"{result.cost:,}G",
                inline=True
            )
            embed.set_footer(text="⚒️ 강화를 계속하려면 위 드롭다운에서 아이템을 선택하세요")
        elif current_gold < cost:
            embed.set_footer(text="⚠️ 골드가 부족합니다!")
        else:
            embed.set_footer(text="⚒️ 강화 시도 버튼을 눌러 강화하세요")

        return embed

    def create_result_embed(self, result) -> discord.Embed:
        """강화 결과 임베드"""
        # 등급 정보는 다시 조회해야 하므로 기본 이름 사용
        item_name = result.item_name

        if result.success:
            embed = discord.Embed(
                title="✅ 강화 성공!",
                description=f"**{item_name}** +{result.previous_level} → **+{result.new_level}**",
                color=discord.Color.green()
            )
            embed.add_field(
                name="🎉 축하합니다!",
                value=f"스탯 보너스: +{result.new_level * 5}%",
                inline=False
            )

        else:
            if result.result_type == EnhancementResult.FAIL_MAINTAIN:
                embed = discord.Embed(
                    title="❌ 강화 실패",
                    description=f"**{item_name}** +{result.previous_level} (유지)",
                    color=discord.Color.orange()
                )
                embed.add_field(
                    name="💫 다행입니다",
                    value="강화 레벨이 유지되었습니다.",
                    inline=False
                )

            elif result.result_type == EnhancementResult.FAIL_DECREASE:
                embed = discord.Embed(
                    title="❌ 강화 실패",
                    description=f"**{item_name}** +{result.previous_level} → **+{result.new_level}**",
                    color=discord.Color.red()
                )
                decrease = result.previous_level - result.new_level
                embed.add_field(
                    name="📉 레벨 하락",
                    value=f"강화 레벨이 -{decrease} 감소했습니다.",
                    inline=False
                )

            elif result.result_type == EnhancementResult.FAIL_RESET:
                embed = discord.Embed(
                    title="❌ 강화 실패 - 초기화",
                    description=f"**{item_name}** +{result.previous_level} → **+0**",
                    color=discord.Color.dark_red()
                )
                embed.add_field(
                    name="💥 초기화",
                    value="강화 레벨이 0으로 초기화되었습니다.",
                    inline=False
                )

            elif result.result_type == EnhancementResult.FAIL_DESTROY:
                embed = discord.Embed(
                    title="💥 강화 실패 - 아이템 파괴!",
                    description=f"**{item_name}**이(가) 파괴되었습니다...",
                    color=discord.Color.from_rgb(0, 0, 0)
                )
                embed.add_field(
                    name="☠️ 파괴됨",
                    value="아이템이 영구적으로 사라졌습니다.",
                    inline=False
                )

        embed.add_field(
            name="💸 소모 골드",
            value=f"{result.cost:,}G",
            inline=True
        )

        return embed
