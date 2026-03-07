"""
주간 타워 UI
"""
from __future__ import annotations

import discord
import os

from config import EmbedColor
from service.tower.tower_service import is_boss_floor


class TowerEntryView(discord.ui.View):
    def __init__(self, user: discord.User, timeout: int = 60):
        super().__init__(timeout=timeout)
        self.user = user
        self.action = None
        if os.getenv("E2E_UI_AUTOPILOT") == "TRUE":
            self.action = "enter"
            self.stop()

    def create_embed(self, season_id: int, progress) -> discord.Embed:
        current_floor = progress.current_floor if progress.current_floor > 0 else 1
        embed = discord.Embed(
            title="🗼 주간 타워",
            description=(
                f"현재 시즌: **{season_id}**\n"
                f"최고 기록: **{progress.highest_floor_reached}층**\n"
                f"현재 위치: **{current_floor}층**"
            ),
            color=EmbedColor.DEFAULT
        )
        embed.add_field(
            name="⚠️ 주의사항",
            value=(
                "• 아이템 사용 불가\n"
                "• 휴식공간에서만 스킬/장비 변경 가능\n"
                "• 도주 불가\n"
                "• 사망 시 1층부터 재시작"
            ),
            inline=False
        )
        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("본인만 사용할 수 있습니다.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="입장", style=discord.ButtonStyle.success, emoji="🗼")
    async def enter(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.action = "enter"
        self.stop()
        await interaction.response.edit_message(view=None)

    @discord.ui.button(label="취소", style=discord.ButtonStyle.danger, emoji="❌")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.action = "cancel"
        self.stop()
        await interaction.response.edit_message(content="주간 타워 입장을 취소했습니다.", embed=None, view=None)


class TowerFloorClearView(discord.ui.View):
    def __init__(self, user: discord.User, cleared_floor: int, timeout: int = 120):
        super().__init__(timeout=timeout)
        self.user = user
        self.cleared_floor = cleared_floor
        self.action = None
        if os.getenv("E2E_UI_AUTOPILOT") == "TRUE":
            max_floors = int(os.getenv("E2E_TOWER_MAX_FLOORS") or 1)
            self.action = "return" if self.cleared_floor >= max_floors else "next"
            self.stop()

    def create_embed(self, db_user, reward_result, tower_coins: int) -> discord.Embed:
        next_floor = self.cleared_floor + 1
        boss_warning = "\n⚠️ 다음은 보스층입니다!" if is_boss_floor(next_floor) else ""

        embed = discord.Embed(
            title=f"✅ {self.cleared_floor}층 클리어!",
            description=(
                f"🎉 층별 보상\n"
                f"💎 경험치: +{reward_result.exp_gained:,}\n"
                f"💰 골드: +{reward_result.gold_gained:,}\n"
                f"🪙 타워 코인: +{tower_coins}\n"
                f"❤️ HP: {db_user.now_hp}/{db_user.hp}\n"
                f"📈 Lv.{db_user.level}{boss_warning}"
            ),
            color=EmbedColor.DEFAULT
        )
        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("본인만 사용할 수 있습니다.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="다음 층", style=discord.ButtonStyle.success, emoji="➡️")
    async def next_floor(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.action = "next"
        self.stop()
        await interaction.response.edit_message(view=None)

    @discord.ui.button(label="귀환", style=discord.ButtonStyle.danger, emoji="🚪")
    async def return_tower(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.action = "return"
        self.stop()
        await interaction.response.edit_message(content="주간 타워를 종료했습니다.", embed=None, view=None)
