"""
도감 조회 View

유저가 수집한 아이템, 스킬, 몬스터를 탭 + 페이지네이션으로 표시합니다.
"""
import discord
from typing import List

from models import User
from service.collection_service import CollectionService, CollectionEntry, CollectionStats
from utils.grade_display import format_item_name, format_skill_name


class CollectionView(discord.ui.View):
    """
    도감 조회 View

    탭(아이템/스킬/몬스터) + 페이지네이션으로 표시합니다.
    """

    ITEMS_PER_PAGE = 10

    def __init__(
        self,
        discord_user: discord.User,
        user: User,
        stats: CollectionStats,
        items: List[CollectionEntry],
        skills: List[CollectionEntry],
        monsters: List[CollectionEntry],
    ):
        super().__init__(timeout=120)
        self.discord_user = discord_user
        self.user = user
        self.stats = stats
        self.items = items
        self.skills = skills
        self.monsters = monsters
        self.current_tab = "overview"  # overview, items, skills, monsters
        self.current_page = 0

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """본인만 조작 가능"""
        if interaction.user.id != self.discord_user.id:
            await interaction.response.send_message(
                "다른 사람의 도감은 조작할 수 없습니다.",
                ephemeral=True
            )
            return False
        return True

    def create_embed(self) -> discord.Embed:
        """현재 탭에 맞는 Embed 생성"""
        if self.current_tab == "overview":
            return self._create_overview_embed()
        elif self.current_tab == "items":
            return self._create_list_embed("아이템", self.items, discord.Color.green())
        elif self.current_tab == "skills":
            return self._create_list_embed("스킬", self.skills, discord.Color.purple())
        elif self.current_tab == "monsters":
            return self._create_list_embed("몬스터", self.monsters, discord.Color.red())
        return self._create_overview_embed()

    def _create_overview_embed(self) -> discord.Embed:
        """도감 개요 Embed"""
        embed = discord.Embed(
            title=f"📖 {self.user.get_name()}의 도감",
            color=discord.Color.gold()
        )

        # 전체 진행률
        total_progress = self.stats.completion_rate * 100
        progress_bar = self._create_bar(self.stats.completion_rate, 20)

        embed.description = (
            f"**전체 수집률**\n"
            f"{progress_bar} {total_progress:.1f}%\n"
            f"(`{self.stats.total_collected}` / `{self.stats.total}`)"
        )

        # 아이템 통계
        item_rate = (self.stats.item_collected / self.stats.item_total * 100
                     if self.stats.item_total > 0 else 0)
        embed.add_field(
            name="📦 아이템",
            value=f"`{self.stats.item_collected}` / `{self.stats.item_total}` ({item_rate:.1f}%)",
            inline=True
        )

        # 스킬 통계
        skill_rate = (self.stats.skill_collected / self.stats.skill_total * 100
                      if self.stats.skill_total > 0 else 0)
        embed.add_field(
            name="✨ 스킬",
            value=f"`{self.stats.skill_collected}` / `{self.stats.skill_total}` ({skill_rate:.1f}%)",
            inline=True
        )

        # 몬스터 통계
        monster_rate = (self.stats.monster_collected / self.stats.monster_total * 100
                        if self.stats.monster_total > 0 else 0)
        embed.add_field(
            name="👹 몬스터",
            value=f"`{self.stats.monster_collected}` / `{self.stats.monster_total}` ({monster_rate:.1f}%)",
            inline=True
        )

        embed.set_footer(text="아래 버튼으로 상세 목록을 확인하세요")
        return embed

    def _create_list_embed(
        self,
        title: str,
        entries: List[CollectionEntry],
        color: discord.Color
    ) -> discord.Embed:
        """목록 Embed 생성 (페이지네이션)"""
        total_pages = max(1, (len(entries) + self.ITEMS_PER_PAGE - 1) // self.ITEMS_PER_PAGE)
        self.current_page = min(self.current_page, total_pages - 1)
        self.current_page = max(0, self.current_page)

        start_idx = self.current_page * self.ITEMS_PER_PAGE
        end_idx = start_idx + self.ITEMS_PER_PAGE
        page_entries = entries[start_idx:end_idx]

        embed = discord.Embed(
            title=f"📖 {title} 도감",
            color=color
        )

        if not entries:
            embed.description = "수집된 항목이 없습니다."
        else:
            lines = []
            for i, entry in enumerate(page_entries):
                idx = start_idx + i + 1
                # 등급별 색상 적용 및 아이콘
                if title == "아이템":
                    display_name = format_item_name(entry.name, entry.grade_id)
                    icon = "📦"
                elif title == "스킬":
                    display_name = format_skill_name(entry.name, entry.grade_id)
                    icon = "✨"
                else:
                    display_name = entry.name
                    icon = "👹"

                # 짧은 설명 추가 (최대 45자, 줄바꿈으로 깔끔하게)
                if entry.description:
                    desc = entry.description.strip()
                    if len(desc) > 45:
                        desc = desc[:42] + "..."
                    lines.append(f"`{idx:2d}` {icon} **{display_name}**\n      └ `{desc}`")
                else:
                    lines.append(f"`{idx:2d}` {icon} **{display_name}**")

            embed.description = "\n".join(lines)

        embed.set_footer(text=f"페이지 {self.current_page + 1} / {total_pages} | 총 {len(entries)}개")
        return embed

    def _create_bar(self, ratio: float, length: int = 10) -> str:
        """프로그레스 바 생성"""
        filled = int(ratio * length)
        empty = length - filled
        return "█" * filled + "░" * empty

    def _get_current_list(self) -> List[CollectionEntry]:
        """현재 탭의 목록"""
        if self.current_tab == "items":
            return self.items
        elif self.current_tab == "skills":
            return self.skills
        elif self.current_tab == "monsters":
            return self.monsters
        return []

    def _update_buttons(self):
        """페이지네이션 버튼 상태 업데이트"""
        entries = self._get_current_list()
        total_pages = max(1, (len(entries) + self.ITEMS_PER_PAGE - 1) // self.ITEMS_PER_PAGE)

        self.prev_button.disabled = self.current_page <= 0 or self.current_tab == "overview"
        self.next_button.disabled = self.current_page >= total_pages - 1 or self.current_tab == "overview"

    # ==========================================================================
    # 탭 버튼
    # ==========================================================================

    @discord.ui.button(label="📊 개요", style=discord.ButtonStyle.primary, row=0)
    async def overview_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """개요 탭"""
        self.current_tab = "overview"
        self.current_page = 0
        self._update_buttons()
        await interaction.response.edit_message(embed=self.create_embed(), view=self)

    @discord.ui.button(label="📦 아이템", style=discord.ButtonStyle.secondary, row=0)
    async def items_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """아이템 탭"""
        self.current_tab = "items"
        self.current_page = 0
        self._update_buttons()
        await interaction.response.edit_message(embed=self.create_embed(), view=self)

    @discord.ui.button(label="✨ 스킬", style=discord.ButtonStyle.secondary, row=0)
    async def skills_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """스킬 탭"""
        self.current_tab = "skills"
        self.current_page = 0
        self._update_buttons()
        await interaction.response.edit_message(embed=self.create_embed(), view=self)

    @discord.ui.button(label="👹 몬스터", style=discord.ButtonStyle.secondary, row=0)
    async def monsters_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """몬스터 탭"""
        self.current_tab = "monsters"
        self.current_page = 0
        self._update_buttons()
        await interaction.response.edit_message(embed=self.create_embed(), view=self)

    # ==========================================================================
    # 페이지네이션 버튼
    # ==========================================================================

    @discord.ui.button(label="◀ 이전", style=discord.ButtonStyle.secondary, row=1, disabled=True)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """이전 페이지"""
        if self.current_page > 0:
            self.current_page -= 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self.create_embed(), view=self)

    @discord.ui.button(label="다음 ▶", style=discord.ButtonStyle.secondary, row=1, disabled=True)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """다음 페이지"""
        self.current_page += 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self.create_embed(), view=self)

    @discord.ui.button(label="닫기", style=discord.ButtonStyle.danger, row=1)
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """닫기"""
        await interaction.response.edit_message(content="도감을 닫았습니다.", embed=None, view=None)
        self.stop()
