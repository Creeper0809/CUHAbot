"""
경매장 메인 UI

4-tab navigation: 전체 리스팅, 내 등록, 내 입찰, 구매 주문
"""
import discord
from datetime import datetime
from typing import Optional

from models.auction_listing import AuctionListing, AuctionStatus
from models.auction_bid import AuctionBid
from models.buy_order import BuyOrder
from models.users import User
from service.auction.auction_service import AuctionService
from utils.grade_display import get_grade_emoji


class AuctionMainView(discord.ui.View):
    """경매장 메인 View"""

    def __init__(
        self,
        user: discord.User,
        db_user: User,
        timeout: int = 180
    ):
        super().__init__(timeout=timeout)
        self.user = user
        self.db_user = db_user
        self.message: Optional[discord.Message] = None

        # 탭 상태
        self.current_tab = "all"  # all, my_listings, my_bids, buy_orders

        # 페이지네이션
        self.page = 0
        self.items_per_page = 5

        # 데이터
        self.listings: list[AuctionListing] = []
        self.bids: list[AuctionBid] = []
        self.buy_orders: list[BuyOrder] = []

        # 필터 (검색 모달에서 설정)
        self.filters = {
            "item_type": None,
            "item_grade": None,
            "min_enhancement": 0,
            "max_enhancement": 99,
            "min_price": 0,
            "max_price": 999999999
        }

    async def initialize(self):
        """비동기 초기화 (데이터 로드)"""
        await self.refresh_data()

    async def refresh_data(self):
        """현재 탭에 맞는 데이터 새로고침"""
        if self.current_tab == "all":
            self.listings = await AuctionService.search_listings(
                item_type=self.filters["item_type"],
                item_grade=self.filters["item_grade"],
                min_enhancement=self.filters["min_enhancement"],
                max_enhancement=self.filters["max_enhancement"],
                min_price=self.filters["min_price"],
                max_price=self.filters["max_price"],
                sort_by="created_at",
                offset=0,
                limit=100
            )
        elif self.current_tab == "my_listings":
            self.listings = await AuctionService.get_my_listings(
                self.db_user,
                status=AuctionStatus.ACTIVE
            )
        elif self.current_tab == "my_bids":
            self.bids = await AuctionService.get_my_bids(self.db_user)
        elif self.current_tab == "buy_orders":
            self.buy_orders = await AuctionService.get_my_buy_orders(self.db_user)

        self.page = 0

    def create_embed(self) -> discord.Embed:
        """현재 탭에 맞는 Embed 생성"""
        if self.current_tab == "all":
            return self._create_all_listings_embed()
        elif self.current_tab == "my_listings":
            return self._create_my_listings_embed()
        elif self.current_tab == "my_bids":
            return self._create_my_bids_embed()
        elif self.current_tab == "buy_orders":
            return self._create_buy_orders_embed()

    def _create_all_listings_embed(self) -> discord.Embed:
        """전체 리스팅 Embed"""
        embed = discord.Embed(
            title="🏛️ 경매장 - 전체 리스팅",
            description="아이템을 사고팔 수 있습니다.",
            color=discord.Color.gold()
        )

        if not self.listings:
            embed.add_field(
                name="📦 리스팅 없음",
                value="현재 등록된 경매가 없습니다.",
                inline=False
            )
            return embed

        # 페이지네이션
        total_pages = (len(self.listings) + self.items_per_page - 1) // self.items_per_page
        start_idx = self.page * self.items_per_page
        end_idx = min(start_idx + self.items_per_page, len(self.listings))
        page_listings = self.listings[start_idx:end_idx]

        for listing in page_listings:
            # 등급 이모지
            grade_emoji = get_grade_emoji(listing.instance_grade) if listing.instance_grade > 0 else ""

            # 강화 표시
            enhance_str = f" +{listing.enhancement_level}" if listing.enhancement_level > 0 else ""

            # 제목
            title = f"{grade_emoji} {listing.item_name}{enhance_str}"

            # 타입 이모지
            type_emoji = "⏳" if listing.auction_type.value == "bid" else "💰"

            # 남은 시간
            time_remaining = listing.time_remaining
            if time_remaining.total_seconds() > 0:
                hours = int(time_remaining.total_seconds() // 3600)
                minutes = int((time_remaining.total_seconds() % 3600) // 60)
                time_str = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"
            else:
                time_str = "만료됨"

            # 내용
            value = (
                f"{type_emoji} **{listing.auction_type.value.upper()}**\n"
                f"💵 현재가: **{listing.current_price:,}G**\n"
                f"⏰ 남은시간: {time_str}\n"
                f"👤 판매자: {listing.seller.username}"
            )

            if listing.auction_type.value == "bid" and listing.buyout_price:
                value += f"\n⚡ 즉구가: {listing.buyout_price:,}G"

            embed.add_field(
                name=f"#{listing.id} - {title}",
                value=value,
                inline=True
            )

        embed.set_footer(
            text=f"페이지 {self.page + 1}/{max(total_pages, 1)} | 총 {len(self.listings)}개 리스팅"
        )

        return embed

    def _create_my_listings_embed(self) -> discord.Embed:
        """내 리스팅 Embed"""
        embed = discord.Embed(
            title="🏛️ 경매장 - 내 등록",
            description="내가 등록한 경매 목록입니다.",
            color=discord.Color.blue()
        )

        if not self.listings:
            embed.add_field(
                name="📦 등록 없음",
                value="현재 등록한 경매가 없습니다.",
                inline=False
            )
            return embed

        # 페이지네이션
        total_pages = (len(self.listings) + self.items_per_page - 1) // self.items_per_page
        start_idx = self.page * self.items_per_page
        end_idx = min(start_idx + self.items_per_page, len(self.listings))
        page_listings = self.listings[start_idx:end_idx]

        for listing in page_listings:
            grade_emoji = get_grade_emoji(listing.instance_grade) if listing.instance_grade > 0 else ""
            enhance_str = f" +{listing.enhancement_level}" if listing.enhancement_level > 0 else ""
            title = f"{grade_emoji} {listing.item_name}{enhance_str}"

            type_emoji = "⏳" if listing.auction_type.value == "bid" else "💰"

            time_remaining = listing.time_remaining
            if time_remaining.total_seconds() > 0:
                hours = int(time_remaining.total_seconds() // 3600)
                minutes = int((time_remaining.total_seconds() % 3600) // 60)
                time_str = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"
            else:
                time_str = "만료됨"

            value = (
                f"{type_emoji} **{listing.auction_type.value.upper()}**\n"
                f"💵 현재가: **{listing.current_price:,}G**\n"
                f"⏰ 남은시간: {time_str}\n"
                f"📊 상태: {listing.status.value}"
            )

            embed.add_field(
                name=f"#{listing.id} - {title}",
                value=value,
                inline=True
            )

        embed.set_footer(
            text=f"페이지 {self.page + 1}/{max(total_pages, 1)} | 총 {len(self.listings)}개"
        )

        return embed

    def _create_my_bids_embed(self) -> discord.Embed:
        """내 입찰 Embed"""
        embed = discord.Embed(
            title="🏛️ 경매장 - 내 입찰",
            description="내가 입찰한 경매 목록입니다.",
            color=discord.Color.green()
        )

        if not self.bids:
            embed.add_field(
                name="💰 입찰 없음",
                value="현재 입찰한 경매가 없습니다.",
                inline=False
            )
            return embed

        # 페이지네이션
        total_pages = (len(self.bids) + self.items_per_page - 1) // self.items_per_page
        start_idx = self.page * self.items_per_page
        end_idx = min(start_idx + self.items_per_page, len(self.bids))
        page_bids = self.bids[start_idx:end_idx]

        for bid in page_bids:
            listing = bid.auction

            grade_emoji = get_grade_emoji(listing.instance_grade) if listing.instance_grade > 0 else ""
            enhance_str = f" +{listing.enhancement_level}" if listing.enhancement_level > 0 else ""
            title = f"{grade_emoji} {listing.item_name}{enhance_str}"

            # 최고 입찰자 여부
            is_highest = (bid.bid_amount == listing.current_price)
            status_emoji = "🥇" if is_highest else "🥈"

            time_remaining = listing.time_remaining
            if time_remaining.total_seconds() > 0:
                hours = int(time_remaining.total_seconds() // 3600)
                minutes = int((time_remaining.total_seconds() % 3600) // 60)
                time_str = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"
            else:
                time_str = "만료됨"

            value = (
                f"{status_emoji} **{'최고 입찰' if is_highest else '입찰중'}**\n"
                f"💵 내 입찰가: **{bid.bid_amount:,}G**\n"
                f"💎 현재가: {listing.current_price:,}G\n"
                f"⏰ 남은시간: {time_str}"
            )

            embed.add_field(
                name=f"#{listing.id} - {title}",
                value=value,
                inline=True
            )

        embed.set_footer(
            text=f"페이지 {self.page + 1}/{max(total_pages, 1)} | 총 {len(self.bids)}개"
        )

        return embed

    def _create_buy_orders_embed(self) -> discord.Embed:
        """구매 주문 Embed"""
        embed = discord.Embed(
            title="🏛️ 경매장 - 구매 주문",
            description="내가 등록한 구매 주문 목록입니다.",
            color=discord.Color.purple()
        )

        if not self.buy_orders:
            embed.add_field(
                name="📋 주문 없음",
                value="현재 등록한 구매 주문이 없습니다.",
                inline=False
            )
            return embed

        # 페이지네이션
        total_pages = (len(self.buy_orders) + self.items_per_page - 1) // self.items_per_page
        start_idx = self.page * self.items_per_page
        end_idx = min(start_idx + self.items_per_page, len(self.buy_orders))
        page_orders = self.buy_orders[start_idx:end_idx]

        # 아이템 이름 조회를 위해 캐시 사용
        from models.repos.static_cache import item_cache

        for order in page_orders:
            item = item_cache.get(order.item_id)
            item_name = item.name if item else f"Item {order.item_id}"

            time_remaining = order.time_remaining
            if time_remaining.total_seconds() > 0:
                hours = int(time_remaining.total_seconds() // 3600)
                minutes = int((time_remaining.total_seconds() % 3600) // 60)
                time_str = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"
            else:
                time_str = "만료됨"

            value = (
                f"📦 아이템: **{item_name}**\n"
                f"⚡ 강화: {order.min_enhancement_level}~{order.max_enhancement_level}\n"
                f"🌟 등급: {order.min_instance_grade}~{order.max_instance_grade}\n"
                f"💰 최대가: **{order.max_price:,}G**\n"
                f"⏰ 남은시간: {time_str}\n"
                f"📊 상태: {order.status.value}"
            )

            embed.add_field(
                name=f"#{order.id}",
                value=value,
                inline=True
            )

        embed.set_footer(
            text=f"페이지 {self.page + 1}/{max(total_pages, 1)} | 총 {len(self.buy_orders)}개"
        )

        return embed

    # =========================================================================
    # Tab Buttons
    # =========================================================================

    @discord.ui.button(label="🏪 전체 리스팅", style=discord.ButtonStyle.primary, row=0)
    async def tab_all(self, interaction: discord.Interaction, button: discord.ui.Button):
        """전체 리스팅 탭"""
        if interaction.user != self.user:
            await interaction.response.send_message(
                "다른 사용자의 경매장입니다.",
                ephemeral=True
            )
            return

        self.current_tab = "all"
        await self.refresh_data()
        self._update_tab_buttons()

        embed = self.create_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="📝 내 등록", style=discord.ButtonStyle.secondary, row=0)
    async def tab_my_listings(self, interaction: discord.Interaction, button: discord.ui.Button):
        """내 리스팅 탭"""
        if interaction.user != self.user:
            await interaction.response.send_message(
                "다른 사용자의 경매장입니다.",
                ephemeral=True
            )
            return

        self.current_tab = "my_listings"
        await self.refresh_data()
        self._update_tab_buttons()

        embed = self.create_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="💰 내 입찰", style=discord.ButtonStyle.secondary, row=0)
    async def tab_my_bids(self, interaction: discord.Interaction, button: discord.ui.Button):
        """내 입찰 탭"""
        if interaction.user != self.user:
            await interaction.response.send_message(
                "다른 사용자의 경매장입니다.",
                ephemeral=True
            )
            return

        self.current_tab = "my_bids"
        await self.refresh_data()
        self._update_tab_buttons()

        embed = self.create_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="📋 구매 주문", style=discord.ButtonStyle.secondary, row=0)
    async def tab_buy_orders(self, interaction: discord.Interaction, button: discord.ui.Button):
        """구매 주문 탭"""
        if interaction.user != self.user:
            await interaction.response.send_message(
                "다른 사용자의 경매장입니다.",
                ephemeral=True
            )
            return

        self.current_tab = "buy_orders"
        await self.refresh_data()
        self._update_tab_buttons()

        embed = self.create_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    # =========================================================================
    # Action Buttons
    # =========================================================================

    @discord.ui.button(label="🔍 검색/필터", style=discord.ButtonStyle.secondary, row=1)
    async def filter_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """검색/필터 모달 열기"""
        if interaction.user != self.user:
            await interaction.response.send_message(
                "다른 사용자의 경매장입니다.",
                ephemeral=True
            )
            return

        from views.auction.filter_modal import FilterModal

        modal = FilterModal(parent_view=self)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="📊 경매 현황 보기", style=discord.ButtonStyle.primary, row=1)
    async def view_listing_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """경매 현황 상세 보기"""
        if interaction.user != self.user:
            await interaction.response.send_message(
                "다른 사용자의 경매장입니다.",
                ephemeral=True
            )
            return

        from views.auction.select_listing_modal import SelectListingModal

        modal = SelectListingModal(
            user=self.user,
            db_user=self.db_user,
            parent_view=self
        )
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="➕ 등록하기", style=discord.ButtonStyle.success, row=1)
    async def create_listing_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """경매 등록"""
        if interaction.user != self.user:
            await interaction.response.send_message(
                "다른 사용자의 경매장입니다.",
                ephemeral=True
            )
            return

        from views.auction.item_select_view import AuctionItemSelectView

        # 아이템 선택 View 생성
        select_view = AuctionItemSelectView(
            user=self.user, db_user=self.db_user, parent_view=self
        )
        await select_view.initialize()

        embed = select_view.create_embed()
        await interaction.response.send_message(embed=embed, view=select_view, ephemeral=True)

        select_view.message = await interaction.original_response()

    @discord.ui.button(label="📋 주문하기", style=discord.ButtonStyle.success, row=1)
    async def create_buy_order_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """구매 주문 등록"""
        if interaction.user != self.user:
            await interaction.response.send_message(
                "다른 사용자의 경매장입니다.",
                ephemeral=True
            )
            return

        from views.auction.buy_order_modal import CreateBuyOrderModal

        modal = CreateBuyOrderModal(db_user=self.db_user, parent_view=self)
        await interaction.response.send_modal(modal)

    # =========================================================================
    # Pagination Buttons
    # =========================================================================

    @discord.ui.button(label="◀", style=discord.ButtonStyle.secondary, row=2)
    async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        """이전 페이지"""
        if interaction.user != self.user:
            await interaction.response.send_message(
                "다른 사용자의 경매장입니다.",
                ephemeral=True
            )
            return

        # 현재 탭의 총 아이템 수 확인
        if self.current_tab == "all" or self.current_tab == "my_listings":
            total_items = len(self.listings)
        elif self.current_tab == "my_bids":
            total_items = len(self.bids)
        else:  # buy_orders
            total_items = len(self.buy_orders)

        total_pages = max(1, (total_items + self.items_per_page - 1) // self.items_per_page)

        if self.page > 0:
            self.page -= 1
        else:
            self.page = total_pages - 1

        embed = self.create_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="▶", style=discord.ButtonStyle.secondary, row=2)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        """다음 페이지"""
        if interaction.user != self.user:
            await interaction.response.send_message(
                "다른 사용자의 경매장입니다.",
                ephemeral=True
            )
            return

        # 현재 탭의 총 아이템 수 확인
        if self.current_tab == "all" or self.current_tab == "my_listings":
            total_items = len(self.listings)
        elif self.current_tab == "my_bids":
            total_items = len(self.bids)
        else:  # buy_orders
            total_items = len(self.buy_orders)

        total_pages = max(1, (total_items + self.items_per_page - 1) // self.items_per_page)

        if self.page < total_pages - 1:
            self.page += 1
        else:
            self.page = 0

        embed = self.create_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="🔄 새로고침", style=discord.ButtonStyle.secondary, row=2)
    async def refresh_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """새로고침"""
        if interaction.user != self.user:
            await interaction.response.send_message(
                "다른 사용자의 경매장입니다.",
                ephemeral=True
            )
            return

        await self.refresh_data()
        embed = self.create_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="❌ 닫기", style=discord.ButtonStyle.danger, row=2)
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """닫기"""
        if interaction.user != self.user:
            await interaction.response.send_message(
                "다른 사용자의 경매장입니다.",
                ephemeral=True
            )
            return

        await interaction.response.edit_message(
            content="경매장을 닫았습니다.",
            embed=None,
            view=None
        )
        self.stop()

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _update_tab_buttons(self):
        """탭 버튼 스타일 업데이트"""
        tab_buttons = [
            (self.children[0], "all"),
            (self.children[1], "my_listings"),
            (self.children[2], "my_bids"),
            (self.children[3], "buy_orders"),
        ]

        for button, tab_name in tab_buttons:
            if self.current_tab == tab_name:
                button.style = discord.ButtonStyle.primary
            else:
                button.style = discord.ButtonStyle.secondary

    async def on_timeout(self):
        """타임아웃 처리"""
        if self.message:
            try:
                await self.message.edit(
                    content="⏰ 경매장이 타임아웃되었습니다.",
                    embed=None,
                    view=None
                )
            except discord.NotFound:
                pass

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """상호작용 권한 체크"""
        if interaction.user != self.user:
            await interaction.response.send_message(
                "다른 사용자의 경매장입니다.",
                ephemeral=True
            )
            return False
        return True
