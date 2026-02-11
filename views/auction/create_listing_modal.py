"""
경매 리스팅 생성 Modal

사용자가 인벤토리 아이템을 경매에 등록합니다.
"""
import discord

from exceptions import AuctionError
from models.users import User
from models.user_inventory import UserInventory
from models.auction_listing import AuctionType
from service.auction.auction_service import AuctionService


class CreateListingModal(discord.ui.Modal, title="📝 경매 등록"):
    """
    경매 리스팅 생성 Modal

    - 경매 타입: "입찰" (BID) 또는 "즉시구매" (BUYNOW)
    - 시작가 (필수, 최소 100G)
    - 즉구가 (입찰 경매의 경우 선택사항)
    - 기간 (1~72시간)
    """

    auction_type_input = discord.ui.TextInput(
        label="경매 타입",
        placeholder="'입찰' 또는 '즉시구매'",
        required=True,
        max_length=10,
    )

    starting_price_input = discord.ui.TextInput(
        label="시작가 (G)",
        placeholder="최소 100G",
        required=True,
        max_length=20,
    )

    buyout_price_input = discord.ui.TextInput(
        label="즉구가 (G) - 선택사항",
        placeholder="입찰 경매에서만 사용 (즉시 낙찰 가격)",
        required=False,
        max_length=20,
    )

    duration_input = discord.ui.TextInput(
        label="경매 기간 (시간)",
        placeholder="1~72 (기본: 24시간)",
        required=False,
        default="24",
        max_length=3,
    )

    def __init__(
        self,
        inventory_item: UserInventory,
        db_user: User,
        parent_view: "AuctionMainView",
    ):
        super().__init__()
        self.inventory_item = inventory_item
        self.db_user = db_user
        self.parent_view = parent_view

    async def on_submit(self, interaction: discord.Interaction):
        """경매 리스팅 생성"""
        try:
            # 1. 경매 타입 파싱
            auction_type_str = self.auction_type_input.value.strip()
            if auction_type_str in ["입찰", "BID", "bid"]:
                auction_type = AuctionType.BID
            elif auction_type_str in ["즉시구매", "즉구", "BUYNOW", "buynow"]:
                auction_type = AuctionType.BUYNOW
            else:
                await interaction.response.send_message(
                    "⚠️ 경매 타입은 '입찰' 또는 '즉시구매'만 입력 가능합니다.",
                    ephemeral=True,
                )
                return

            # 2. 시작가 파싱
            try:
                starting_price = int(
                    self.starting_price_input.value.strip().replace(",", "")
                )
            except ValueError:
                await interaction.response.send_message(
                    "⚠️ 시작가는 숫자만 입력해주세요.", ephemeral=True
                )
                return

            if starting_price < 100:
                await interaction.response.send_message(
                    "⚠️ 시작가는 최소 100G 이상이어야 합니다.", ephemeral=True
                )
                return

            # 3. 즉구가 파싱 (선택사항)
            buyout_price = None
            buyout_price_str = self.buyout_price_input.value.strip()
            if buyout_price_str:
                try:
                    buyout_price = int(buyout_price_str.replace(",", ""))
                except ValueError:
                    await interaction.response.send_message(
                        "⚠️ 즉구가는 숫자만 입력해주세요.", ephemeral=True
                    )
                    return

                if buyout_price <= starting_price:
                    await interaction.response.send_message(
                        "⚠️ 즉구가는 시작가보다 높아야 합니다.", ephemeral=True
                    )
                    return

            # 즉시구매 경매는 즉구가 없음
            if auction_type == AuctionType.BUYNOW and buyout_price is not None:
                await interaction.response.send_message(
                    "⚠️ '즉시구매' 타입에서는 즉구가를 설정할 수 없습니다. "
                    "시작가가 곧 판매 가격입니다.",
                    ephemeral=True,
                )
                return

            # 4. 경매 기간 파싱
            try:
                duration_hours = int(self.duration_input.value.strip())
            except ValueError:
                await interaction.response.send_message(
                    "⚠️ 경매 기간은 숫자만 입력해주세요.", ephemeral=True
                )
                return

            if not (1 <= duration_hours <= 72):
                await interaction.response.send_message(
                    "⚠️ 경매 기간은 1~72시간 사이여야 합니다.", ephemeral=True
                )
                return

            # 리스팅 생성
            await interaction.response.defer(ephemeral=False)

            listing = await AuctionService.create_listing(
                user=self.db_user,
                inventory_id=self.inventory_item.id,
                auction_type=auction_type,
                starting_price=starting_price,
                buyout_price=buyout_price,
                duration_hours=duration_hours,
            )

            # DB에서 최신 골드 값 새로고침
            await self.db_user.refresh_from_db()

            # 성공 메시지
            auction_type_display = "입찰 경매" if auction_type == AuctionType.BID else "즉시구매"
            item = await self.inventory_item.item.get()

            msg = (
                f"✅ **경매 등록 완료!**\n"
                f"아이템: **{item.name}** (강화 +{self.inventory_item.enhancement_level})\n"
                f"타입: **{auction_type_display}**\n"
                f"시작가: **{starting_price:,}G**\n"
            )

            if buyout_price:
                msg += f"즉구가: **{buyout_price:,}G**\n"

            msg += (
                f"경매 기간: **{duration_hours}시간**\n"
                f"등록 수수료: **{int(starting_price * 0.02):,}G** (2%)\n"
                f"현재 보유 골드: **{self.db_user.gold:,}G**"
            )

            await interaction.followup.send(msg, ephemeral=False)

            # 부모 View 갱신
            await self.parent_view.refresh_data()
            embed = self.parent_view.create_embed()
            await self.parent_view.message.edit(embed=embed, view=self.parent_view)

        except AuctionError as e:
            await interaction.followup.send(f"⚠️ 경매 등록 실패: {e}", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(
                f"❌ 경매 등록 중 오류가 발생했습니다: {e}", ephemeral=True
            )
