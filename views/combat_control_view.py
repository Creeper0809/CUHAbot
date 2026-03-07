"""
전투 전용 컨트롤 View
"""
from __future__ import annotations

import discord

from models.repos.raid_repo import find_all_raid_parts
from service.session import ContentType
from service.raid.raid_service import queue_raid_target_selection
from service.raid.raid_minigame_service import (
    get_minigame_choice_payloads,
    get_pending_raid_minigame,
    resolve_raid_minigame_choice,
)
from service.raid.raid_special_action_service import use_raid_special_action
from service.skill.ultimate_service import (
    can_cast_ultimate,
    get_ultimate_mode_for_skill,
    is_ultimate_on_cooldown,
    request_manual_ultimate,
)


class RaidTargetSelect(discord.ui.Select):
    def __init__(self, session):
        self.session = session
        options = []

        if session and session.raid_id:
            destroyed = getattr(session, "raid_destroyed_parts", set()) or set()
            current_round = 1
            if getattr(session, "combat_context", None):
                current_round = int(getattr(session.combat_context, "round_number", 1))
            parts = find_all_raid_parts(session.raid_id)
            for part in parts:
                # 파괴된 부위는 선택 불가, 본체는 항상 허용
                if part.part_key != "body" and part.part_key in destroyed:
                    continue
                if current_round < int(getattr(part, "targetable_from_turn", 1)):
                    continue
                options.append(
                    discord.SelectOption(
                        label=part.part_name[:100],
                        value=part.part_key,
                        description=f"우선 타겟: {part.part_key}"[:100],
                    )
                )

        if not options:
            options.append(discord.SelectOption(label="선택 가능한 부위 없음", value="none"))

        super().__init__(
            placeholder="🎯 우선 공격 부위 선택 (다음 턴 적용)",
            min_values=1,
            max_values=1,
            options=options[:25],
            row=1,
        )

    async def callback(self, interaction: discord.Interaction):
        if not self.session or not self.session.in_combat:
            await interaction.response.send_message("⚠️ 현재 전투 중이 아닙니다.", ephemeral=True)
            return

        selected = self.values[0]
        if selected == "none":
            await interaction.response.send_message("⚠️ 선택 가능한 부위가 없습니다.", ephemeral=True)
            return

        current_round = 0
        if getattr(self.session, "combat_context", None):
            current_round = int(getattr(self.session.combat_context, "round_number", 0))

        ok = queue_raid_target_selection(self.session, selected, current_round)
        if not ok:
            await interaction.response.send_message("⚠️ 레이드 타겟 변경에 실패했습니다.", ephemeral=True)
            return

        apply_round = getattr(self.session, "raid_target_apply_turn", current_round + 1)
        await interaction.response.send_message(
            f"🎯 우선 타겟을 **{selected}**(으)로 예약했습니다. "
            f"**라운드 {apply_round}**부터 적용됩니다.",
            ephemeral=True
        )


class RaidSpecialActionSelect(discord.ui.Select):
    def __init__(self, session):
        self.session = session
        options = []
        if session and session.raid_id:
            from models.repos.raid_repo import find_raid_special_actions

            for key, action in find_raid_special_actions().items():
                options.append(
                    discord.SelectOption(
                        label=action.action_name[:100],
                        value=key,
                        description=f"CD {action.cooldown_rounds}R / 라운드당 1회"[:100],
                    )
                )
        if not options:
            options.append(discord.SelectOption(label="사용 가능한 액션 없음", value="none"))

        super().__init__(
            placeholder="🛠️ 레이드 특수 액션 사용",
            min_values=1,
            max_values=1,
            options=options[:25],
            row=2,
        )

    async def callback(self, interaction: discord.Interaction):
        if not self.session or not self.session.in_combat:
            await interaction.response.send_message("⚠️ 현재 전투 중이 아닙니다.", ephemeral=True)
            return
        selected = self.values[0]
        if selected == "none":
            await interaction.response.send_message("⚠️ 사용 가능한 액션이 없습니다.", ephemeral=True)
            return

        actor = self.view._find_actor() if hasattr(self.view, "_find_actor") else None
        if not actor:
            await interaction.response.send_message("⚠️ 액터 정보를 찾지 못했습니다.", ephemeral=True)
            return

        current_round = 1
        if getattr(self.session, "combat_context", None):
            current_round = int(getattr(self.session.combat_context, "round_number", 1))

        logs = use_raid_special_action(self.session, actor, selected, current_round)

        # 전투 로그에 즉시 반영
        if getattr(self.session, "combat_context", None):
            for log in logs:
                self.session.combat_context.combat_log.append(log)

        await interaction.response.send_message("\n".join(logs), ephemeral=True)


class RaidMinigameSelect(discord.ui.Select):
    def __init__(self, session):
        self.session = session
        self.minigame = get_pending_raid_minigame(session)

        if self.minigame and session and getattr(session, "combat_context", None):
            current_round = int(getattr(session.combat_context, "round_number", 1) or 1)
            payloads, progress_text = get_minigame_choice_payloads(session, current_round)
            options = [
                discord.SelectOption(
                    label=label[:100],
                    value=value,
                    description=f"{self.minigame.minigame_name} {progress_text}"[:100],
                )
                for value, label in payloads
            ]
        else:
            options = [discord.SelectOption(label="진행 중인 미니게임 없음", value="none")]

        super().__init__(
            placeholder="🎮 레이드 미니게임 입력",
            min_values=1,
            max_values=1,
            options=options[:25],
            row=3,
        )

    async def callback(self, interaction: discord.Interaction):
        if not self.session or not self.session.in_combat:
            await interaction.response.send_message("⚠️ 현재 전투 중이 아닙니다.", ephemeral=True)
            return

        selected = self.values[0]
        if selected == "none":
            await interaction.response.send_message("⚠️ 진행 중인 미니게임이 없습니다.", ephemeral=True)
            return

        current_round = 1
        if getattr(self.session, "combat_context", None):
            current_round = int(getattr(self.session.combat_context, "round_number", 1))

        logs = resolve_raid_minigame_choice(self.session, interaction.user, selected, current_round)

        if getattr(self.session, "combat_context", None):
            for log in logs:
                self.session.combat_context.combat_log.append(log)

        await interaction.response.send_message("\n".join(logs), ephemeral=True)


class RaidMinigameChoiceButton(discord.ui.Button):
    def __init__(self, session, value: str, label: str, row: int = 3, disabled: bool = False):
        self.session = session
        self.choice_value = value
        style = discord.ButtonStyle.secondary
        if value == "P":
            style = discord.ButtonStyle.success
        elif value in ("E", "L"):
            style = discord.ButtonStyle.primary
        elif value in ("S", "R"):
            style = discord.ButtonStyle.danger
        elif value == "B":
            style = discord.ButtonStyle.success
        super().__init__(label=label[:80], style=style, row=row, disabled=disabled)

    async def callback(self, interaction: discord.Interaction):
        if not self.session or not self.session.in_combat:
            await interaction.response.send_message("⚠️ 현재 전투 중이 아닙니다.", ephemeral=True)
            return

        current_round = 1
        if getattr(self.session, "combat_context", None):
            current_round = int(getattr(self.session.combat_context, "round_number", 1))

        logs = resolve_raid_minigame_choice(
            self.session,
            interaction.user,
            self.choice_value,
            current_round,
        )

        if getattr(self.session, "combat_context", None):
            for log in logs:
                self.session.combat_context.combat_log.append(log)

        # 미니게임 완료 시 버튼 비활성화
        refreshed_view = CombatControlView(self.session, interaction.user.id, timeout=None)
        await interaction.response.edit_message(view=refreshed_view)
        await interaction.followup.send("\n".join(logs), ephemeral=True)


class CombatControlView(discord.ui.View):
    def __init__(self, session, actor_discord_id: int, timeout: int | None = None):
        super().__init__(timeout=timeout)
        self.session = session
        self.actor_discord_id = actor_discord_id

        if session and session.content_type == ContentType.RAID:
            self.add_item(RaidTargetSelect(session))
            self.add_item(RaidSpecialActionSelect(session))
            pending_mg = get_pending_raid_minigame(session)
            if pending_mg:
                if getattr(session, "combat_context", None):
                    current_round = int(getattr(session.combat_context, "round_number", 1) or 1)
                    payloads, _ = get_minigame_choice_payloads(session, current_round)
                else:
                    payloads = []

                # 전용 버튼 UI 우선, fallback은 기존 셀렉트 사용
                if payloads:
                    stage_inputs = dict(getattr(session, "raid_minigame_stage_inputs", {}) or {})
                    already_submitted = str(actor_discord_id) in stage_inputs
                    for value, label in payloads[:4]:
                        self.add_item(
                            RaidMinigameChoiceButton(
                                session,
                                value,
                                f"🎮 {label}",
                                row=3,
                                disabled=already_submitted,
                            )
                        )
                else:
                    self.add_item(RaidMinigameSelect(session))

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
