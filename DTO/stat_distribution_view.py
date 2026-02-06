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
        if hasattr(self.view, "on_stat_selected"):
            await self.view.on_stat_selected(self.values[0], interaction)
            return
        self.view.selected_stat = self.values[0]
        await self.view._update_message(interaction)


class StatOverviewView(ui.View):
    """스탯 분배 개요 View"""

    def __init__(self, discord_user: discord.User, db_user: User):
        super().__init__(timeout=120)
        self.discord_user = discord_user
        self.db_user = db_user
        self.message: discord.Message = None
        self.preview_stat: str | None = None
        self.preview_points: int = 0

    def create_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="📊 스탯 분배",
            description=f"사용 가능한 포인트: **{self.db_user.stat_points}**",
            color=discord.Color.blue()
        )
        stat_lines = []
        for stat_key, display_name in STAT_NAMES.items():
            current = getattr(self.db_user, stat_key)
            marker = "▶ " if stat_key == self.preview_stat else "  "
            if stat_key == self.preview_stat and self.preview_points > 0:
                increment = STAT_INCREMENTS[stat_key]
                delta = self.preview_points * increment
                stat_lines.append(f"{marker}{display_name}: {current} (+{delta})")
            else:
                stat_lines.append(f"{marker}{display_name}: {current}")

        embed.add_field(
            name="현재 스탯",
            value="\n".join(stat_lines),
            inline=False
        )
        embed.add_field(
            name="안내",
            value="스탯 선택 창에서 분배할 스탯을 고르세요.",
            inline=False
        )
        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.discord_user.id:
            await interaction.response.send_message(
                "다른 사람의 스탯 분배를 할 수 없습니다.",
                ephemeral=True
            )
            return False
        return True

    async def refresh_message(self) -> None:
        if self.message:
            embed = self.create_embed()
            await self.message.edit(embed=embed, view=self)

    async def update_preview(self, stat_key: str | None, points: int) -> None:
        self.preview_stat = stat_key
        self.preview_points = max(points, 0)
        await self.refresh_message()

    @ui.button(label="닫기", style=discord.ButtonStyle.danger)
    async def close(self, interaction: discord.Interaction, button: ui.Button):
        self.stop()
        await interaction.response.edit_message(content="스탯 분배 창을 닫았습니다.", embed=None, view=None)


class StatSelectView(ui.View):
    """스탯 선택 View"""

    def __init__(self, discord_user: discord.User, db_user: User, parent_view: StatOverviewView):
        super().__init__(timeout=120)
        self.discord_user = discord_user
        self.db_user = db_user
        self.parent_view = parent_view
        self.message: discord.Message = None
        self.selected_stat = "hp"
        self.points_used = 0
        self.add_item(StatSelect())
        self.add_item(StatAdjustButton("+1", 1))
        self.add_item(StatAdjustButton("+5", 5))
        self.add_item(StatAdjustButton("+10", 10))
        self.add_item(StatAdjustButton("-1", -1))
        self.add_item(StatAdjustButton("-5", -5))
        self.add_item(StatSaveButton())
        self.add_item(StatSelectCloseButton())

    def create_embed(self) -> discord.Embed:
        available = self.db_user.stat_points
        embed = discord.Embed(
            title="📊 스탯 분배 - 선택",
            description=f"사용 가능한 포인트: **{available}**",
            color=discord.Color.blue()
        )
        selected_name = STAT_NAMES[self.selected_stat]
        current = getattr(self.db_user, self.selected_stat)
        increment = STAT_INCREMENTS[self.selected_stat]
        embed.add_field(
            name=f"🎯 선택: {selected_name}",
            value=(
                f"현재: {current}\n"
                f"증가 예정: +{self.points_used * increment}\n"
                f"포인트당: +{increment}"
            ),
            inline=False
        )
        embed.set_footer(text="선택 후 포인트를 조절하고 저장하세요.")
        return embed

    async def on_stat_selected(self, stat_key: str, interaction: discord.Interaction):
        self.selected_stat = stat_key
        self.points_used = 0
        embed = self.create_embed()
        await interaction.response.edit_message(embed=embed, view=self)
        await self.parent_view.update_preview(self.selected_stat, self.points_used)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.discord_user.id:
            await interaction.response.send_message(
                "다른 사람의 스탯 분배를 할 수 없습니다.",
                ephemeral=True
            )
            return False
        return True

    async def refresh_message(self) -> None:
        if self.message:
            embed = self.create_embed()
            await self.message.edit(embed=embed, view=self)


class StatAdjustButton(ui.Button):
    """스탯 조절 버튼"""

    def __init__(self, label: str, delta: int):
        style = discord.ButtonStyle.primary if delta > 0 else discord.ButtonStyle.secondary
        super().__init__(label=label, style=style, row=1)
        self.delta = delta

    async def callback(self, interaction: discord.Interaction):
        view: StatSelectView = self.view
        if self.delta > 0:
            available = view.db_user.stat_points - view.points_used
            if available < self.delta:
                await interaction.response.send_message("포인트가 부족합니다!", ephemeral=True)
                return
            view.points_used += self.delta
        else:
            if view.points_used < abs(self.delta):
                await interaction.response.send_message("제거할 포인트가 없습니다!", ephemeral=True)
                return
            view.points_used += self.delta

        embed = view.create_embed()
        await interaction.response.edit_message(embed=embed, view=view)
        await view.parent_view.update_preview(view.selected_stat, view.points_used)


class StatSaveButton(ui.Button):
    """저장 버튼"""

    def __init__(self):
        super().__init__(label="💾 저장", style=discord.ButtonStyle.success, row=3)

    async def callback(self, interaction: discord.Interaction):
        view: StatSelectView = self.view
        if view.points_used == 0:
            await interaction.response.send_message("분배할 포인트가 없습니다!", ephemeral=True)
            return

        increment = STAT_INCREMENTS[view.selected_stat]
        current = getattr(view.db_user, view.selected_stat)
        setattr(view.db_user, view.selected_stat, current + view.points_used * increment)

        if view.selected_stat == "hp":
            hp_increase = view.points_used * increment
            view.db_user.now_hp = min(view.db_user.now_hp + hp_increase, view.db_user.hp)

        view.db_user.stat_points -= view.points_used
        await view.db_user.save()

        await view.parent_view.refresh_message()

        view.points_used = 0
        embed = view.create_embed()
        embed.add_field(
            name="✅ 저장 완료",
            value=f"{STAT_NAMES[view.selected_stat]}에 포인트가 분배되었습니다.",
            inline=False
        )
        await interaction.response.edit_message(embed=embed, view=view)
        await view.parent_view.update_preview(None, 0)


class StatSelectCloseButton(ui.Button):
    """선택 창 닫기"""

    def __init__(self):
        super().__init__(label="닫기", style=discord.ButtonStyle.danger, row=3)

    async def callback(self, interaction: discord.Interaction):
        view: StatSelectView = self.view
        await interaction.response.edit_message(content="스탯 선택 창을 닫았습니다.", embed=None, view=None)
        if view.parent_view and view.parent_view.message:
            try:
                await view.parent_view.message.edit(
                    content="스탯 분배 창을 닫았습니다.",
                    embed=None,
                    view=None
                )
            except discord.NotFound:
                pass


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
