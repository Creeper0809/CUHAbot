"""
전투 전용 컨트롤 View
"""
from __future__ import annotations

import discord

from service.skill.ultimate_service import (
    can_cast_ultimate,
    get_ultimate_mode_for_skill,
    is_ultimate_on_cooldown,
    request_manual_ultimate,
)


class CombatControlView(discord.ui.View):
    def __init__(self, session, actor_discord_id: int, timeout: int | None = None):
        super().__init__(timeout=timeout)
        self.session = session
        self.actor_discord_id = actor_discord_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.actor_discord_id:
            await interaction.response.send_message("본인 전투 창만 조작할 수 있습니다.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="🔥 궁극기 예약", style=discord.ButtonStyle.primary, row=0)
    async def reserve_ultimate(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.session or not self.session.in_combat:
            await interaction.response.send_message("⚠️ 현재 전투 중이 아닙니다.", ephemeral=True)
            return

        actor = self._find_actor()
        if not actor:
            await interaction.response.send_message("⚠️ 전투 참가자 정보를 찾을 수 없습니다.", ephemeral=True)
            return

        skill_id = getattr(actor, "equipped_ultimate_skill", 0)
        if not skill_id:
            await interaction.response.send_message("⚠️ 장착된 궁극기가 없습니다.", ephemeral=True)
            return

        mode = get_ultimate_mode_for_skill(skill_id)
        if mode != "manual":
            await interaction.response.send_message(
                "⚠️ 현재 장착한 궁극기는 자동 발동형입니다.",
                ephemeral=True
            )
            return

        if getattr(actor, "manual_ultimate_requested", False):
            await interaction.response.send_message("⏳ 이미 예약되어 있습니다.", ephemeral=True)
            return

        if is_ultimate_on_cooldown(actor):
            cd = int(getattr(actor, "ultimate_cooldown_remaining", 0))
            await interaction.response.send_message(
                f"⚠️ 궁극기 쿨다운 중입니다. ({cd}턴 남음)",
                ephemeral=True
            )
            return

        if not can_cast_ultimate(actor):
            gauge = int(getattr(actor, "ultimate_gauge", 0))
            await interaction.response.send_message(
                f"⚠️ 궁극기 게이지가 부족합니다. ({gauge}/100)",
                ephemeral=True
            )
            return

        request_manual_ultimate(actor)
        await interaction.response.send_message(
            "🔥 궁극기 예약 완료! 다음 행동 가능 턴에 발동합니다.",
            ephemeral=True
        )

    def _find_actor(self):
        if not self.session:
            return None
        leader = getattr(self.session, "user", None)
        if leader and getattr(leader, "discord_id", None) == self.actor_discord_id:
            return leader

        participants = getattr(self.session, "participants", {}) or {}
        for participant in participants.values():
            if getattr(participant, "discord_id", None) == self.actor_discord_id:
                return participant
        return None
