"""
스탯 분배 View

스탯 포인트를 분배하는 UI를 제공합니다.
드롭다운으로 스탯을 선택하고 버튼으로 포인트를 분배합니다.
"""
import discord
from discord import ui

from models import User


# 스탯별 증가량
STAT_INCREMENTS = {
    "hp": 10,           # 1포인트당 HP +10
    "attack": 2,        # 1포인트당 물리 공격력 +2
    "defense": 2,       # 1포인트당 물리 방어력 +2
    "speed": 1,         # 1포인트당 속도 +1
    "ap_attack": 2,     # 1포인트당 마법 공격력 +2
    "ap_defense": 2,    # 1포인트당 마법 방어력 +2
}

# 스탯 표시 이름
STAT_NAMES = {
    "hp": "❤️ HP",
    "attack": "⚔️ 물리공격",
    "defense": "🛡️ 물리방어",
    "speed": "💨 속도",
    "ap_attack": "✨ 마법공격",
    "ap_defense": "🔮 마법방어",
}


class StatSelect(ui.Select):
    """스탯 선택 드롭다운"""

    def __init__(self):
        options = [
            discord.SelectOption(label="❤️ HP", value="hp", description=f"1포인트당 +{STAT_INCREMENTS['hp']}"),
            discord.SelectOption(label="⚔️ 물리공격", value="attack", description=f"1포인트당 +{STAT_INCREMENTS['attack']}"),
            discord.SelectOption(label="🛡️ 물리방어", value="defense", description=f"1포인트당 +{STAT_INCREMENTS['defense']}"),
            discord.SelectOption(label="💨 속도", value="speed", description=f"1포인트당 +{STAT_INCREMENTS['speed']}"),
            discord.SelectOption(label="✨ 마법공격", value="ap_attack", description=f"1포인트당 +{STAT_INCREMENTS['ap_attack']}"),
            discord.SelectOption(label="🔮 마법방어", value="ap_defense", description=f"1포인트당 +{STAT_INCREMENTS['ap_defense']}"),
        ]
        super().__init__(placeholder="스탯을 선택하세요", options=options, row=0)

    async def callback(self, interaction: discord.Interaction):
        self.view.selected_stat = self.values[0]
        await self.view._update_message(interaction)


class StatDistributionView(ui.View):
    """스탯 분배 View"""

    def __init__(self, discord_user: discord.User, db_user: User):
        super().__init__(timeout=120)
        self.discord_user = discord_user
        self.db_user = db_user
        self.message: discord.Message = None

        # 선택된 스탯
        self.selected_stat = "hp"

        # 임시 분배 상태 (아직 저장되지 않음)
        self.pending_stats = {
            "hp": 0,
            "attack": 0,
            "defense": 0,
            "speed": 0,
            "ap_attack": 0,
            "ap_defense": 0,
        }
        self.points_used = 0

        # 드롭다운 추가
        self.add_item(StatSelect())

    def create_embed(self) -> discord.Embed:
        """현재 상태 임베드 생성"""
        available = self.db_user.stat_points - self.points_used
        embed = discord.Embed(
            title="📊 스탯 분배",
            description=f"사용 가능한 포인트: **{available}** / {self.db_user.stat_points}",
            color=discord.Color.blue()
        )

        # 현재 스탯 + 대기중인 증가량 표시
        stat_lines_left = []
        stat_lines_right = []

        for i, (stat_key, display_name) in enumerate(STAT_NAMES.items()):
            current = getattr(self.db_user, stat_key)
            pending = self.pending_stats[stat_key]
            increment = STAT_INCREMENTS[stat_key]

            # 선택된 스탯 표시
            marker = "▶ " if stat_key == self.selected_stat else "  "

            if pending > 0:
                line = f"{marker}{display_name}: {current} → **{current + pending * increment}** (+{pending * increment})"
            else:
                line = f"{marker}{display_name}: {current}"

            if i < 3:
                stat_lines_left.append(line)
            else:
                stat_lines_right.append(line)

        embed.add_field(
            name="📈 물리 스탯",
            value="\n".join(stat_lines_left),
            inline=True
        )

        embed.add_field(
            name="✨ 마법/속도",
            value="\n".join(stat_lines_right),
            inline=True
        )

        # 선택된 스탯 정보
        selected_name = STAT_NAMES[self.selected_stat]
        selected_increment = STAT_INCREMENTS[self.selected_stat]
        current_value = getattr(self.db_user, self.selected_stat)
        pending_value = self.pending_stats[self.selected_stat]

        embed.add_field(
            name=f"🎯 선택: {selected_name}",
            value=(
                f"현재: {current_value}\n"
                f"증가 예정: +{pending_value * selected_increment}\n"
                f"포인트당: +{selected_increment}"
            ),
            inline=False
        )

        if self.points_used > 0:
            embed.set_footer(text="💡 저장 버튼을 눌러 적용하세요. 초기화로 다시 분배할 수 있습니다.")
        else:
            embed.set_footer(text="💡 드롭다운에서 스탯을 선택한 후 버튼으로 포인트를 분배하세요.")

        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.discord_user.id:
            await interaction.response.send_message(
                "다른 사람의 스탯 분배를 할 수 없습니다.",
                ephemeral=True
            )
            return False
        return True

    def _add_stat(self, amount: int = 1) -> bool:
        """선택된 스탯에 포인트 추가"""
        available = self.db_user.stat_points - self.points_used
        if available < amount:
            return False

        self.pending_stats[self.selected_stat] += amount
        self.points_used += amount
        return True

    def _remove_stat(self, amount: int = 1) -> bool:
        """선택된 스탯에서 포인트 제거"""
        if self.pending_stats[self.selected_stat] < amount:
            return False

        self.pending_stats[self.selected_stat] -= amount
        self.points_used -= amount
        return True

    async def _update_message(self, interaction: discord.Interaction):
        """메시지 업데이트"""
        embed = self.create_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    # 포인트 증감 버튼
    @ui.button(label="+1", style=discord.ButtonStyle.primary, row=1)
    async def add_1(self, interaction: discord.Interaction, button: ui.Button):
        if self._add_stat(1):
            await self._update_message(interaction)
        else:
            await interaction.response.send_message("포인트가 부족합니다!", ephemeral=True)

    @ui.button(label="+5", style=discord.ButtonStyle.primary, row=1)
    async def add_5(self, interaction: discord.Interaction, button: ui.Button):
        if self._add_stat(5):
            await self._update_message(interaction)
        else:
            await interaction.response.send_message("포인트가 부족합니다!", ephemeral=True)

    @ui.button(label="+10", style=discord.ButtonStyle.primary, row=1)
    async def add_10(self, interaction: discord.Interaction, button: ui.Button):
        if self._add_stat(10):
            await self._update_message(interaction)
        else:
            await interaction.response.send_message("포인트가 부족합니다!", ephemeral=True)

    @ui.button(label="-1", style=discord.ButtonStyle.secondary, row=1)
    async def remove_1(self, interaction: discord.Interaction, button: ui.Button):
        if self._remove_stat(1):
            await self._update_message(interaction)
        else:
            await interaction.response.send_message("제거할 포인트가 없습니다!", ephemeral=True)

    @ui.button(label="-5", style=discord.ButtonStyle.secondary, row=1)
    async def remove_5(self, interaction: discord.Interaction, button: ui.Button):
        if self._remove_stat(5):
            await self._update_message(interaction)
        else:
            await interaction.response.send_message("제거할 포인트가 없습니다!", ephemeral=True)

    # 저장/초기화/취소 버튼들
    @ui.button(label="💾 저장", style=discord.ButtonStyle.success, row=2)
    async def save_button(self, interaction: discord.Interaction, button: ui.Button):
        if self.points_used == 0:
            await interaction.response.send_message("분배할 포인트가 없습니다!", ephemeral=True)
            return

        # 스탯 적용
        for stat_key, points in self.pending_stats.items():
            if points > 0:
                increment = STAT_INCREMENTS[stat_key]
                current = getattr(self.db_user, stat_key)
                setattr(self.db_user, stat_key, current + points * increment)

        # HP 분배 시 now_hp도 증가
        if self.pending_stats["hp"] > 0:
            hp_increase = self.pending_stats["hp"] * STAT_INCREMENTS["hp"]
            self.db_user.now_hp = min(self.db_user.now_hp + hp_increase, self.db_user.hp)

        # 포인트 차감
        self.db_user.stat_points -= self.points_used

        # DB 저장
        await self.db_user.save()

        # 결과 메시지
        embed = discord.Embed(
            title="✅ 스탯 분배 완료!",
            color=discord.Color.green()
        )

        for stat_key, display_name in STAT_NAMES.items():
            current = getattr(self.db_user, stat_key)
            embed.add_field(name=display_name, value=str(current), inline=True)

        embed.add_field(
            name="남은 포인트",
            value=str(self.db_user.stat_points),
            inline=False
        )

        await interaction.response.edit_message(embed=embed, view=None)
        self.stop()

    @ui.button(label="🔄 초기화", style=discord.ButtonStyle.secondary, row=2)
    async def reset_button(self, interaction: discord.Interaction, button: ui.Button):
        self.pending_stats = {"hp": 0, "attack": 0, "defense": 0, "speed": 0, "ap_attack": 0, "ap_defense": 0}
        self.points_used = 0
        await self._update_message(interaction)

    @ui.button(label="❌ 취소", style=discord.ButtonStyle.secondary, row=2)
    async def cancel_button(self, interaction: discord.Interaction, button: ui.Button):
        embed = discord.Embed(
            title="❌ 스탯 분배 취소",
            description="분배를 취소했습니다.",
            color=discord.Color.greyple()
        )
        await interaction.response.edit_message(embed=embed, view=None)
        self.stop()

    async def on_timeout(self):
        if self.message:
            embed = discord.Embed(
                title="⏰ 시간 초과",
                description="스탯 분배가 취소되었습니다.",
                color=discord.Color.greyple()
            )
            try:
                await self.message.edit(embed=embed, view=None)
            except discord.HTTPException:
                pass
