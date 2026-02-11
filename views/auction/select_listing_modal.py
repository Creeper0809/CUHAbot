"""
경매 현황 보기 Modal

경매 ID를 입력받아 상세 정보를 표시합니다.
"""
import discord

from models.auction_listing import AuctionListing
from models.users import User


class SelectListingModal(discord.ui.Modal, title="📊 경매 현황 보기"):
    """경매 현황 보기 Modal"""

    listing_id_input = discord.ui.TextInput(
        label="경매 ID",
        placeholder="조회할 경매의 ID를 입력하세요 (예: 1)",
        required=True,
        max_length=20,
    )

    def __init__(
        self,
        user: discord.User,
        db_user: User,
        parent_view: "AuctionMainView",
    ):
        super().__init__()
        self.user = user
        self.db_user = db_user
        self.parent_view = parent_view

    async def on_submit(self, interaction: discord.Interaction):
        """경매 선택 처리"""
        try:
            # 경매 ID 파싱
            listing_id_str = self.listing_id_input.value.strip()
            try:
                listing_id = int(listing_id_str)
            except ValueError:
                await interaction.response.send_message(
                    "⚠️ 경매 ID는 숫자만 입력해주세요.", ephemeral=True
                )
                return

            # 경매 조회
            listing = await AuctionListing.filter(id=listing_id).prefetch_related("seller").first()

            if not listing:
                await interaction.response.send_message(
                    f"⚠️ 경매 ID {listing_id}를 찾을 수 없습니다.", ephemeral=True
                )
                return

            # 상세 View 생성
            from views.auction.listing_detail_view import ListingDetailView

            detail_view = ListingDetailView(
                user=self.user,
                db_user=self.db_user,
                listing=listing,
                parent_view=self.parent_view,
            )

            embed = detail_view.create_embed()
            await interaction.response.send_message(
                embed=embed,
                view=detail_view,
                ephemeral=True
            )

            detail_view.message = await interaction.original_response()

        except Exception as e:
            await interaction.response.send_message(
                f"❌ 경매 조회 중 오류가 발생했습니다: {e}", ephemeral=True
            )
