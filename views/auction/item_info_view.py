"""
경매 아이템 정보 View

경매 리스팅의 아이템 상세 정보를 표시합니다.
"""
import discord
from typing import Optional

from models.auction_listing import AuctionListing
from service.item.grade_service import GradeService
from utils.grade_display import get_grade_emoji, format_item_name


class AuctionItemInfoView(discord.ui.View):
    """경매 아이템 정보 View"""

    def __init__(
        self,
        user: discord.User,
        listing: AuctionListing,
        timeout: int = 60,
    ):
        super().__init__(timeout=timeout)
        self.user = user
        self.listing = listing
        self.message: Optional[discord.Message] = None

        self.add_item(CloseButton())

    def create_embed(self) -> discord.Embed:
        """아이템 상세 정보 Embed 생성"""
        listing = self.listing
        instance_grade = listing.instance_grade

        # 등급 이모지 및 포맷팅된 이름
        grade_emoji = get_grade_emoji(instance_grade) if instance_grade > 0 else ""
        formatted_name = format_item_name(listing.item_name, instance_grade if instance_grade > 0 else None)
        enhance_str = f" +{listing.enhancement_level}" if listing.enhancement_level > 0 else ""

        # 축복/저주 상태
        status_emoji = ""
        if listing.is_blessed:
            status_emoji = " ✨"
        elif listing.is_cursed:
            status_emoji = " 💀"

        embed = discord.Embed(
            title=f"{grade_emoji} {formatted_name}{enhance_str}{status_emoji}",
            description=f"경매 #{listing.id}의 아이템 정보",
            color=discord.Color.blue()
        )

        # 아이템 기본 정보
        self._add_equipment_info(embed)

        # 인스턴스 등급 정보
        if instance_grade > 0:
            self._add_grade_info(embed)

        # 축복/저주 상태
        if listing.is_blessed or listing.is_cursed:
            self._add_status_info(embed)

        # 특수 효과
        if listing.special_effects:
            self._add_special_effects(embed)

        return embed

    def _add_equipment_info(self, embed: discord.Embed):
        """장비 정보 추가"""
        from models.repos.static_cache import get_equipment_info

        info = get_equipment_info(self.listing.item_id)

        if not info:
            embed.add_field(
                name="⚠️ 주의",
                value="아이템 정보를 불러올 수 없습니다.",
                inline=False
            )
            return

        # 강화 레벨
        if self.listing.enhancement_level > 0:
            embed.add_field(
                name="⚡ 강화",
                value=f"+{self.listing.enhancement_level}",
                inline=True
            )

        # 레벨 제한
        if info.get("require_level", 1) > 1:
            embed.add_field(
                name="📊 요구 레벨",
                value=f"Lv.{info['require_level']}",
                inline=True
            )

        # 장비 슬롯
        if info.get("equip_pos"):
            embed.add_field(
                name="📍 장비 슬롯",
                value=info["equip_pos"],
                inline=True
            )

        # 세트 이름
        if info.get("set_name"):
            embed.add_field(
                name="🎭 세트",
                value=info["set_name"],
                inline=True
            )

        # === 요구 능력치 ===
        req_stats = []
        for stat_name in ["require_str", "require_int", "require_dex", "require_vit", "require_luk"]:
            val = info.get(stat_name, 0)
            if val > 0:
                display_name = stat_name.replace("require_", "").upper()
                req_stats.append(f"{display_name} {val}")

        if req_stats:
            req_desc = " / ".join(req_stats)
            req_desc += "\n💡 장착하려면 위 능력치를 만족해야 합니다"
            embed.add_field(
                name="📋 요구 능력치",
                value=req_desc,
                inline=False
            )

        # === 스탯 정보 (상세 계산식 포함) ===
        grade_mult = GradeService.get_stat_multiplier(self.listing.instance_grade) if self.listing.instance_grade > 0 else 1.0
        enhance_mult = 1 + (self.listing.enhancement_level * 0.05) if self.listing.enhancement_level > 0 else 1.0

        stat_labels = {
            "attack": "⚔️ 공격력",
            "ap_attack": "🔮 마법공격력",
            "hp": "❤️ 체력",
            "ad_defense": "🛡️ 물리방어",
            "ap_defense": "✨ 마법방어",
            "speed": "⚡ 속도",
        }

        stat_lines = []
        total_bonus = 0

        # ANSI 색상 코드
        green = "\u001b[0;32m"  # 초록색 (등급)
        yellow = "\u001b[1;33m"  # 노란색 (강화)
        reset = "\u001b[0m"

        for key, label in stat_labels.items():
            base_val = info.get(key) or 0
            if base_val <= 0:
                continue

            # 단계별 계산
            grade_bonus = int(base_val * (grade_mult - 1))
            total_before_enhance = int(base_val * grade_mult)
            enhance_bonus = int(total_before_enhance * (enhance_mult - 1))
            final_val = int(base_val * grade_mult * enhance_mult)
            total_bonus += (final_val - base_val)

            # 표시 형식
            if grade_bonus == 0 and enhance_bonus == 0:
                stat_lines.append(f"{label}: {base_val}")
            else:
                breakdown_parts = [str(base_val)]
                if grade_bonus > 0:
                    breakdown_parts.append(f"{green}{grade_bonus}{reset}")
                if enhance_bonus > 0:
                    breakdown_parts.append(f"{yellow}{enhance_bonus}{reset}")
                breakdown_text = " + ".join(breakdown_parts)
                stat_lines.append(f"{label}: {final_val} ({breakdown_text})")

        if stat_lines:
            stat_header = "📊 스탯 상세"
            if total_bonus > 0:
                stat_header += f" (총 보너스: +{total_bonus})"

            stat_value = "```ansi\n" + "\n".join(stat_lines) + "\n```"
            embed.add_field(
                name=stat_header,
                value=stat_value,
                inline=False
            )

    def _add_grade_info(self, embed: discord.Embed):
        """등급 정보 추가"""
        from config.grade import get_grade_info

        instance_grade = self.listing.instance_grade
        grade_info_data = get_grade_info(instance_grade)

        if grade_info_data:
            grade_display = GradeService.get_grade_display(instance_grade)
            grade_mult = grade_info_data.stat_multiplier

            grade_desc = f"{grade_display}\n"
            grade_desc += f"• 기본 스탯 **{grade_mult}배** 증폭\n"

            if grade_info_data.effect_slots_max > 0:
                grade_desc += f"• 특수 효과 {grade_info_data.effect_slots_min}~{grade_info_data.effect_slots_max}개 부여"
            else:
                grade_desc += "• 특수 효과 없음"

            embed.add_field(
                name="🎲 인스턴스 등급",
                value=grade_desc,
                inline=False
            )

    def _add_status_info(self, embed: discord.Embed):
        """축복/저주 상태 정보 추가"""
        if self.listing.is_blessed:
            status_desc = "✨ **축복받은 장비**\n"
            status_desc += "• 특별한 가호가 깃든 장비입니다\n"
            status_desc += "• 추가 효과가 부여될 수 있습니다"
        elif self.listing.is_cursed:
            status_desc = "💀 **저주받은 장비**\n"
            status_desc += "• 사악한 기운이 깃든 장비입니다\n"
            status_desc += "• 착용 시 불리한 효과가 있을 수 있습니다"
        else:
            return

        embed.add_field(
            name="🔮 특수 상태",
            value=status_desc,
            inline=False
        )

    def _add_special_effects(self, embed: discord.Embed):
        """특수 효과 정보 추가"""
        from config.grade import SPECIAL_EFFECT_POOL

        effect_lines = []
        name_map = {e.effect_type: e for e in SPECIAL_EFFECT_POOL}

        special_effects = self.listing.special_effects
        if special_effects and isinstance(special_effects, list):
            for effect in special_effects:
                effect_def = name_map.get(effect.get("type"))
                if effect_def:
                    value = effect.get("value", 0)
                    suffix = "%" if effect_def.is_percent else ""
                    effect_lines.append(f"⭐ {effect_def.name}: +{value}{suffix}")

        if effect_lines:
            effect_value = "```ansi\n" + "\n".join(effect_lines) + "\n```"
            embed.add_field(
                name="✨ 특수 효과",
                value=effect_value,
                inline=False
            )

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user == self.user


class CloseButton(discord.ui.Button):
    """닫기 버튼"""

    def __init__(self):
        super().__init__(
            label="닫기",
            style=discord.ButtonStyle.danger,
            emoji="❌",
            row=0
        )

    async def callback(self, interaction: discord.Interaction):
        if self.view.message:
            await self.view.message.delete()
        else:
            await interaction.response.edit_message(
                content="아이템 정보를 닫았습니다.",
                embed=None,
                view=None
            )
