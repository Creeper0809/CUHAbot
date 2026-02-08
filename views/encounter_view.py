"""
인카운터 이벤트 View

던전에서 발생하는 다양한 인카운터에 대한 시각적 UI를 제공합니다.
"""
import asyncio
import discord
from typing import Optional, Callable, Any
from dataclasses import dataclass

from config import EmbedColor


# =============================================================================
# 보물상자 View
# =============================================================================

class TreasureView(discord.ui.View):
    """보물상자 인카운터 View"""

    def __init__(
        self,
        user: discord.User,
        chest_grade: str,
        timeout: int = 30
    ):
        super().__init__(timeout=timeout)
        self.user = user
        self.chest_grade = chest_grade
        self.opened = False
        self.message: Optional[discord.Message] = None

    def create_embed(
        self,
        opened: bool = False,
        gold: int = 0,
        item_name: Optional[str] = None
    ) -> discord.Embed:
        """임베드 생성"""
        grade_info = {
            "normal": ("📦", "낡은 상자", discord.Color.from_rgb(139, 90, 43)),
            "silver": ("🎁", "은빛 상자", discord.Color.from_rgb(192, 192, 192)),
            "gold": ("💎", "황금 상자", discord.Color.gold())
        }

        emoji, name, color = grade_info.get(self.chest_grade, ("📦", "상자", discord.Color.greyple()))

        if not opened:
            embed = discord.Embed(
                title=f"{emoji} {name} 발견!",
                description=(
                    "```\n"
                    "  ╔══════════════╗\n"
                    "  ║   📦 ? ? ?   ║\n"
                    "  ╚══════════════╝\n"
                    "```\n"
                    "상자를 열어 보물을 획득하세요!"
                ),
                color=color
            )
            embed.set_footer(text="열기 버튼을 눌러주세요")
        else:
            embed = discord.Embed(
                title=f"{emoji} {name} 열림!",
                description=(
                    "```\n"
                    "  ╔══════════════╗\n"
                    f"  ║  🎁 {item_name or f'{gold:,}G'}   ║\n"
                    "  ╚══════════════╝\n"
                    "```"
                ),
                color=color
            )
            if item_name:
                embed.add_field(
                    name="획득 보상",
                    value=f"🎁 **{item_name}**",
                    inline=False
                )
            else:
                embed.add_field(
                    name="획득 보상",
                    value=f"💰 **{gold:,}** 골드",
                    inline=False
                )

        return embed

    @discord.ui.button(label="상자 열기", style=discord.ButtonStyle.success, emoji="🔓")
    async def open_chest(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            await interaction.response.send_message("이 상자는 당신의 것이 아닙니다!", ephemeral=True)
            return

        self.opened = True
        self.stop()
        await interaction.response.defer()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user == self.user


# =============================================================================
# 함정 View
# =============================================================================

class TrapView(discord.ui.View):
    """함정 인카운터 View"""

    def __init__(
        self,
        user: discord.User,
        trap_name: str,
        damage: int,
        timeout: int = 30
    ):
        super().__init__(timeout=timeout)
        self.user = user
        self.trap_name = trap_name
        self.damage = damage
        self.escaped = False
        self.message: Optional[discord.Message] = None

    def create_embed(self, triggered: bool = False) -> discord.Embed:
        """임베드 생성"""
        trap_emojis = {
            "가시 함정": "🦔",
            "독 가스": "☠️",
            "함정 화살": "🏹",
            "낙하 함정": "🕳️",
            "폭발 함정": "💥"
        }

        trap_emoji = trap_emojis.get(self.trap_name, "⚠️")

        if not triggered:
            embed = discord.Embed(
                title=f"{trap_emoji} 함정 감지!",
                description=(
                    f"**{self.trap_name}**이(가) 작동하려 한다!\n\n"
                    "```diff\n"
                    f"- 예상 피해: {self.damage} HP\n"
                    "```\n"
                    "빠르게 회피를 시도하세요!"
                ),
                color=discord.Color.orange()
            )
            embed.set_footer(text="3초 안에 회피 버튼을 누르세요!")
        else:
            embed = discord.Embed(
                title=f"{trap_emoji} {self.trap_name} 작동!",
                description=(
                    "```diff\n"
                    f"- {self.damage} HP 피해를 받았다!\n"
                    "```"
                ),
                color=discord.Color.red()
            )

        return embed

    def create_escaped_embed(self) -> discord.Embed:
        """회피 성공 임베드"""
        return discord.Embed(
            title="💨 회피 성공!",
            description=f"**{self.trap_name}**을(를) 피했다!",
            color=discord.Color.green()
        )

    @discord.ui.button(label="회피!", style=discord.ButtonStyle.primary, emoji="💨")
    async def dodge_trap(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            await interaction.response.send_message("이것은 당신의 함정이 아닙니다!", ephemeral=True)
            return

        self.escaped = True
        self.stop()
        await interaction.response.defer()


# =============================================================================
# 랜덤 이벤트 View
# =============================================================================

class RandomEventView(discord.ui.View):
    """랜덤 이벤트 인카운터 View"""

    def __init__(
        self,
        user: discord.User,
        is_blessing: bool,
        event_type: str,
        timeout: int = 30
    ):
        super().__init__(timeout=timeout)
        self.user = user
        self.is_blessing = is_blessing
        self.event_type = event_type
        self.accepted = False
        self.message: Optional[discord.Message] = None

    def create_embed(self, before: bool = True) -> discord.Embed:
        """임베드 생성"""
        if self.is_blessing:
            if before:
                embed = discord.Embed(
                    title="✨ 신비로운 기운!",
                    description=(
                        "공기 중에 신비로운 에너지가 감돈다...\n\n"
                        "```\n"
                        "   ✧･ﾟ: *✧･ﾟ:*   *:･ﾟ✧*:･ﾟ✧\n"
                        "      축 복 의   기 운\n"
                        "   ✧･ﾟ: *✧･ﾟ:*   *:･ﾟ✧*:･ﾟ✧\n"
                        "```\n"
                        "축복을 받으시겠습니까?"
                    ),
                    color=discord.Color.gold()
                )
            else:
                embed = discord.Embed(
                    title="✨ 축복을 받았다!",
                    color=discord.Color.gold()
                )
        else:
            if before:
                embed = discord.Embed(
                    title="👻 불길한 기운...",
                    description=(
                        "어둠 속에서 무언가 다가온다...\n\n"
                        "```\n"
                        "   ～～～～～～～～～～～～～\n"
                        "      저 주 의   기 운\n"
                        "   ～～～～～～～～～～～～～\n"
                        "```\n"
                        "저주를 받게 될 것 같다..."
                    ),
                    color=discord.Color.dark_purple()
                )
            else:
                embed = discord.Embed(
                    title="👻 저주를 받았다...",
                    color=discord.Color.dark_purple()
                )

        return embed

    @discord.ui.button(label="받아들이기", style=discord.ButtonStyle.success, emoji="🙏")
    async def accept_event(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            await interaction.response.send_message("이것은 당신의 이벤트가 아닙니다!", ephemeral=True)
            return

        self.accepted = True
        self.stop()
        await interaction.response.defer()


# =============================================================================
# NPC View
# =============================================================================

class NPCView(discord.ui.View):
    """NPC 인카운터 View"""

    def __init__(
        self,
        user: discord.User,
        npc_type: str,
        timeout: int = 30
    ):
        super().__init__(timeout=timeout)
        self.user = user
        self.npc_type = npc_type
        self.interacted = False
        self.message: Optional[discord.Message] = None

    def create_embed(self, before: bool = True) -> discord.Embed:
        """임베드 생성"""
        npc_info = {
            "merchant": {
                "emoji": "🧙",
                "name": "떠돌이 상인",
                "description": "이국적인 물건들을 들고 다니는 상인이다.",
                "dialogue": "여행자여, 좋은 물건이 있다네!",
                "action": "대화하기"
            },
            "healer": {
                "emoji": "💚",
                "name": "방랑 치료사",
                "description": "상처를 치료해주는 친절한 치료사다.",
                "dialogue": "치료가 필요해 보이는군요...",
                "action": "치료받기"
            },
            "sage": {
                "emoji": "📚",
                "name": "현명한 현자",
                "description": "오래된 지식을 가진 현자다.",
                "dialogue": "지혜를 나눠주지...",
                "action": "가르침 받기"
            }
        }

        info = npc_info.get(self.npc_type, npc_info["merchant"])

        if before:
            embed = discord.Embed(
                title=f"{info['emoji']} {info['name']} 등장!",
                description=(
                    f"*\"{info['dialogue']}\"*\n\n"
                    f"{info['description']}"
                ),
                color=discord.Color.blue()
            )
            embed.set_footer(text=f"버튼을 눌러 {info['action']}!")

            # 버튼 라벨 업데이트
            for child in self.children:
                if isinstance(child, discord.ui.Button):
                    child.label = info['action']
        else:
            embed = discord.Embed(
                title=f"{info['emoji']} {info['name']}",
                color=discord.Color.blue()
            )

        return embed

    @discord.ui.button(label="대화하기", style=discord.ButtonStyle.primary, emoji="💬")
    async def interact_npc(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            await interaction.response.send_message("이 NPC는 당신과 대화하지 않습니다!", ephemeral=True)
            return

        self.interacted = True
        self.stop()
        await interaction.response.defer()


# =============================================================================
# 숨겨진 방 View
# =============================================================================

class HiddenRoomView(discord.ui.View):
    """숨겨진 방 인카운터 View"""

    def __init__(
        self,
        user: discord.User,
        timeout: int = 30
    ):
        super().__init__(timeout=timeout)
        self.user = user
        self.entered = False
        self.message: Optional[discord.Message] = None

    def create_embed(self, before: bool = True, gold: int = 0, exp: int = 0, heal: int = 0) -> discord.Embed:
        """임베드 생성"""
        if before:
            embed = discord.Embed(
                title="🚪 숨겨진 문 발견!",
                description=(
                    "벽 틈새에서 희미한 빛이 새어나온다...\n\n"
                    "```\n"
                    "   ╔═══╦═══╗\n"
                    "   ║   ┃   ║\n"
                    "   ║ ? ┃ ? ║\n"
                    "   ║   ┃   ║\n"
                    "   ╚═══╩═══╝\n"
                    "```\n"
                    "안으로 들어가시겠습니까?"
                ),
                color=discord.Color.purple()
            )
            embed.set_footer(text="희귀한 보물이 있을지도...")
        else:
            embed = discord.Embed(
                title="🚪 숨겨진 방 탐험!",
                description=(
                    "고대의 보물이 가득한 방을 발견했다!\n\n"
                    "```diff\n"
                    f"+ 💰 골드: {gold:,}\n"
                    f"+ 💎 경험치: {exp}\n"
                    f"+ 💚 HP 회복: {heal}\n"
                    "```"
                ),
                color=discord.Color.purple()
            )
            embed.add_field(
                name="휴식",
                value="편안한 장소에서 잠시 휴식을 취했다...",
                inline=False
            )

        return embed

    @discord.ui.button(label="입장하기", style=discord.ButtonStyle.success, emoji="🚪")
    async def enter_room(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            await interaction.response.send_message("이 문은 당신을 위한 것이 아닙니다!", ephemeral=True)
            return

        self.entered = True
        self.stop()
        await interaction.response.defer()


# =============================================================================
# 결과 표시 유틸리티
# =============================================================================

async def show_encounter_result(
    message: discord.Message,
    embed: discord.Embed,
    delay: float = 2.0
) -> None:
    """
    인카운터 결과를 표시하고 일정 시간 후 삭제

    Args:
        message: 편집할 메시지
        embed: 결과 임베드
        delay: 표시 후 삭제까지 대기 시간
    """
    await message.edit(embed=embed, view=None)
    await asyncio.sleep(delay)
    try:
        await message.delete()
    except discord.NotFound:
        pass
