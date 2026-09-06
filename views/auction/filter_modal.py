"""
경매 검색/필터 Modal

사용자가 다양한 조건으로 경매 리스팅을 필터링할 수 있습니다.
"""
import discord
from typing import Optional

from models.item import ItemType


class FilterModal(discord.ui.Modal, title="🔍 검색/필터"):
    """
    경매 검색 필터 Modal

    4개 필터 (모두 선택적):
    - 아이템 타입: "장비" 또는 "소비"
    - 등급 범위: "1-5" (D=1, C=2, B=3, A=4, S=5, SS=6, SSS=7, 신화=8)
    - 강화 범위: "0-10"
    - 가격 범위: "1000-50000"
    """

    item_type_input = discord.ui.TextInput(
        label="아이템 타입",
        placeholder="장비 또는 소비 (선택사항)",
        required=False,
        max_length=10,
    )

    grade_range_input = discord.ui.TextInput(
        label="등급 범위",
        placeholder="예: 1-5 (D=1, S=5, 신화=8) (선택사항)",
        required=False,
        max_length=20,
    )

    enhancement_range_input = discord.ui.TextInput(
        label="강화 범위",
        placeholder="예: 0-10 (선택사항)",
        required=False,
        max_length=20,
    )

    price_range_input = discord.ui.TextInput(
        label="가격 범위",
        placeholder="예: 1000-50000 (선택사항)",
        required=False,
        max_length=30,
    )

    affix_input = discord.ui.TextInput(
        label="옵션 ID / 최소 티어 / 최소 수치",
        placeholder="예: burn_power / 2 / 8 (선택사항)",
        required=False,
        max_length=60,
    )

    def __init__(self, parent_view: "AuctionMainView"):
        super().__init__()
        self.parent_view = parent_view

    async def on_submit(self, interaction: discord.Interaction):
        """필터 적용 및 검색 결과 갱신"""
        filters = {}

        # 1. 아이템 타입 파싱
        item_type_str = self.item_type_input.value.strip()
        if item_type_str:
            if item_type_str in ["장비", "EQUIPMENT", "EQUIP"]:
                filters["item_type"] = ItemType.EQUIP
            elif item_type_str in ["소비", "CONSUMABLE", "CONSUME"]:
                filters["item_type"] = ItemType.CONSUME
            else:
                await interaction.response.send_message(
                    "⚠️ 아이템 타입은 '장비' 또는 '소비'만 입력 가능합니다.",
                    ephemeral=True,
                )
                return

        # 2. 등급 범위 파싱
        grade_range_str = self.grade_range_input.value.strip()
        if grade_range_str:
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

                filters["min_grade"] = min_grade
                filters["max_grade"] = max_grade
            except Exception as e:
                await interaction.response.send_message(
                    f"⚠️ 등급 범위 형식이 올바르지 않습니다: {e}\n예: 1-5 또는 3",
                    ephemeral=True,
                )
                return

        # 3. 강화 범위 파싱
        enhancement_range_str = self.enhancement_range_input.value.strip()
        if enhancement_range_str:
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

                filters["min_enhancement"] = min_enhancement
                filters["max_enhancement"] = max_enhancement
            except Exception as e:
                await interaction.response.send_message(
                    f"⚠️ 강화 범위 형식이 올바르지 않습니다: {e}\n예: 0-10 또는 5",
                    ephemeral=True,
                )
                return

        # 4. 가격 범위 파싱
        price_range_str = self.price_range_input.value.strip()
        if price_range_str:
            try:
                if "-" in price_range_str:
                    parts = price_range_str.split("-")
                    min_price = int(parts[0])
                    max_price = int(parts[1])
                else:
                    min_price = max_price = int(price_range_str)

                if min_price < 0 or max_price < 0:
                    raise ValueError("가격은 0 이상이어야 합니다")
                if min_price > max_price:
                    raise ValueError("최소 가격이 최대 가격보다 클 수 없습니다")

                filters["min_price"] = min_price
                filters["max_price"] = max_price
            except Exception as e:
                await interaction.response.send_message(
                    f"⚠️ 가격 범위 형식이 올바르지 않습니다: {e}\n예: 1000-50000 또는 10000",
                    ephemeral=True,
                )
                return

        # 5. 관계형 옵션 필터: affix_id / minimum tier / minimum value
        affix_str = self.affix_input.value.strip()
        if affix_str:
            try:
                parts = [part.strip() for part in affix_str.split("/")]
                from config.itemization_v4 import AFFIX_BY_ID
                if parts[0] not in AFFIX_BY_ID:
                    raise ValueError("알 수 없는 옵션 ID입니다")
                filters["affix_id"] = parts[0]
                if len(parts) >= 2 and parts[1]:
                    tier = int(parts[1])
                    if not 1 <= tier <= 5:
                        raise ValueError("티어는 1~5여야 합니다")
                    filters["min_affix_tier"] = tier
                if len(parts) >= 3 and parts[2]:
                    filters["min_affix_value"] = float(parts[2])
            except Exception as exc:
                await interaction.response.send_message(
                    f"⚠️ 옵션 필터 형식이 올바르지 않습니다: {exc}", ephemeral=True,
                )
                return

        # 필터 적용
        defaults = {
            "item_type": None, "item_grade": None, "min_grade": 0, "max_grade": 8,
            "min_enhancement": 0, "max_enhancement": 99,
            "min_price": 0, "max_price": 999999999,
            "affix_id": None, "min_affix_tier": None, "min_affix_value": None,
        }
        defaults.update(filters)
        self.parent_view.filters = defaults
        self.parent_view.page = 0  # 첫 페이지로 리셋

        # 데이터 재로드 및 UI 갱신
        await self.parent_view.refresh_data()
        embed = self.parent_view.create_embed()

        await interaction.response.edit_message(embed=embed, view=self.parent_view)

        # 피드백 메시지
        filter_desc = []
        if "item_type" in filters:
            filter_desc.append(f"타입: {filters['item_type'].value}")
        if "min_grade" in filters:
            filter_desc.append(
                f"등급: {filters['min_grade']}~{filters['max_grade']}"
            )
        if "min_enhancement" in filters:
            filter_desc.append(
                f"강화: +{filters['min_enhancement']}~+{filters['max_enhancement']}"
            )
        if "min_price" in filters:
            filter_desc.append(
                f"가격: {filters['min_price']:,}G~{filters['max_price']:,}G"
            )

        if filter_desc:
            filter_msg = " | ".join(filter_desc)
            await interaction.followup.send(
                f"✅ 필터 적용: {filter_msg}", ephemeral=True
            )
        else:
            await interaction.followup.send("✅ 모든 필터 해제", ephemeral=True)
