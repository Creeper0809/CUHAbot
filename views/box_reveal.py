"""Discord-native staged reveal for already-committed box rewards."""

from __future__ import annotations

import asyncio
from collections import Counter

import discord

from config import BOX_PITY_BY_ID
from service.item.box_open_service import (
    BoxOpenBatch, BoxOpenService, BoxRewardOutcome, pity_chances,
)


GRADE_COLORS = {
    0: 0x95A5A6, 1: 0xECF0F1, 2: 0x2ECC71, 3: 0x3498DB,
    4: 0x9B59B6, 5: 0xF1C40F, 6: 0xE67E22, 7: 0xE74C3C, 8: 0x00E5FF,
}
GRADE_EMOJI = {0: "💰", 1: "⬜", 2: "🟩", 3: "🟦", 4: "🟪", 5: "🟨", 6: "🟧", 7: "❤️", 8: "💎"}
TYPE_NAMES = {"gold": "골드", "equipment": "장비", "skill": "스킬"}


def _pity_text(outcome: BoxRewardOutcome, box_id: int) -> str:
    rule = BOX_PITY_BY_ID.get(box_id)
    if not rule:
        return "확정 등급 상자 · 천장 미적용"
    base, adjusted, _ = pity_chances(box_id, outcome.pity_after)
    remaining = max(0, rule.hard_pity - outcome.pity_after)
    return (
        f"기본 확률 {base * 100:.2f}% · "
        f"현재 보정 확률 {adjusted * 100:.2f}%\n"
        f"실패 {outcome.pity_after}회 · 확정까지 {remaining}회"
    )


def create_reveal_embed(batch: BoxOpenBatch, stage: str, outcome_index: int = 0) -> discord.Embed:
    outcome = batch.outcomes[min(outcome_index, len(batch.outcomes) - 1)]
    if stage == "closed":
        embed = discord.Embed(
            title=f"📦 {batch.box_name}",
            description="봉인이 풀리기 시작합니다…",
            color=discord.Color.dark_grey(),
        )
        embed.add_field(name="천장", value=_pity_text(outcome, batch.box_id), inline=False)
        return embed
    if stage == "shake":
        return discord.Embed(title="▰▱▱ 봉인이 흔들립니다…", color=discord.Color.dark_grey())
    if stage == "type":
        return discord.Embed(
            title=f"▰▰▱ {TYPE_NAMES.get(outcome.reward_type, outcome.reward_type)} 기운!",
            description="등급을 확인하는 중…",
            color=discord.Color.blurple(),
        )
    if stage == "grade":
        grade = outcome.grade_name or "골드"
        return discord.Embed(
            title=f"{GRADE_EMOJI.get(outcome.grade, '✨')} {grade}",
            description="마지막 봉인이 해제됩니다…",
            color=GRADE_COLORS.get(outcome.grade, 0x95A5A6),
        )
    return create_final_embed(batch)


def _outcome_line(outcome: BoxRewardOutcome) -> str:
    if outcome.reward_type == "gold":
        line = f"💰 **{outcome.gold:,} 골드**"
    else:
        line = f"{GRADE_EMOJI.get(outcome.grade, '✨')} **[{outcome.grade_name}] {outcome.name}** ×{outcome.quantity}"
        if outcome.special_effects:
            effects = ", ".join(
                str(effect.get("name") or effect.get("type") or effect)
                if isinstance(effect, dict) else str(effect)
                for effect in outcome.special_effects[:3]
            )
            line += f"\n  특수 효과: {effects}"
    badges = []
    if outcome.new_collection:
        badges.append("🆕 첫 도감")
    if outcome.hard_pity_triggered:
        badges.append("🎯 천장")
    return line + (f" · {' · '.join(badges)}" if badges else "")


def create_final_embed(batch: BoxOpenBatch) -> discord.Embed:
    highest = max((outcome.grade for outcome in batch.outcomes), default=0)
    embed = discord.Embed(
        title=f"✨ {batch.box_name} 공개 완료!",
        color=GRADE_COLORS.get(highest, 0x95A5A6),
    )
    if len(batch.outcomes) <= 5:
        embed.description = "\n".join(_outcome_line(outcome) for outcome in batch.outcomes)
    else:
        counts = Counter(
            (outcome.reward_type, outcome.grade_name or "골드") for outcome in batch.outcomes
        )
        embed.description = "\n".join(
            f"• {TYPE_NAMES.get(kind, kind)} [{grade}] × **{count}**"
            for (kind, grade), count in sorted(counts.items())
        )
        highlights = [outcome for outcome in batch.outcomes if outcome.grade >= 5]
        if highlights:
            embed.add_field(
                name="🌟 S 이상 하이라이트",
                value="\n".join(_outcome_line(outcome) for outcome in highlights[:10]),
                inline=False,
            )
    last = batch.outcomes[-1]
    embed.add_field(name="현재 천장", value=_pity_text(last, batch.box_id), inline=False)
    if batch.replayed:
        embed.set_footer(text="이미 처리된 요청의 확정 결과입니다.")
    return embed


class BoxRevealView(discord.ui.View):
    def __init__(self, owner_id: int, *, continue_event: asyncio.Event | None = None):
        super().__init__(timeout=120)
        self.owner_id = owner_id
        self.skip_event = asyncio.Event()
        self.continue_event = continue_event

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.owner_id:
            return True
        await interaction.response.send_message("이 상자는 주인만 조작할 수 있습니다.", ephemeral=True)
        return False

    @discord.ui.button(label="즉시 공개", style=discord.ButtonStyle.primary, custom_id="box_reveal:skip")
    async def skip(self, interaction: discord.Interaction, _: discord.ui.Button):
        self.skip_event.set()
        await interaction.response.defer()

    async def wait_or_skip(self, delay: float) -> bool:
        if self.skip_event.is_set():
            return True
        try:
            await asyncio.wait_for(self.skip_event.wait(), timeout=delay)
            return True
        except asyncio.TimeoutError:
            return False


class BoxResultView(discord.ui.View):
    def __init__(self, owner_id: int, batch: BoxOpenBatch, *, continue_event: asyncio.Event | None = None):
        super().__init__(timeout=120)
        self.owner_id = owner_id
        self.batch = batch
        self.continue_event = continue_event
        if continue_event is None:
            self.remove_item(self.continue_button)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.owner_id:
            return True
        await interaction.response.send_message("이 결과는 주인만 조작할 수 있습니다.", ephemeral=True)
        return False

    @discord.ui.button(label="다시 열기", style=discord.ButtonStyle.success, custom_id="box_reveal:again")
    async def again(self, interaction: discord.Interaction, _: discord.ui.Button):
        from models.user_inventory import UserInventory
        from models.repos import find_account_by_discordid

        user = await find_account_by_discordid(interaction.user.id)
        inventory = await UserInventory.filter(
            user=user, item_id=self.batch.box_id, quantity__gt=0
        ).order_by("id").first()
        if not inventory:
            await interaction.response.send_message("같은 상자가 더 없습니다.", ephemeral=True)
            return
        batch = await BoxOpenService.open_boxes(user, inventory.id, 1, interaction.id)
        await interaction.response.edit_message(embed=create_reveal_embed(batch, "closed"), view=None)
        await animate_box_reveal(interaction, batch, response_already_used=True)

    @discord.ui.button(label="인벤토리", style=discord.ButtonStyle.secondary, custom_id="box_reveal:inventory")
    async def inventory(self, interaction: discord.Interaction, _: discord.ui.Button):
        await interaction.response.send_message("`/인벤토리`에서 남은 상자와 획득품을 확인할 수 있습니다.", ephemeral=True)

    @discord.ui.button(label="계속 탐험", style=discord.ButtonStyle.primary, custom_id="box_reveal:continue")
    async def continue_button(self, interaction: discord.Interaction, _: discord.ui.Button):
        if self.continue_event:
            self.continue_event.set()
        await interaction.response.edit_message(view=None)
        self.stop()

    @discord.ui.button(label="닫기", style=discord.ButtonStyle.danger, custom_id="box_reveal:close")
    async def close(self, interaction: discord.Interaction, _: discord.ui.Button):
        await interaction.response.edit_message(view=None)
        self.stop()


async def animate_box_reveal(
    interaction: discord.Interaction,
    batch: BoxOpenBatch,
    *,
    response_already_used: bool = False,
    continue_event: asyncio.Event | None = None,
) -> None:
    reveal_view = BoxRevealView(interaction.user.id, continue_event=continue_event)
    if response_already_used:
        message = await interaction.original_response()
        await message.edit(embed=create_reveal_embed(batch, "closed"), view=reveal_view)
    else:
        await interaction.response.edit_message(
            embed=create_reveal_embed(batch, "closed"), view=reveal_view
        )
        message = await interaction.original_response()

    if len(batch.outcomes) >= 6:
        await message.edit(embed=create_reveal_embed(batch, "shake"), view=reveal_view)
        await reveal_view.wait_or_skip(1.2)
    elif len(batch.outcomes) == 1:
        elapsed = 0.0
        for stage, target_time in (("shake", 0.45), ("type", 1.05), ("grade", 1.65)):
            if await reveal_view.wait_or_skip(max(0.0, target_time - elapsed)):
                break
            await message.edit(embed=create_reveal_embed(batch, stage), view=reveal_view)
            elapsed = target_time
        if not reveal_view.skip_event.is_set():
            await reveal_view.wait_or_skip(max(0.0, 2.4 - elapsed))
    else:
        for index in range(len(batch.outcomes)):
            if await reveal_view.wait_or_skip(1.0):
                break
            await message.edit(embed=create_reveal_embed(batch, "grade", index), view=reveal_view)

    await message.edit(
        embed=create_final_embed(batch),
        view=BoxResultView(interaction.user.id, batch, continue_event=continue_event),
    )
