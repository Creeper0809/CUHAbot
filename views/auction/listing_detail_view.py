"""
경매 리스팅 상세 View

선택한 경매의 상세 정보를 보여주고 입찰/구매할 수 있습니다.
"""
import discord
from typing import Optional

from exceptions import AuctionError, InsufficientGoldError
from models.auction_listing import AuctionListing, AuctionType
from models.users import User
from service.auction.auction_service import AuctionService
from utils.grade_display import get_grade_emoji


class ListingDetailView(discord.ui.View):
    """경매 리스팅 상세 View"""

    def __init__(
        self,
        user: discord.User,
        db_user: User,
        listing: AuctionListing,
        parent_view: "AuctionMainView",
        timeout: int = 60,
    ):
        super().__init__(timeout=timeout)
        self.user = user
        self.db_user = db_user
        self.listing = listing
        self.parent_view = parent_view
        self.message: Optional[discord.Message] = None

        # 내가 판매자인지 확인
        self.is_seller = (listing.seller_id == db_user.id)

        # 버튼 활성화/비활성화
        self._update_buttons()

    def _update_buttons(self):
        """버튼 상태 업데이트"""
        # 입찰 버튼 (BID 모드만)
        self.bid_button.disabled = (
            self.is_seller
            or self.listing.auction_type != AuctionType.BID
        )

        # 즉시 구매 버튼
        # BID 모드에서 buyout_price가 있거나, BUYNOW 모드
        has_buyout = (
            self.listing.auction_type == AuctionType.BUYNOW
            or (self.listing.auction_type == AuctionType.BID and self.listing.buyout_price)
        )
        self.buynow_button.disabled = self.is_seller or not has_buyout

        # 취소 버튼 (판매자만)
        self.cancel_button.disabled = not self.is_seller

    def create_embed(self) -> discord.Embed:
        """상세 정보 Embed 생성"""
        listing = self.listing
        grade_emoji = get_grade_emoji(listing.instance_grade) if listing.instance_grade > 0 else ""
        enhance_str = f" +{listing.enhancement_level}" if listing.enhancement_level > 0 else ""

        embed = discord.Embed(
            title=f"{grade_emoji} {listing.item_name}{enhance_str}",
            description=f"경매 #{listing.id}",
            color=discord.Color.blue()
        )

        # 타입
        type_str = "⏳ 입찰 경매" if listing.auction_type == AuctionType.BID else "💰 즉시 구매"
        embed.add_field(name="타입", value=type_str, inline=True)

        # 판매자
        seller_name = listing.seller.username if hasattr(listing.seller, "username") else f"User #{listing.seller_id}"
        embed.add_field(name="👤 판매자", value=seller_name, inline=True)

        # 상태
        embed.add_field(name="📊 상태", value=listing.status.value.upper(), inline=True)

        # 가격
        if listing.auction_type == AuctionType.BID:
            embed.add_field(
                name="💵 현재가",
                value=f"{listing.current_price:,}G",
                inline=True
            )
            if listing.buyout_price:
                embed.add_field(
                    name="⚡ 즉구가",
                    value=f"{listing.buyout_price:,}G",
                    inline=True
                )
        else:
            embed.add_field(
                name="💵 가격",
                value=f"{listing.current_price:,}G",
                inline=True
            )

        # 남은 시간
        time_remaining = listing.time_remaining
        if time_remaining.total_seconds() > 0:
            hours = int(time_remaining.total_seconds() // 3600)
            minutes = int((time_remaining.total_seconds() % 3600) // 60)
            time_str = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"
        else:
            time_str = "만료됨"
        embed.add_field(name="⏰ 남은 시간", value=time_str, inline=True)

        # 아이템 정보
        if listing.instance_grade > 0:
            embed.add_field(
                name="✨ 등급",
                value=f"{grade_emoji} {listing.instance_grade}등급",
                inline=True
            )

        if listing.is_blessed:
            embed.add_field(name="💫 축복", value="축복됨", inline=True)
        if listing.is_cursed:
            embed.add_field(name="😈 저주", value="저주됨", inline=True)

        # 내 골드
        embed.add_field(
            name="💰 내 골드",
            value=f"{self.db_user.gold:,}G",
            inline=False
        )

        return embed

    @discord.ui.button(label="💰 입찰", style=discord.ButtonStyle.primary, row=0)
    async def bid_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """입찰하기"""
        if interaction.user != self.user:
            await interaction.response.send_message(
                "다른 사용자의 경매장입니다.",
                ephemeral=True
            )
            return

        from views.auction.bid_modal import BidModal

        modal = BidModal(
            listing=self.listing,
            db_user=self.db_user,
            parent_view=self.parent_view
        )
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="⚡ 즉시 구매", style=discord.ButtonStyle.success, row=0)
    async def buynow_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """즉시 구매"""
        if interaction.user != self.user:
            await interaction.response.send_message(
                "다른 사용자의 경매장입니다.",
                ephemeral=True
            )
            return

        try:
            await interaction.response.defer(ephemeral=False)

            # 구매가 결정
            if self.listing.auction_type == AuctionType.BUYNOW:
                buy_price = self.listing.current_price
            else:  # BID with buyout
                buy_price = self.listing.buyout_price

            # 즉시 구매 실행
            await AuctionService.buy_now(
                user=self.db_user,
                listing_id=self.listing.id
            )

            # DB에서 최신 골드 값 새로고침
            await self.db_user.refresh_from_db()

            # 성공 메시지
            await interaction.followup.send(
                f"✅ **즉시 구매 완료!**\n"
                f"아이템: **{self.listing.item_name}**\n"
                f"구매가: **{buy_price:,}G**\n"
                f"남은 골드: **{self.db_user.gold:,}G**",
                ephemeral=False
            )

            # 부모 View 갱신
            await self.parent_view.refresh_data()
            embed = self.parent_view.create_embed()
            await self.parent_view.message.edit(embed=embed, view=self.parent_view)

            # 현재 View 닫기
            if self.message:
                await self.message.delete()

        except InsufficientGoldError as e:
            await interaction.followup.send(
                f"⚠️ 골드가 부족합니다.\n"
                f"필요: **{e.required:,}G**\n"
                f"보유: **{e.current:,}G**",
                ephemeral=True
            )
        except AuctionError as e:
            await interaction.followup.send(
                f"⚠️ 구매 실패: {e}",
                ephemeral=True
            )
        except Exception as e:
            await interaction.followup.send(
                f"❌ 구매 처리 중 오류가 발생했습니다: {e}",
                ephemeral=True
            )

    @discord.ui.button(label="❌ 경매 취소", style=discord.ButtonStyle.danger, row=0)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """경매 취소 (판매자만)"""
        if interaction.user != self.user:
            await interaction.response.send_message(
                "다른 사용자의 경매장입니다.",
                ephemeral=True
            )
            return

        try:
            await interaction.response.defer(ephemeral=False)

            await AuctionService.cancel_listing(
                user=self.db_user,
                listing_id=self.listing.id
            )

            # 성공 메시지
            await interaction.followup.send(
                f"✅ **경매 취소 완료!**\n"
                f"아이템: **{self.listing.item_name}**\n"
                f"아이템이 인벤토리로 반환되었습니다.",
                ephemeral=False
            )

            # 부모 View 갱신
            await self.parent_view.refresh_data()
            embed = self.parent_view.create_embed()
            await self.parent_view.message.edit(embed=embed, view=self.parent_view)

            # 현재 View 닫기
            if self.message:
                await self.message.delete()

        except AuctionError as e:
            await interaction.followup.send(
                f"⚠️ 취소 실패: {e}",
                ephemeral=True
            )
        except Exception as e:
            await interaction.followup.send(
                f"❌ 취소 처리 중 오류가 발생했습니다: {e}",
                ephemeral=True
            )

    @discord.ui.button(label="📖 아이템 정보", style=discord.ButtonStyle.primary, row=1)
    async def item_info_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """아이템 정보 보기"""
        if interaction.user != self.user:
            await interaction.response.send_message(
                "다른 사용자의 경매장입니다.",
                ephemeral=True
            )
            return

        from views.auction.item_info_view import AuctionItemInfoView

        info_view = AuctionItemInfoView(
            user=interaction.user,
            listing=self.listing
        )

        embed = info_view.create_embed()
        await interaction.response.send_message(
            embed=embed,
            view=info_view,
            ephemeral=True
        )

        info_view.message = await interaction.original_response()

    @discord.ui.button(label="🔙 돌아가기", style=discord.ButtonStyle.secondary, row=1)
    async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """돌아가기"""
        if interaction.user != self.user:
            await interaction.response.send_message(
                "다른 사용자의 경매장입니다.",
                ephemeral=True
            )
            return

        if self.message:
            await self.message.delete()
