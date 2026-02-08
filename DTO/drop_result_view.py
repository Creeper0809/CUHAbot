"""
드롭 결과 UI

전투 승리 후 획득한 아이템을 표시하는 Discord Embed입니다.
"""
import discord
from typing import List, Optional
from dataclasses import dataclass

from config import EmbedColor
from utility.grade_display import format_item_name


@dataclass
class DropItem:
    """드롭된 아이템 정보"""
    name: str
    quantity: int = 1
    grade_id: Optional[int] = None
    enhancement_level: int = 0


@dataclass
class DropResult:
    """드롭 결과 정보"""
    monster_names: str
    turn_count: int
    exp_gained: int
    gold_gained: int
    dropped_items: List[DropItem]
    luck_bonus: float = 0.0  # 행운 보너스 (0.0 = 없음)


def create_drop_result_embed(result: DropResult) -> discord.Embed:
    """
    드롭 결과 임베드 생성

    Args:
        result: 드롭 결과 데이터

    Returns:
        Discord Embed 객체
    """
    embed = discord.Embed(
        title="🏆 전투 승리!",
        description=f"**{result.monster_names}** 처치 ({result.turn_count}턴)",
        color=EmbedColor.SUCCESS if hasattr(EmbedColor, 'SUCCESS') else 0x00FF00
    )

    # 획득 EXP/Gold
    exp_text = f"⭐ **{result.exp_gained:,}** EXP"
    gold_text = f"💰 **{result.gold_gained:,}** Gold"
    embed.add_field(
        name="보상",
        value=f"{exp_text}\n{gold_text}",
        inline=True
    )

    # 드롭 아이템
    if result.dropped_items:
        items_text = []
        for item in result.dropped_items:
            # 등급별 색상 적용
            formatted_name = format_item_name(item.name, item.grade_id)

            # 강화 레벨 표시
            enhance = f" +{item.enhancement_level}" if item.enhancement_level > 0 else ""

            # 수량 표시
            qty = f" x{item.quantity}" if item.quantity > 1 else ""

            items_text.append(f"📦 {formatted_name}{enhance}{qty}")

        embed.add_field(
            name=f"🎁 획득 아이템 ({len(result.dropped_items)})",
            value="\n".join(items_text),
            inline=False
        )
    else:
        embed.add_field(
            name="🎁 획득 아이템",
            value="드롭 아이템 없음",
            inline=False
        )

    # 행운 보너스 (있을 경우)
    if result.luck_bonus > 0:
        embed.set_footer(text=f"🍀 행운 보너스: +{result.luck_bonus * 100:.1f}%")

    return embed
