import discord
from discord import app_commands
from discord.ext import commands
from typing import List

from bot import GUILD_IDS


class GameGuidePagination(discord.ui.View):
    """게임 가이드 페이지네이션 View"""

    def __init__(self, embeds: List[discord.Embed], user_id: int):
        super().__init__(timeout=180)  # 3분 타임아웃
        self.embeds = embeds
        self.user_id = user_id
        self.current_page = 0
        self.max_pages = len(embeds)
        self._update_buttons()

    def _update_buttons(self):
        """버튼 상태 업데이트"""
        self.prev_button.disabled = self.current_page == 0
        self.next_button.disabled = self.current_page == self.max_pages - 1

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """본인만 조작 가능"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "다른 사람의 가이드는 조작할 수 없습니다.",
                ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="◀", style=discord.ButtonStyle.primary, custom_id="prev")
    async def prev_button(self, interaction: discord.Interaction, _: discord.ui.Button):
        """이전 페이지"""
        self.current_page = max(0, self.current_page - 1)
        self._update_buttons()
        await interaction.response.edit_message(embed=self.embeds[self.current_page], view=self)

    @discord.ui.button(label="▶", style=discord.ButtonStyle.primary, custom_id="next")
    async def next_button(self, interaction: discord.Interaction, _: discord.ui.Button):
        """다음 페이지"""
        self.current_page = min(self.max_pages - 1, self.current_page + 1)
        self._update_buttons()
        await interaction.response.edit_message(embed=self.embeds[self.current_page], view=self)


class HelpCommand(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="도움말",
        description="봇의 모든 명령어를 확인합니다"
    )
    @app_commands.guilds(*GUILD_IDS)
    async def help_command(self, interaction: discord.Interaction):
        """모든 명령어 목록을 보여줍니다."""
        embed = discord.Embed(
            title="📖 CUHA Bot 명령어 목록",
            description="CUHA Bot의 모든 명령어입니다.",
            color=discord.Color.blue()
        )

        # 기본 명령어
        embed.add_field(
            name="📌 기본 명령어",
            value=(
                "`/내정보` - 내 캐릭터 정보를 확인합니다\n"
                "`/게임설명` - 게임 시스템 설명을 봅니다\n"
                "`/도움말` - 이 도움말을 표시합니다\n"
                "`/설명` - 아이템/스킬/몬스터 정보를 검색합니다"
            ),
            inline=False
        )

        # 던전 및 전투
        embed.add_field(
            name="⚔️ 던전 & 전투",
            value=(
                "`/던전입장` - 던전을 선택하고 입장합니다\n"
                "`/도감` - 수집한 아이템/스킬/몬스터를 확인합니다"
            ),
            inline=False
        )

        # 스킬 관리
        embed.add_field(
            name="✨ 스킬 덱",
            value=(
                "`/덱` - 스킬 덱을 관리합니다 (10슬롯)\n"
                "스킬 덱은 전투에서 랜덤으로 사용됩니다"
            ),
            inline=False
        )

        # 장비 및 인벤토리
        embed.add_field(
            name="🎒 인벤토리",
            value=(
                "`/인벤토리` - 보유 아이템/장비를 관리합니다\n"
                "인벤토리에서 장비 장착, 아이템 사용 가능"
            ),
            inline=False
        )

        # 성장 시스템
        embed.add_field(
            name="📈 성장",
            value=(
                "`/스탯` - 레벨업 시 얻은 스탯 포인트를 분배합니다\n"
            ),
            inline=False
        )

        # 미니게임
        embed.add_field(
            name="🎲 미니게임",
            value=(
                "`/dice` - 주사위 게임\n"
                "`/rsp` - 가위바위보"
            ),
            inline=False
        )

        embed.set_footer(text="💡 명령어는 /를 입력하면 자동완성됩니다")

        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="게임설명",
        description="게임의 핵심 시스템을 설명합니다"
    )
    @app_commands.guilds(*GUILD_IDS)
    async def game_guide(self, interaction: discord.Interaction):
        """게임 시스템 전체 설명 (docs/ 기반)"""

        # 메인 embed
        main_embed = discord.Embed(
            title="🎮 CUHA Bot 게임 가이드",
            description="**덱빌딩 턴제 RPG 던전 탐험 게임**",
            color=discord.Color.gold()
        )

        main_embed.add_field(
            name="📖 게임 개요",
            value=(
                "**10개의 스킬 슬롯**에 스킬을 장착하고,\n"
                "매 턴 **랜덤으로 발동되는 스킬**로 전투합니다.\n"
                "\n"
                "같은 스킬을 여러 슬롯에 장착하면\n"
                "발동 확률이 증가합니다!\n"
                "\n"
                "예: 화염구 3개 → 30% 발동 확률"
            ),
            inline=False
        )

        # 전투 시스템 embed
        combat_embed = discord.Embed(
            title="⚔️ 전투 시스템",
            color=discord.Color.red()
        )

        combat_embed.add_field(
            name="🎲 스킬 덱 시스템 (Bag 방식)",
            value=(
                "**10개 슬롯** → 매 턴 랜덤 1개 발동\n"
                "**Bag 시스템**: 10턴마다 모든 스킬 1회씩 보장\n"
                "\n"
                "예시 덱:\n"
                "```\n"
                "[화염구×3] [치유×2] [버프×2] [공격×3]\n"
                "→ 10턴 안에 모든 스킬 최소 1회 발동!\n"
                "```\n"
                "**패시브 스킬도 덱 슬롯 차지!**"
            ),
            inline=False
        )

        combat_embed.add_field(
            name="🔄 전투 흐름",
            value=(
                "1️⃣ **내 턴**: 덱에서 랜덤 스킬 발동\n"
                "2️⃣ **몬스터 턴**: 몬스터 스킬 발동\n"
                "3️⃣ **턴 종료**: 버프/디버프 -1턴\n"
                "4️⃣ **DOT 적용**: 화상, 중독 등 피해\n"
                "5️⃣ 다음 턴 or 전투 종료"
            ),
            inline=False
        )

        combat_embed.add_field(
            name="⚠️ 전투 중 제한사항 (중요!)",
            value=(
                "전투 시작 후:\n"
                "❌ **아이템 사용 불가**\n"
                "❌ **스킬 덱 변경 불가**\n"
                "❌ **장비 변경 불가**\n"
                "✅ 도주 가능 (일반 몬스터만 50% 성공)\n"
                "\n"
                "💡 **전투 전 준비를 완벽하게!**"
            ),
            inline=False
        )

        # 성장 시스템 embed
        growth_embed = discord.Embed(
            title="📈 성장 시스템",
            color=discord.Color.green()
        )

        growth_embed.add_field(
            name="💪 5대 기본 능력치",
            value=(
                "**STR (힘)** - 물리 공격/HP/방어력\n"
                "**INT (지능)** - 마법 공격/마법 방어\n"
                "**DEX (민첩)** - 속도/회피/명중\n"
                "**VIT (활력)** - HP/방어력/HP 회복\n"
                "**LUK (행운)** - 치명타/드롭률\n"
                "\n"
                "레벨업 시 **3포인트** 획득!\n"
                "최대 Lv.100 (총 ~300pt)"
            ),
            inline=False
        )

        growth_embed.add_field(
            name="⚔️ 장비 시스템 (8슬롯)",
            value=(
                "**무기** / **투구** / **갑옷** / **장갑**\n"
                "**신발** / **목걸이** / **반지×2** / **보조무기**\n"
                "\n"
                "등급: D(1.0x) → C → B → A → S → SS → SSS → 신화(4.0x)\n"
                "능력치 요구: STR/INT/DEX/VIT/LUK\n"
                "\n"
                "던전 드랍 or 상점 구매"
            ),
            inline=False
        )

        growth_embed.add_field(
            name="✨ 스킬 등급 & 타입",
            value=(
                "**등급**: D(1.0x) ~ 신화(4.5x)\n"
                "\n"
                "**타입**:\n"
                "• attack - 공격 스킬 (권장 4~7개)\n"
                "• heal - 회복 스킬 (권장 1~3개)\n"
                "• buff - 강화 스킬 (권장 1~3개)\n"
                "• debuff - 약화 스킬 (권장 1~3개)\n"
                "• ultimate - 궁극기 (1회용, 강력)\n"
                "• passive - 패시브 (슬롯 차지)"
            ),
            inline=False
        )

        # 속성 시스템 embed
        element_embed = discord.Embed(
            title="🔥 속성 시스템",
            color=discord.Color.purple()
        )

        element_embed.add_field(
            name="⚡ 속성 상성 (원형 구조)",
            value=(
                "🔥 **화염** → ❄️ **냉기** → ⚡ **번개** → 💧 **수속성** → 🔥\n"
                "✨ **신성** ↔ 🌑 **암흑** (서로 강점)\n"
                "\n"
                "**강점 공격**: **×1.5 (150% 피해)**\n"
                "**동일 속성**: ×0.5 (50% 피해)\n"
                "**속성 면역**: ×0.0 (무효화)\n"
                "\n"
                "💡 속성 상성을 활용하여 덱을 구성하세요!"
            ),
            inline=False
        )

        element_embed.add_field(
            name="🔗 상태이상 체인 (키워드 시스템)",
            value=(
                "**화염**: 화상 → 소각 → 연소\n"
                "**냉기**: 둔화 → 동결 → 파쇄\n"
                "**번개**: 감전 → 마비 → 과부하\n"
                "**암흑**: 중독 → 저주 → 흡혈 → 감염\n"
                "**수속성**: 잠식 → 침수\n"
                "\n"
                "키워드 중첩으로 강력한 효과 발동!\n"
                "예: 화염 키워드 7개 → 화염 +35%"
            ),
            inline=False
        )

        # 팁 embed
        tips_embed = discord.Embed(
            title="💡 초보자 가이드",
            color=discord.Color.orange()
        )

        tips_embed.add_field(
            name="🎯 덱 빌딩 전략",
            value=(
                "**1️⃣ 균형형 덱 (추천)**\n"
                "   공격 5 + 회복/버프 5\n"
                "   턴당 기대 DPS: 50-80%\n"
                "\n"
                "**2️⃣ 공격형 덱**\n"
                "   공격 7 + 회복/버프 3\n"
                "   턴당 기대 DPS: 70-110%\n"
                "\n"
                "**3️⃣ 속성 특화 덱**\n"
                "   같은 속성 7개 이상\n"
                "   → 속성 밀도 시너지 +35%!\n"
                "\n"
                "💡 패시브는 1~2개가 적당"
            ),
            inline=False
        )

        tips_embed.add_field(
            name="🚀 시작 가이드",
            value=(
                "1️⃣ `/내정보` - 내 캐릭터 확인\n"
                "2️⃣ `/덱` - 스킬 10개 장착\n"
                "3️⃣ `/던전입장` - 첫 던전 도전\n"
                "4️⃣ 전투 → 경험치/골드/아이템 획득\n"
                "5️⃣ `/스탯` - 레벨업 시 포인트 분배\n"
                "6️⃣ `/인벤토리` - 장비 장착\n"
                "7️⃣ 더 강한 던전 도전!\n"
                "\n"
                "💡 **HP 자연회복**: 최대 HP의 1%/분\n"
                "   VIT 투자 시 회복률 증가"
            ),
            inline=False
        )

        # 페이지 정보 추가
        embeds = [main_embed, combat_embed, growth_embed, element_embed, tips_embed]

        for i, embed in enumerate(embeds, 1):
            embed.set_footer(text=f"📄 페이지 {i}/{len(embeds)} | ◀ ▶ 버튼으로 이동")

        # 마지막 페이지에 추가 메시지
        tips_embed.set_footer(text=f"📄 페이지 5/5 | 📚 자세한 내용은 docs/ 문서 참조 | 즐거운 모험 되세요! 🎮")

        # 페이지네이션 View와 함께 전송
        view = GameGuidePagination(embeds, interaction.user.id)
        await interaction.response.send_message(embed=embeds[0], view=view)


async def setup(bot: commands.Bot):
    await bot.add_cog(HelpCommand(bot))
