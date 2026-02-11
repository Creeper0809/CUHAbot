"""
경매 입찰 Modal

사용자가 특정 경매에 입찰할 수 있습니다.
"""
import discord

from exceptions import (
    AuctionError,
    AuctionBidTooLowError,
    AuctionSelfBidError,
    AuctionAlreadyEndedError,
)
from models.auction_listing import AuctionListing
from models.users import User
from service.auction.auction_service import AuctionService


class BidModal(discord.ui.Modal, title="💰 입찰하기"):
    """
    입찰 Modal

    - 현재가보다 높은 금액만 입찰 가능
    - 입찰 시 즉시 골드 차감 (에스크로)
    - 다른 사람이 더 높게 입찰하면 자동 환불
    """

    bid_amount_input = discord.ui.TextInput(
        label="입찰 금액",
        placeholder="현재가보다 높은 금액을 입력하세요",
        required=True,
        max_length=20,
    )

    def __init__(
        self,
        listing: AuctionListing,
        db_user: User,
        parent_view: "AuctionMainView",
    ):
        super().__init__()
        self.listing = listing
        self.db_user = db_user
        self.parent_view = parent_view

        # 현재가 힌트 업데이트
        self.bid_amount_input.placeholder = (
            f"현재가: {listing.current_price:,}G (최소: {listing.current_price + 1:,}G)"
        )

    async def on_submit(self, interaction: discord.Interaction):
        """입찰 처리"""
        try:
            # 입찰 금액 파싱
            bid_amount_str = self.bid_amount_input.value.strip().replace(",", "")
            try:
                bid_amount = int(bid_amount_str)
            except ValueError:
                await interaction.response.send_message(
                    "⚠️ 입찰 금액은 숫자만 입력해주세요.", ephemeral=True
                )
                return

            if bid_amount <= 0:
                await interaction.response.send_message(
                    "⚠️ 입찰 금액은 0보다 커야 합니다.", ephemeral=True
                )
                return

            # 입찰 실행
            await interaction.response.defer(ephemeral=False)

            bid = await AuctionService.place_bid(
                user=self.db_user, listing_id=self.listing.id, bid_amount=bid_amount
            )

            # DB에서 최신 골드 값 새로고침
            await self.db_user.refresh_from_db()

            # 성공 메시지
            await interaction.followup.send(
                f"✅ **입찰 완료!**\n"
                f"경매: **{self.listing.item_name}** (강화 +{self.listing.enhancement_level})\n"
                f"입찰가: **{bid_amount:,}G**\n"
                f"현재 보유 골드: **{self.db_user.gold:,}G**",
                ephemeral=False,
            )

            # 부모 View 갱신
            await self.parent_view.refresh_data()
            embed = self.parent_view.create_embed()
            await self.parent_view.message.edit(embed=embed, view=self.parent_view)

        except AuctionSelfBidError:
            await interaction.followup.send(
                "⚠️ 자신이 등록한 경매에는 입찰할 수 없습니다.", ephemeral=True
            )
        except AuctionBidTooLowError as e:
            await interaction.followup.send(
                f"⚠️ 입찰 금액이 현재가보다 낮습니다.\n"
                f"현재가: **{e.current_price:,}G**\n"
                f"입찰가: **{e.bid_amount:,}G**\n"
                f"최소 입찰가: **{e.current_price + 1:,}G**",
                ephemeral=True,
            )
        except AuctionAlreadyEndedError:
            await interaction.followup.send(
                "⚠️ 이미 종료된 경매입니다.", ephemeral=True
            )
        except AuctionError as e:
            await interaction.followup.send(f"⚠️ 입찰 실패: {e}", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(
                f"❌ 입찰 처리 중 오류가 발생했습니다: {e}", ephemeral=True
            )
