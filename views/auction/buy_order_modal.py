"""
구매 주문 생성 Modal

사용자가 원하는 아이템 조건과 최대 지불 가격을 제시합니다.
"""
import discord

from exceptions import AuctionError
from models.users import User
from models.item import Item
from service.auction.auction_service import AuctionService


class CreateBuyOrderModal(discord.ui.Modal, title="📋 구매 주문 생성"):
    """
    구매 주문 Modal

    - 아이템 ID, 강화 범위, 등급 범위, 최대 가격, 기간 입력
    - 주문 시 최대 가격만큼 골드 차감 (에스크로)
    - 조건에 맞는 리스팅이 등록되면 자동 매칭
    """

    item_id_input = discord.ui.TextInput(
        label="아이템 ID",
        placeholder="원하는 아이템의 ID를 입력하세요",
        required=True,
        max_length=10,
    )

    enhancement_range_input = discord.ui.TextInput(
        label="강화 범위",
        placeholder="예: 0-10 또는 5 (단일값)",
        required=False,
        default="0-99",
        max_length=20,
    )

    grade_range_input = discord.ui.TextInput(
        label="등급 범위",
        placeholder="예: 1-5 또는 3 (D=1, S=5, 신화=8)",
        required=False,
        default="0-8",
        max_length=20,
    )

    max_price_input = discord.ui.TextInput(
        label="최대 지불 가격",
        placeholder="최대 얼마까지 지불할 수 있나요? (최소 100G)",
        required=True,
        max_length=20,
    )

    duration_input = discord.ui.TextInput(
        label="주문 유지 시간 (시간)",
        placeholder="1~72 (기본: 24시간)",
        required=False,
        default="24",
        max_length=3,
    )

    def __init__(self, db_user: User, parent_view: "AuctionMainView"):
        super().__init__()
        self.db_user = db_user
        self.parent_view = parent_view

    async def on_submit(self, interaction: discord.Interaction):
        """구매 주문 생성"""
        try:
            # 1. 아이템 ID 파싱 및 검증
            try:
                item_id = int(self.item_id_input.value.strip())
            except ValueError:
                await interaction.response.send_message(
                    "⚠️ 아이템 ID는 숫자만 입력해주세요.", ephemeral=True
                )
                return

            item = await Item.get_or_none(id=item_id)
            if not item:
                await interaction.response.send_message(
                    f"⚠️ 아이템 ID {item_id}를 찾을 수 없습니다.", ephemeral=True
                )
                return

            # 2. 강화 범위 파싱
            enhancement_range_str = self.enhancement_range_input.value.strip()
            try:
                if "-" in enhancement_range_str:
                    parts = enhancement_range_str.split("-")
                    min_enhancement = int(parts[0])
                    max_enhancement = int(parts[1])
                else:
                    min_enhancement = max_enhancement = int(enhancement_range_str)

                if min_enhancement < 0 or max_enhancement < 0:
                    raise ValueError("강화 수치는 0 이상이어야 합니다")
                if min_enhancement > max_enhancement:
                    raise ValueError("최소 강화가 최대 강화보다 클 수 없습니다")
            except Exception as e:
                await interaction.response.send_message(
                    f"⚠️ 강화 범위 형식이 올바르지 않습니다: {e}\n예: 0-10 또는 5",
                    ephemeral=True,
                )
                return

            # 3. 등급 범위 파싱
            grade_range_str = self.grade_range_input.value.strip()
            try:
                if "-" in grade_range_str:
                    parts = grade_range_str.split("-")
                    min_grade = int(parts[0])
                    max_grade = int(parts[1])
                else:
                    min_grade = max_grade = int(grade_range_str)

                if not (0 <= min_grade <= 8 and 0 <= max_grade <= 8):
                    raise ValueError("등급은 0~8 사이여야 합니다")
                if min_grade > max_grade:
                    raise ValueError("최소 등급이 최대 등급보다 클 수 없습니다")
            except Exception as e:
                await interaction.response.send_message(
                    f"⚠️ 등급 범위 형식이 올바르지 않습니다: {e}\n예: 1-5 또는 3",
                    ephemeral=True,
                )
                return

            # 4. 최대 가격 파싱
            try:
                max_price = int(self.max_price_input.value.strip().replace(",", ""))
            except ValueError:
                await interaction.response.send_message(
                    "⚠️ 최대 가격은 숫자만 입력해주세요.", ephemeral=True
                )
                return

            if max_price < 100:
                await interaction.response.send_message(
                    "⚠️ 최대 가격은 최소 100G 이상이어야 합니다.", ephemeral=True
                )
                return

            # 5. 주문 기간 파싱
            try:
                duration_hours = int(self.duration_input.value.strip())
            except ValueError:
                await interaction.response.send_message(
                    "⚠️ 주문 기간은 숫자만 입력해주세요.", ephemeral=True
                )
                return

            if not (1 <= duration_hours <= 72):
                await interaction.response.send_message(
                    "⚠️ 주문 기간은 1~72시간 사이여야 합니다.", ephemeral=True
                )
                return

            # 구매 주문 생성
            await interaction.response.defer(ephemeral=False)

            buy_order = await AuctionService.create_buy_order(
                user=self.db_user,
                item_id=item_id,
                max_price=max_price,
                min_enhancement=min_enhancement,
                max_enhancement=max_enhancement,
                min_grade=min_grade,
                max_grade=max_grade,
                duration_hours=duration_hours,
            )

            # DB에서 최신 골드 값 새로고침
            await self.db_user.refresh_from_db()

            # 성공 메시지
            await interaction.followup.send(
                f"✅ **구매 주문 생성 완료!**\n"
                f"아이템: **{item.name}**\n"
                f"강화: **+{min_enhancement}~+{max_enhancement}**\n"
                f"등급: **{min_grade}~{max_grade}**\n"
                f"최대 가격: **{max_price:,}G**\n"
                f"유지 시간: **{duration_hours}시간**\n"
                f"에스크로: **{max_price:,}G** 차감됨\n"
                f"현재 보유 골드: **{self.db_user.gold:,}G**",
                ephemeral=False,
            )

            # 부모 View 갱신
            await self.parent_view.refresh_data()
            embed = self.parent_view.create_embed()
            await self.parent_view.message.edit(embed=embed, view=self.parent_view)

        except AuctionError as e:
            await interaction.followup.send(f"⚠️ 구매 주문 생성 실패: {e}", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(
                f"❌ 구매 주문 생성 중 오류가 발생했습니다: {e}", ephemeral=True
            )
