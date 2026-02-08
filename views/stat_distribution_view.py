"""
스탯 분배 View

5대 능력치(STR/INT/DEX/VIT/LUK)에 포인트를 분배하는 UI를 제공합니다.
드롭다운으로 능력치를 선택하고 버튼으로 포인트를 분배합니다.
"""
import discord
from discord import ui

from models import User
from service.player.stat_conversion import convert_abilities_to_combat_stats


# 능력치 정보 (포인트당 1:1 증가)
ABILITY_NAMES = {
    "str": "💪 STR (힘)",
    "int": "🧠 INT (지능)",
    "dex": "🏃 DEX (민첩)",
    "vit": "❤️ VIT (활력)",
    "luk": "🍀 LUK (행운)",
}

ABILITY_DESCRIPTIONS = {
    "str": "물리 공격 +2.5, HP +5, 물방 +0.3",
    "int": "마법 공격 +2.5, HP +2, 마방 +0.8",
    "dex": "속도 +1, 명중 +0.4%, 회피 +0.3%",
    "vit": "HP +12, 물방 +1.2, 회복 +0.04%",
    "luk": "물공 +0.5, 치확 +0.3%, 치뎀 +1%",
}

ABILITY_DB_FIELDS = {
    "str": "bonus_str",
    "int": "bonus_int",
    "dex": "bonus_dex",
    "vit": "bonus_vit",
    "luk": "bonus_luk",
}


class AbilitySelect(ui.Select):
    """능력치 선택 드롭다운"""

    def __init__(self):
        options = [
            discord.SelectOption(
                label="💪 STR (힘)", value="str",
                description=ABILITY_DESCRIPTIONS["str"]
            ),
            discord.SelectOption(
                label="🧠 INT (지능)", value="int",
                description=ABILITY_DESCRIPTIONS["int"]
            ),
            discord.SelectOption(
                label="🏃 DEX (민첩)", value="dex",
                description=ABILITY_DESCRIPTIONS["dex"]
            ),
            discord.SelectOption(
                label="❤️ VIT (활력)", value="vit",
                description=ABILITY_DESCRIPTIONS["vit"]
            ),
            discord.SelectOption(
                label="🍀 LUK (행운)", value="luk",
                description=ABILITY_DESCRIPTIONS["luk"]
            ),
        ]
        super().__init__(placeholder="능력치를 선택하세요", options=options, row=0)

    async def callback(self, interaction: discord.Interaction):
        self.view.selected_stat = self.values[0]
        self.view.pending_stats[self.view.selected_stat] = self.view.pending_stats.get(self.view.selected_stat, 0)
        await self.view._update_message(interaction)


class StatDistributionView(ui.View):
    """스탯 분배 View (5대 능력치 시스템)"""

    def __init__(self, discord_user: discord.User, db_user: User):
        super().__init__(timeout=120)
        self.discord_user = discord_user
        self.db_user = db_user
        self.message: discord.Message = None

        # 선택된 능력치
        self.selected_stat = "str"

        # 임시 분배 상태 (아직 저장되지 않음)
        self.pending_stats = {
            "str": 0,
            "int": 0,
            "dex": 0,
            "vit": 0,
            "luk": 0,
        }
        self.points_used = 0

        # 드롭다운 추가
        self.add_item(AbilitySelect())

    def _get_current_ability(self, key: str) -> int:
        """현재 능력치 값 조회"""
        field = ABILITY_DB_FIELDS[key]
        return getattr(self.db_user, field)

    def _get_preview_ability(self, key: str) -> int:
        """미리보기 능력치 값 (현재 + 대기분)"""
        return self._get_current_ability(key) + self.pending_stats[key]

    def create_embed(self) -> discord.Embed:
        """현재 상태 임베드 생성"""
        available = self.db_user.stat_points - self.points_used
        embed = discord.Embed(
            title="📊 스탯 분배",
            description=f"사용 가능한 포인트: **{available}** / {self.db_user.stat_points}",
            color=discord.Color.blue()
        )

        # 현재 능력치 + 대기중인 증가량 표시
        ability_lines = []
        for key, display_name in ABILITY_NAMES.items():
            current = self._get_current_ability(key)
            pending = self.pending_stats[key]
            marker = "▶ " if key == self.selected_stat else "  "

            if pending > 0:
                ability_lines.append(
                    f"{marker}{display_name}: {current} → **{current + pending}** (+{pending})"
                )
            else:
                ability_lines.append(f"{marker}{display_name}: {current}")

        embed.add_field(
            name="📈 능력치",
            value="\n".join(ability_lines),
            inline=False
        )

        # 변환 미리보기 (대기 중인 포인트 반영)
        preview_str = self._get_preview_ability("str")
        preview_int = self._get_preview_ability("int")
        preview_dex = self._get_preview_ability("dex")
        preview_vit = self._get_preview_ability("vit")
        preview_luk = self._get_preview_ability("luk")

        bonus = convert_abilities_to_combat_stats(
            preview_str, preview_int, preview_dex, preview_vit, preview_luk
        )

        embed.add_field(
            name="⚔️ 전투 스탯 (변환)",
            value=(
                f"```\n"
                f"HP       : +{bonus.hp}\n"
                f"물리공격 : +{bonus.attack}\n"
                f"마법공격 : +{bonus.ap_attack}\n"
                f"물리방어 : +{bonus.ad_defense}\n"
                f"마법방어 : +{bonus.ap_defense}\n"
                f"속도     : +{bonus.speed}\n"
                f"```"
            ),
            inline=True
        )

        embed.add_field(
            name="🎯 보조 스탯 (변환)",
            value=(
                f"```\n"
                f"명중률   : +{bonus.accuracy:.1f}%\n"
                f"회피율   : +{bonus.evasion:.1f}%\n"
                f"치명타율 : +{bonus.crit_rate:.1f}%\n"
                f"치명타뎀 : +{bonus.crit_damage:.1f}%\n"
                f"드롭률   : +{bonus.drop_rate:.1f}%\n"
                f"```"
            ),
            inline=True
        )

        # 선택된 능력치 상세
        selected_name = ABILITY_NAMES[self.selected_stat]
        selected_desc = ABILITY_DESCRIPTIONS[self.selected_stat]
        current_value = self._get_current_ability(self.selected_stat)
        pending_value = self.pending_stats[self.selected_stat]

        embed.add_field(
            name=f"🎯 선택: {selected_name}",
            value=(
                f"현재: {current_value}\n"
                f"증가 예정: +{pending_value}\n"
                f"효과: {selected_desc}"
            ),
            inline=False
        )

        if self.points_used > 0:
            embed.set_footer(text="💡 저장 버튼을 눌러 적용하세요. 초기화로 다시 분배할 수 있습니다.")
        else:
            embed.set_footer(text="💡 드롭다운에서 능력치를 선택한 후 버튼으로 포인트를 분배하세요.")

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
        """선택된 능력치에 포인트 추가"""
        available = self.db_user.stat_points - self.points_used
        if available < amount:
            return False

        self.pending_stats[self.selected_stat] += amount
        self.points_used += amount
        return True

    def _remove_stat(self, amount: int = 1) -> bool:
        """선택된 능력치에서 포인트 제거"""
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

        # 능력치 적용 (1:1 직접 증가)
        for key, points in self.pending_stats.items():
            if points > 0:
                field = ABILITY_DB_FIELDS[key]
                current = getattr(self.db_user, field)
                setattr(self.db_user, field, current + points)

        # 포인트 차감
        self.db_user.stat_points -= self.points_used

        # DB 저장
        await self.db_user.save()

        # 결과 메시지
        embed = discord.Embed(
            title="✅ 스탯 분배 완료!",
            color=discord.Color.green()
        )

        for key, display_name in ABILITY_NAMES.items():
            current = self._get_current_ability(key)
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
        self.pending_stats = {"str": 0, "int": 0, "dex": 0, "vit": 0, "luk": 0}
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


# Legacy compatibility: StatOverviewView, StatSelectView removed
# The new system uses a single StatDistributionView with AbilitySelect dropdown
