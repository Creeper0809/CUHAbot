"""
랭킹 View

플레이어 랭킹을 탭 기반으로 표시하는 UI를 제공합니다.
"""
from typing import Optional

import discord

from models import User
from service.ranking_service import RankingService


class RankingView(discord.ui.View):
    """랭킹 View"""

    ITEMS_PER_PAGE = 10

    def __init__(
        self,
        user: discord.User,
        db_user: User,
        timeout: int = 120
    ):
        super().__init__(timeout=timeout)

        self.user = user
        self.db_user = db_user
        self.current_tab = "level"  # "level" or "gold"
        self.current_page = 0
        self.level_rankings = []
        self.gold_rankings = []
        self.user_ranks = {}
        self.message: Optional[discord.Message] = None

        # 탭 버튼 (Row 0)
        self.add_item(TabButton("🎖️ 레벨", "level", is_active=True))
        self.add_item(TabButton("💰 골드", "gold", is_active=False))

        # 페이지 버튼 (Row 1)
        self.add_item(PrevPageButton())
        self.add_item(NextPageButton())
        self.add_item(CloseButton())

    async def load_data(self):
        """데이터 로딩"""
        self.level_rankings = await RankingService.get_level_ranking(100)
        self.gold_rankings = await RankingService.get_gold_ranking(100)
        self.user_ranks = await RankingService.get_user_rankings(self.db_user.id)

    def create_embed(self) -> discord.Embed:
        """현재 탭/페이지에 맞는 Embed 생성"""
        if self.current_tab == "level":
            return self._create_level_embed()
        else:
            return self._create_gold_embed()

    def _create_level_embed(self) -> discord.Embed:
        """레벨 랭킹 Embed"""
        rankings = self.level_rankings
        start = self.current_page * self.ITEMS_PER_PAGE
        end = start + self.ITEMS_PER_PAGE
        page_data = rankings[start:end]

        embed = discord.Embed(
            title="🏆 레벨 랭킹",
            description=f"📊 당신의 순위: **#{self.user_ranks['level_rank']}**",
            color=discord.Color.gold()
        )

        if not page_data:
            embed.add_field(
                name="랭킹 없음",
                value="아직 랭킹 데이터가 없습니다.",
                inline=False
            )
        else:
            # 순위 표시
            ranking_text = []
            for entry in page_data:
                rank_emoji = self._get_rank_emoji(entry["rank"])
                is_me = entry["discord_id"] == self.user.id
                highlight = "**" if is_me else ""
                me_indicator = " 👈 YOU" if is_me else ""

                ranking_text.append(
                    f"{rank_emoji} {highlight}{entry['rank']}. {entry['username']}{highlight}{me_indicator}\n"
                    f"   Lv.{entry['level']} (EXP: {entry['exp']:,})"
                )

            embed.add_field(
                name=f"순위 ({start+1}-{min(end, len(rankings))})",
                value="\n\n".join(ranking_text),
                inline=False
            )

        total_pages = max(1, (len(rankings) + self.ITEMS_PER_PAGE - 1) // self.ITEMS_PER_PAGE)
        embed.set_footer(text=f"📄 페이지 {self.current_page + 1}/{total_pages}")

        return embed

    def _create_gold_embed(self) -> discord.Embed:
        """골드 랭킹 Embed"""
        rankings = self.gold_rankings
        start = self.current_page * self.ITEMS_PER_PAGE
        end = start + self.ITEMS_PER_PAGE
        page_data = rankings[start:end]

        embed = discord.Embed(
            title="🏆 골드 랭킹",
            description=f"📊 당신의 순위: **#{self.user_ranks['gold_rank']}**",
            color=discord.Color.gold()
        )

        if not page_data:
            embed.add_field(
                name="랭킹 없음",
                value="아직 랭킹 데이터가 없습니다.",
                inline=False
            )
        else:
            # 순위 표시
            ranking_text = []
            for entry in page_data:
                rank_emoji = self._get_rank_emoji(entry["rank"])
                is_me = entry["discord_id"] == self.user.id
                highlight = "**" if is_me else ""
                me_indicator = " 👈 YOU" if is_me else ""

                ranking_text.append(
                    f"{rank_emoji} {highlight}{entry['rank']}. {entry['username']}{highlight}{me_indicator}\n"
                    f"   💰 {entry['gold']:,}G"
                )

            embed.add_field(
                name=f"순위 ({start+1}-{min(end, len(rankings))})",
                value="\n\n".join(ranking_text),
                inline=False
            )

        total_pages = max(1, (len(rankings) + self.ITEMS_PER_PAGE - 1) // self.ITEMS_PER_PAGE)
        embed.set_footer(text=f"📄 페이지 {self.current_page + 1}/{total_pages}")

        return embed

    @staticmethod
    def _get_rank_emoji(rank: int) -> str:
        """순위별 이모지"""
        if rank == 1:
            return "🥇"
        elif rank == 2:
            return "🥈"
        elif rank == 3:
            return "🥉"
        else:
            return "📍"

    def _update_tab_buttons(self):
        """탭 버튼 업데이트"""
        # 기존 탭 버튼 제거
        to_remove = [item for item in self.children if isinstance(item, TabButton)]
        for item in to_remove:
            self.remove_item(item)

        # 새 탭 버튼 추가
        level_btn = TabButton("🎖️ 레벨", "level", is_active=(self.current_tab == "level"))
        level_btn.row = 0
        self.add_item(level_btn)

        gold_btn = TabButton("💰 골드", "gold", is_active=(self.current_tab == "gold"))
        gold_btn.row = 0
        self.add_item(gold_btn)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """본인만 사용 가능"""
        if interaction.user.id != self.user.id:
            await interaction.response.send_message(
                "다른 사용자의 랭킹 창은 조작할 수 없습니다.",
                ephemeral=True
            )
            return False
        return True

    async def on_timeout(self):
        """타임아웃 시 View 비활성화"""
        if self.message:
            try:
                await self.message.edit(view=None)
            except discord.NotFound:
                pass


class TabButton(discord.ui.Button):
    """탭 전환 버튼"""

    def __init__(self, label: str, tab_key: str, is_active: bool = False):
        style = discord.ButtonStyle.primary if is_active else discord.ButtonStyle.secondary
        super().__init__(label=label, style=style, row=0)
        self.tab_key = tab_key

    async def callback(self, interaction: discord.Interaction):
        view: RankingView = self.view

        view.current_tab = self.tab_key
        view.current_page = 0  # 탭 전환 시 첫 페이지로
        view._update_tab_buttons()

        embed = view.create_embed()
        await interaction.response.edit_message(embed=embed, view=view)


class PrevPageButton(discord.ui.Button):
    """이전 페이지 버튼"""

    def __init__(self):
        super().__init__(label="◀", style=discord.ButtonStyle.secondary, row=1)

    async def callback(self, interaction: discord.Interaction):
        view: RankingView = self.view

        rankings = view.level_rankings if view.current_tab == "level" else view.gold_rankings
        total_pages = max(1, (len(rankings) + view.ITEMS_PER_PAGE - 1) // view.ITEMS_PER_PAGE)

        if view.current_page > 0:
            view.current_page -= 1
        else:
            view.current_page = total_pages - 1  # 첫 페이지에서 이전 -> 마지막 페이지

        embed = view.create_embed()
        await interaction.response.edit_message(embed=embed, view=view)


class NextPageButton(discord.ui.Button):
    """다음 페이지 버튼"""

    def __init__(self):
        super().__init__(label="▶", style=discord.ButtonStyle.secondary, row=1)

    async def callback(self, interaction: discord.Interaction):
        view: RankingView = self.view

        rankings = view.level_rankings if view.current_tab == "level" else view.gold_rankings
        total_pages = max(1, (len(rankings) + view.ITEMS_PER_PAGE - 1) // view.ITEMS_PER_PAGE)

        if view.current_page < total_pages - 1:
            view.current_page += 1
        else:
            view.current_page = 0  # 마지막 페이지에서 다음 -> 첫 페이지

        embed = view.create_embed()
        await interaction.response.edit_message(embed=embed, view=view)


class CloseButton(discord.ui.Button):
    """닫기 버튼"""

    def __init__(self):
        super().__init__(label="닫기", style=discord.ButtonStyle.danger, emoji="❌", row=1)

    async def callback(self, interaction: discord.Interaction):
        view: RankingView = self.view
        view.stop()
        await interaction.response.edit_message(
            content="랭킹 창을 닫았습니다.",
            embed=None,
            view=None
        )
