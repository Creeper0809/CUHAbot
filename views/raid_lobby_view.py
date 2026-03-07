import discord

from models.repos import find_account_by_discordid
from service.raid.raid_lobby_service import RaidLobbyState
from service.raid.raid_progress_service import check_raid_entry, consume_raid_entry


def create_raid_lobby_embed(lobby: RaidLobbyState) -> discord.Embed:
    lines = []
    for user_id, ready in lobby.participants.items():
        crown = "👑 " if user_id == lobby.leader_id else ""
        status = "✅ 준비" if ready else "⏳ 대기"
        lines.append(f"{crown}<@{user_id}> - {status}")

    member_text = "\n".join(lines) if lines else "아직 파티원이 없습니다."
    embed = discord.Embed(
        title=f"🐉 레이드 로비 - {lobby.raid_name}",
        description=(
            f"권장 레벨: **Lv.{lobby.required_level}+**\n"
            f"파티: **{lobby.party_size()}/{lobby.max_party_size}**\n"
            f"타임아웃: **{lobby.timeout_seconds}초**\n\n"
            f"{member_text}"
        ),
        color=discord.Color.red(),
    )
    embed.set_footer(text="리더가 시작하거나, 타임아웃 시 자동으로 시작됩니다.")
    return embed


class RaidLobbyView(discord.ui.View):
    def __init__(self, lobby: RaidLobbyState, timeout: int | None = None):
        super().__init__(timeout=timeout if timeout is not None else lobby.timeout_seconds)
        self.lobby = lobby

    @discord.ui.button(label="✅ 준비 완료", style=discord.ButtonStyle.success, custom_id="raid_lobby_ready")
    async def ready_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        if user_id not in self.lobby.participants:
            await interaction.response.send_message("❌ 로비 참가자만 준비할 수 있습니다.", ephemeral=True)
            return
        if self.lobby.started or self.lobby.cancelled:
            await interaction.response.send_message("⚠️ 이미 시작되었거나 취소된 로비입니다.", ephemeral=True)
            return

        self.lobby.participants[user_id] = True
        await interaction.response.send_message("✅ 준비 완료 처리되었습니다.", ephemeral=True)

        if interaction.message:
            try:
                await interaction.message.edit(embed=create_raid_lobby_embed(self.lobby), view=self)
            except Exception:
                pass

    @discord.ui.button(label="⚡ 레이드 시작", style=discord.ButtonStyle.primary, custom_id="raid_lobby_start")
    async def start_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        if user_id != self.lobby.leader_id:
            await interaction.response.send_message("❌ 로비 리더만 시작할 수 있습니다.", ephemeral=True)
            return
        if self.lobby.started or self.lobby.cancelled:
            await interaction.response.send_message("⚠️ 이미 종료된 로비입니다.", ephemeral=True)
            return
        if not self.lobby.all_ready():
            await interaction.response.send_message("⏳ 모든 파티원이 준비 완료여야 시작할 수 있습니다.", ephemeral=True)
            return

        self.lobby.started = True
        self.lobby.event.set()
        await interaction.response.send_message("🚀 레이드를 시작합니다.", ephemeral=True)

    @discord.ui.button(label="🚪 로비 나가기", style=discord.ButtonStyle.danger, custom_id="raid_lobby_leave")
    async def leave_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        if user_id not in self.lobby.participants:
            await interaction.response.send_message("❌ 로비 참가자가 아닙니다.", ephemeral=True)
            return
        if self.lobby.started:
            await interaction.response.send_message("⚠️ 이미 시작된 로비입니다.", ephemeral=True)
            return

        if user_id == self.lobby.leader_id:
            self.lobby.cancelled = True
            self.lobby.event.set()
            await interaction.response.send_message("🛑 로비를 취소했습니다.", ephemeral=True)
            return

        del self.lobby.participants[user_id]
        await interaction.response.send_message(
            "🚪 로비에서 나갔습니다. (입장권 차감은 복구되지 않습니다.)",
            ephemeral=True,
        )
        if interaction.message:
            try:
                await interaction.message.edit(embed=create_raid_lobby_embed(self.lobby), view=self)
            except Exception:
                pass


class RaidLobbyInviteView(discord.ui.View):
    def __init__(self, lobby: RaidLobbyState, timeout: int | None = None):
        super().__init__(timeout=timeout if timeout is not None else lobby.timeout_seconds)
        self.lobby = lobby

    @discord.ui.button(label="🤝 로비 참가", style=discord.ButtonStyle.primary, custom_id="raid_lobby_join")
    async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id

        if self.lobby.cancelled or self.lobby.started:
            await interaction.response.send_message("⚠️ 이미 종료된 레이드 로비입니다.", ephemeral=True)
            return
        if user_id in self.lobby.participants:
            await interaction.response.send_message("⚠️ 이미 로비에 참가 중입니다.", ephemeral=True)
            return
        if self.lobby.is_full():
            await interaction.response.send_message("❌ 파티 인원이 가득 찼습니다.", ephemeral=True)
            return

        # 같은 음성 채널 검증
        if self.lobby.voice_channel_id is not None:
            voice = getattr(interaction.user, "voice", None)
            channel = getattr(voice, "channel", None)
            if not channel or channel.id != self.lobby.voice_channel_id:
                await interaction.response.send_message("❌ 같은 음성 채널에 있어야 참가할 수 있습니다.", ephemeral=True)
                return

        user = await find_account_by_discordid(user_id)
        if not user:
            await interaction.response.send_message("❌ 등록된 계정이 없습니다. `/등록`을 먼저 해주세요.", ephemeral=True)
            return
        if user.level < self.lobby.required_level:
            await interaction.response.send_message(
                f"❌ 레벨이 부족합니다. (현재 {user.level}, 필요 {self.lobby.required_level})",
                ephemeral=True,
            )
            return

        entry_check = await check_raid_entry(user, self.lobby.raid_id)
        if not entry_check.allowed:
            await interaction.response.send_message("⛔ 이번 주 레이드 입장 횟수를 모두 사용했습니다.", ephemeral=True)
            return

        remaining, max_entries = await consume_raid_entry(user, self.lobby.raid_id)
        self.lobby.participants[user_id] = False
        self.lobby.consumed_entries[user_id] = (remaining, max_entries)

        await interaction.response.send_message(
            f"✅ 로비 참가 완료! (입장권 차감: 남은 {remaining}/{max_entries})\n"
            f"리더가 시작하기 전까지 준비 완료 버튼을 눌러주세요.",
            ephemeral=True,
        )

        try:
            embed = create_raid_lobby_embed(self.lobby)
            await interaction.followup.send(embed=embed, view=RaidLobbyView(self.lobby), ephemeral=True)
        except Exception:
            pass

    @discord.ui.button(label="🚶 거절", style=discord.ButtonStyle.secondary, custom_id="raid_lobby_decline")
    async def decline_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("✅ 초대를 거절했습니다.", ephemeral=True)

