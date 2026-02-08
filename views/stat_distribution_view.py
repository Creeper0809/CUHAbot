"""
스탯 분배 View

5대 능력치(STR/INT/DEX/VIT/LUK)에 포인트를 분배하는 UI를 제공합니다.
드롭다운으로 능력치를 선택하고 버튼으로 포인트를 분배합니다.
"""
import discord
from discord import ui

from config import STAT_CONVERSION as C, USER_STATS
from models import User
from models.user_inventory import UserInventory
from service.player.stat_conversion import convert_abilities_to_combat_stats, calculate_hp_regen_rate


def _fmt(value: float, suffix: str = "") -> str:
    """계수를 깔끔한 문자열로 포맷 (정수면 소수점 제거)"""
    return f"+{value:g}{suffix}"


# 능력치 정보 (포인트당 1:1 증가)
ABILITY_NAMES = {
    "str": "💪 STR (힘)",
    "int": "🧠 INT (지능)",
    "dex": "🏃 DEX (민첩)",
    "vit": "❤️ VIT (활력)",
    "luk": "🍀 LUK (행운)",
}

ABILITY_DESCRIPTIONS = {
    "str": f"물리공격 {_fmt(C.ATTACK_STR)}, HP {_fmt(C.HP_STR)}, 물방 {_fmt(C.AD_DEFENSE_STR)}",
    "int": f"마법공격 {_fmt(C.AP_ATTACK_INT)}, HP {_fmt(C.HP_INT)}, 마방 {_fmt(C.AP_DEFENSE_INT)}",
    "dex": f"속도 {_fmt(C.SPEED_DEX)}, 명중 {_fmt(C.ACCURACY_DEX, '%')}, 회피 {_fmt(C.EVASION_DEX, '%')}",
    "vit": f"HP {_fmt(C.HP_VIT)}, 물방 {_fmt(C.AD_DEFENSE_VIT)}, 회복 {_fmt(C.HP_REGEN_VIT * 100, '%')}",
    "luk": f"물공 {_fmt(C.ATTACK_LUK)}, 치확 {_fmt(C.CRIT_RATE_LUK, '%')}, 치뎀 {_fmt(C.CRIT_DAMAGE_LUK, '%')}",
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

        # 현재 능력치 기반 변환 (기존)
        cur_str = self._get_current_ability("str")
        cur_int = self._get_current_ability("int")
        cur_dex = self._get_current_ability("dex")
        cur_vit = self._get_current_ability("vit")
        cur_luk = self._get_current_ability("luk")
        cur = convert_abilities_to_combat_stats(cur_str, cur_int, cur_dex, cur_vit, cur_luk)

        # 미리보기 변환 (기존 + 대기)
        pre = convert_abilities_to_combat_stats(
            self._get_preview_ability("str"), self._get_preview_ability("int"),
            self._get_preview_ability("dex"), self._get_preview_ability("vit"),
            self._get_preview_ability("luk"),
        )

        def _diff_int(cur_val: int, pre_val: int) -> str:
            delta = pre_val - cur_val
            if delta > 0:
                return f"+{cur_val} (+{delta})"
            return f"+{cur_val}"

        def _diff_pct(cur_val: float, pre_val: float) -> str:
            delta = pre_val - cur_val
            if delta > 0.05:
                return f"+{cur_val:.1f}% (+{delta:.1f}%)"
            return f"+{cur_val:.1f}%"

        embed.add_field(
            name="⚔️ 전투 스탯 (변환)",
            value=(
                f"```\n"
                f"HP       : {_diff_int(cur.hp, pre.hp)}\n"
                f"물리공격 : {_diff_int(cur.attack, pre.attack)}\n"
                f"마법공격 : {_diff_int(cur.ap_attack, pre.ap_attack)}\n"
                f"물리방어 : {_diff_int(cur.ad_defense, pre.ad_defense)}\n"
                f"마법방어 : {_diff_int(cur.ap_defense, pre.ap_defense)}\n"
                f"속도     : {_diff_int(cur.speed, pre.speed)}\n"
                f"```"
            ),
            inline=True
        )

        cur_regen_bonus = cur_vit * C.HP_REGEN_VIT * 100
        pre_regen_bonus = self._get_preview_ability("vit") * C.HP_REGEN_VIT * 100
        regen_text = _diff_pct(cur_regen_bonus, pre_regen_bonus)

        embed.add_field(
            name="🎯 보조 스탯 (변환)",
            value=(
                f"```\n"
                f"명중률   : {_diff_pct(cur.accuracy, pre.accuracy)}\n"
                f"회피율   : {_diff_pct(cur.evasion, pre.evasion)}\n"
                f"치명타율 : {_diff_pct(cur.crit_rate, pre.crit_rate)}\n"
                f"치명타뎀 : {_diff_pct(cur.crit_damage, pre.crit_damage)}\n"
                f"드롭률   : {_diff_pct(cur.drop_rate, pre.drop_rate)}\n"
                f"HP회복   : {regen_text}\n"
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

    @ui.button(label="↩ 되돌리기", style=discord.ButtonStyle.secondary, row=2)
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

    @ui.button(label="⚠ 전체 리셋 (스크롤 필요)", style=discord.ButtonStyle.danger, row=3)
    async def full_reset_button(self, interaction: discord.Interaction, button: ui.Button):
        total_allocated = sum(
            self._get_current_ability(key) for key in ABILITY_DB_FIELDS
        )
        if total_allocated == 0:
            await interaction.response.send_message(
                "리셋할 능력치가 없습니다!", ephemeral=True,
            )
            return

        # 스탯 초기화 스크롤 보유 확인
        scroll_id = USER_STATS.STAT_RESET_SCROLL_ID
        scroll_inv = await UserInventory.get_or_none(
            user=self.db_user, item_id=scroll_id,
        )
        if not scroll_inv or scroll_inv.quantity <= 0:
            await interaction.response.send_message(
                "📜 **스탯 초기화 스크롤**이 필요합니다!\n"
                "상점에서 구매하거나 던전에서 획득하세요.",
                ephemeral=True,
            )
            return

        # 확인 뷰로 전환
        confirm_view = StatResetConfirmView(self, scroll_inv, total_allocated)
        embed = discord.Embed(
            title="⚠ 스탯 전체 리셋 확인",
            description=(
                f"📜 **스탯 초기화 스크롤** 1개를 소모합니다.\n"
                f"(보유: {scroll_inv.quantity}개)\n\n"
                f"현재 능력치:\n"
                f"  STR: {self._get_current_ability('str')}"
                f" / INT: {self._get_current_ability('int')}"
                f" / DEX: {self._get_current_ability('dex')}\n"
                f"  VIT: {self._get_current_ability('vit')}"
                f" / LUK: {self._get_current_ability('luk')}\n\n"
                f"**반환 포인트: +{total_allocated}**\n\n"
                f"정말로 초기화하시겠습니까?"
            ),
            color=discord.Color.orange()
        )
        await interaction.response.edit_message(embed=embed, view=confirm_view)

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


class StatResetConfirmView(ui.View):
    """스탯 리셋 최종 확인 뷰"""

    def __init__(self, parent: StatDistributionView, scroll_inv, total_allocated: int):
        super().__init__(timeout=30)
        self.parent = parent
        self.scroll_inv = scroll_inv
        self.total_allocated = total_allocated

    @ui.button(label="확인", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: ui.Button):
        # 스크롤 소모
        self.scroll_inv.quantity -= 1
        if self.scroll_inv.quantity <= 0:
            await self.scroll_inv.delete()
        else:
            await self.scroll_inv.save()

        # 모든 능력치 → 0, 포인트 환불
        for key in ABILITY_DB_FIELDS:
            setattr(self.parent.db_user, ABILITY_DB_FIELDS[key], 0)

        self.parent.db_user.stat_points += self.total_allocated
        await self.parent.db_user.save()

        # 부모 뷰 대기 상태 초기화
        self.parent.pending_stats = {"str": 0, "int": 0, "dex": 0, "vit": 0, "luk": 0}
        self.parent.points_used = 0

        embed = discord.Embed(
            title="⚠ 스탯 전체 리셋 완료",
            description=(
                f"📜 스탯 초기화 스크롤 1개를 사용했습니다.\n"
                f"모든 능력치가 0으로 초기화되었습니다.\n"
                f"**+{self.total_allocated}** 포인트가 환불되었습니다.\n"
                f"사용 가능 포인트: **{self.parent.db_user.stat_points}**"
            ),
            color=discord.Color.orange()
        )
        await interaction.response.edit_message(embed=embed, view=self.parent)
        self.stop()

    @ui.button(label="취소", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: ui.Button):
        # 부모 뷰로 복귀
        embed = self.parent.create_embed()
        await interaction.response.edit_message(embed=embed, view=self.parent)
        self.stop()
