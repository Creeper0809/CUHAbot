"""
멀티유저 만남 이벤트 Discord UI (Phase 3 + 4)

교차로 만남, 캠프파이어, 보스방 대기실 이벤트의 사용자 인터페이스를 제공합니다.
CombatNotificationView 패턴을 따라 multi-user 상호작용을 구현합니다.
"""
import logging
from typing import TYPE_CHECKING, Optional

import discord

from config.social_encounter import SOCIAL_ENCOUNTER

if TYPE_CHECKING:
    from service.dungeon.social_encounter_types import MultiUserEncounterEvent, BossWaitingRoom, RaceState, CrisisEvent
    from service.session import DungeonSession

logger = logging.getLogger(__name__)


class CrossroadsInviteView(discord.ui.View):
    """
    교차로 만남 초대 View

    근처 플레이어와 만남 이벤트 발생 시 양쪽에 전송되는 초대 UI입니다.
    - "찾아가기" 버튼: 만남 수락
    - "지나치기" 버튼: 만남 거절

    패턴: No interaction_check, ephemeral 응답, 이벤트 상태에 응답 저장
    """

    def __init__(self, event: "MultiUserEncounterEvent", timeout: int = 30):
        super().__init__(timeout=timeout)
        self.event = event

    @discord.ui.button(label="👋 찾아가기", style=discord.ButtonStyle.primary, custom_id="crossroads_meet")
    async def meet_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """찾아가기 선택"""
        user_id = interaction.user.id

        # Validation: 참여 자격 확인
        if user_id not in self.event.participant_ids and user_id != self.event.initiator_id:
            await interaction.response.send_message(
                "❌ 이 만남 이벤트에 참여할 수 없습니다.", ephemeral=True
            )
            return

        # 이미 응답한 경우
        if user_id in self.event.responses:
            await interaction.response.send_message(
                "⚠️ 이미 응답하셨습니다.", ephemeral=True
            )
            return

        # 응답 저장
        self.event.responses[user_id] = "meet"
        await interaction.response.send_message(
            "✅ 찾아가기를 선택했습니다. 상대방의 응답을 기다리는 중...", ephemeral=True
        )
        logger.info(f"User {user_id} selected 'meet' for crossroads event")

    @discord.ui.button(label="🚶 지나치기", style=discord.ButtonStyle.secondary, custom_id="crossroads_pass")
    async def pass_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """지나치기 선택"""
        user_id = interaction.user.id

        # Validation: 참여 자격 확인
        if user_id not in self.event.participant_ids and user_id != self.event.initiator_id:
            await interaction.response.send_message(
                "❌ 이 만남 이벤트에 참여할 수 없습니다.", ephemeral=True
            )
            return

        # 이미 응답한 경우
        if user_id in self.event.responses:
            await interaction.response.send_message(
                "⚠️ 이미 응답하셨습니다.", ephemeral=True
            )
            return

        # 응답 저장
        self.event.responses[user_id] = "pass"
        await interaction.response.send_message(
            "✅ 지나치기를 선택했습니다.", ephemeral=True
        )
        logger.info(f"User {user_id} selected 'pass' for crossroads event")


class CrossroadsMeetingView(discord.ui.View):
    """
    교차로 만남 선택지 View

    양쪽이 만남을 수락한 후 나타나는 선택지 UI입니다.
    - "같이 가기": 다음 전투 자동 멀티플레이어 (팀업)
    - "대화하기": 채널 EXP +30 보상
    - "헤어지기": 아무 일 없음
    """

    def __init__(self, event: "MultiUserEncounterEvent", timeout: int = 30):
        super().__init__(timeout=timeout)
        self.event = event

    @discord.ui.button(label="🤝 같이 가기", style=discord.ButtonStyle.primary, custom_id="meeting_team_up")
    async def team_up_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """같이 가기 선택 (다음 전투 자동 합류)"""
        user_id = interaction.user.id

        if user_id not in self.event.participant_ids and user_id != self.event.initiator_id:
            await interaction.response.send_message(
                "❌ 이 만남에 참여할 수 없습니다.", ephemeral=True
            )
            return

        if user_id in self.event.responses:
            await interaction.response.send_message(
                "⚠️ 이미 선택하셨습니다.", ephemeral=True
            )
            return

        self.event.responses[user_id] = "team_up"
        await interaction.response.send_message(
            "✅ 같이 가기를 선택했습니다. 다음 전투에서 만날 것입니다!", ephemeral=True
        )
        logger.info(f"User {user_id} selected 'team_up' for crossroads meeting")

    @discord.ui.button(label="💬 대화하기", style=discord.ButtonStyle.secondary, custom_id="meeting_chat")
    async def chat_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """대화하기 선택 (채널 EXP +30)"""
        user_id = interaction.user.id

        if user_id not in self.event.participant_ids and user_id != self.event.initiator_id:
            await interaction.response.send_message(
                "❌ 이 만남에 참여할 수 없습니다.", ephemeral=True
            )
            return

        if user_id in self.event.responses:
            await interaction.response.send_message(
                "⚠️ 이미 선택하셨습니다.", ephemeral=True
            )
            return

        self.event.responses[user_id] = "chat"
        await interaction.response.send_message(
            f"✅ 대화하기를 선택했습니다. (채널 EXP +{SOCIAL_ENCOUNTER.CROSSROADS_EXP_REWARD})",
            ephemeral=True
        )
        logger.info(f"User {user_id} selected 'chat' for crossroads meeting")

    @discord.ui.button(label="👋 헤어지기", style=discord.ButtonStyle.danger, custom_id="meeting_leave")
    async def leave_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """헤어지기 선택"""
        user_id = interaction.user.id

        if user_id not in self.event.participant_ids and user_id != self.event.initiator_id:
            await interaction.response.send_message(
                "❌ 이 만남에 참여할 수 없습니다.", ephemeral=True
            )
            return

        if user_id in self.event.responses:
            await interaction.response.send_message(
                "⚠️ 이미 선택하셨습니다.", ephemeral=True
            )
            return

        self.event.responses[user_id] = "leave"
        await interaction.response.send_message(
            "✅ 헤어지기를 선택했습니다. 각자의 길을 가십니다.", ephemeral=True
        )
        logger.info(f"User {user_id} selected 'leave' for crossroads meeting")


class CampfireJoinView(discord.ui.View):
    """
    캠프파이어 참여 View

    캠프파이어 발견 시 근처 플레이어들에게 전송되는 참여 초대 UI입니다.
    - "합류" 버튼: 캠프파이어 참여
    - "지나치기" 버튼: 참여 거절
    """

    def __init__(self, event: "MultiUserEncounterEvent", timeout: int = 60):
        super().__init__(timeout=timeout)
        self.event = event

    @discord.ui.button(label="🔥 합류", style=discord.ButtonStyle.primary, custom_id="campfire_join")
    async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """합류 선택"""
        user_id = interaction.user.id

        # Validation
        if user_id not in self.event.participant_ids and user_id != self.event.initiator_id:
            await interaction.response.send_message(
                "❌ 이 캠프파이어에 참여할 수 없습니다.", ephemeral=True
            )
            return

        if user_id in self.event.responses:
            await interaction.response.send_message(
                "⚠️ 이미 응답하셨습니다.", ephemeral=True
            )
            return

        # 응답 저장
        self.event.responses[user_id] = "join"
        await interaction.response.send_message(
            "✅ 캠프파이어에 합류했습니다. 따뜻한 휴식을 취하고 있습니다...", ephemeral=True
        )
        logger.info(f"User {user_id} joined campfire event")

    @discord.ui.button(label="🚶 지나치기", style=discord.ButtonStyle.secondary, custom_id="campfire_pass")
    async def pass_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """지나치기 선택"""
        user_id = interaction.user.id

        # Validation
        if user_id not in self.event.participant_ids and user_id != self.event.initiator_id:
            await interaction.response.send_message(
                "❌ 이 캠프파이어에 참여할 수 없습니다.", ephemeral=True
            )
            return

        if user_id in self.event.responses:
            await interaction.response.send_message(
                "⚠️ 이미 응답하셨습니다.", ephemeral=True
            )
            return

        # 응답 저장
        self.event.responses[user_id] = "pass"
        await interaction.response.send_message(
            "✅ 지나치기를 선택했습니다.", ephemeral=True
        )
        logger.info(f"User {user_id} passed campfire event")


class CampfireMenuView(discord.ui.View):
    """
    캠프파이어 메뉴 View

    캠프파이어 참여 후 나타나는 상호작용 메뉴입니다.
    - "정보 교환": 플레이어 정보 조회
    - "파티 신청": 파티 초대 (향후 확장)
    - "떠나기": 캠프파이어 종료 및 탐험 재개
    """

    def __init__(self, event: "MultiUserEncounterEvent", timeout: int = 300):
        super().__init__(timeout=timeout)
        self.event = event

    @discord.ui.button(label="📊 정보 교환", style=discord.ButtonStyle.primary, custom_id="campfire_info")
    async def info_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """정보 교환 (플레이어 정보 보기)"""
        user_id = interaction.user.id

        if user_id not in self.event.participant_ids and user_id != self.event.initiator_id:
            await interaction.response.send_message(
                "❌ 이 캠프파이어에 참여하지 않았습니다.", ephemeral=True
            )
            return

        # TODO: 실제 플레이어 정보 조회 로직
        await interaction.response.send_message(
            "📊 **캠프파이어 참여자 정보**\n\n"
            "플레이어 정보 기능은 향후 구현 예정입니다.",
            ephemeral=True
        )
        logger.info(f"User {user_id} requested info at campfire")

    @discord.ui.button(label="🤝 파티 신청", style=discord.ButtonStyle.secondary, custom_id="campfire_party")
    async def party_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """파티 신청 (향후 확장)"""
        user_id = interaction.user.id

        if user_id not in self.event.participant_ids and user_id != self.event.initiator_id:
            await interaction.response.send_message(
                "❌ 이 캠프파이어에 참여하지 않았습니다.", ephemeral=True
            )
            return

        await interaction.response.send_message(
            "🤝 파티 시스템은 향후 추가 예정입니다.", ephemeral=True
        )
        logger.info(f"User {user_id} attempted party request at campfire")

    @discord.ui.button(label="🚪 떠나기", style=discord.ButtonStyle.danger, custom_id="campfire_leave")
    async def leave_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """떠나기 (탐험 재개)"""
        user_id = interaction.user.id

        if user_id not in self.event.participant_ids and user_id != self.event.initiator_id:
            await interaction.response.send_message(
                "❌ 이 캠프파이어에 참여하지 않았습니다.", ephemeral=True
            )
            return

        # 응답 저장 (떠나기 선택)
        self.event.responses[user_id] = "leave"
        await interaction.response.send_message(
            "✅ 캠프파이어를 떠났습니다. 탐험을 재개합니다.", ephemeral=True
        )
        logger.info(f"User {user_id} left campfire")


# ============================================================
# Phase 4: 보스방 대기실 Views
# ============================================================


class BossWaitingRoomInviteView(discord.ui.View):
    """
    보스방 초대 View (Phase 4)

    근처 플레이어에게 보스방 참여 초대를 보냅니다.
    - "입장" 버튼: 보스방 참여
    - "지나치기" 버튼: 참여 거절
    """

    def __init__(self, waiting_room: "BossWaitingRoom", timeout: int = 60):
        super().__init__(timeout=timeout)
        self.waiting_room = waiting_room

    @discord.ui.button(label="👑 입장", style=discord.ButtonStyle.primary, custom_id="boss_room_join")
    async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """입장 선택"""
        user_id = interaction.user.id

        # Validation: 이미 참여 중
        if user_id in self.waiting_room.participants:
            await interaction.response.send_message(
                "⚠️ 이미 보스방에 참여했습니다.", ephemeral=True
            )
            return

        # Validation: 최대 인원
        if self.waiting_room.is_full():
            await interaction.response.send_message(
                "❌ 보스방이 가득 찼습니다.", ephemeral=True
            )
            return

        # Validation: 이미 시작됨
        if self.waiting_room.started or self.waiting_room.cancelled:
            await interaction.response.send_message(
                "❌ 보스방이 이미 시작되었거나 취소되었습니다.", ephemeral=True
            )
            return

        # 참여 추가 (미준비 상태)
        self.waiting_room.participants[user_id] = False

        await interaction.response.send_message(
            f"✅ 보스방에 입장했습니다! ({self.waiting_room.get_participant_count()}/{self.waiting_room.max_participants}명)\n"
            "대기실 UI가 곧 전송됩니다.",
            ephemeral=True,
        )
        logger.info(f"User {user_id} joined boss waiting room")

        # 대기실 UI 전송
        try:
            embed = discord.Embed(
                title=f"👑 보스방 대기실: {self.waiting_room.boss_monster.name}",
                description=(
                    f"**{self.waiting_room.boss_monster.name}** 보스전에 참여했습니다.\n\n"
                    f"참여 인원: {self.waiting_room.get_participant_count()}/{self.waiting_room.max_participants}\n"
                    "준비가 되면 \"준비 완료\" 버튼을 눌러주세요."
                ),
                color=discord.Color.red(),
            )

            view = BossWaitingRoomView(self.waiting_room, timeout=self.waiting_room.timeout_seconds)
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)

        except Exception as e:
            logger.error(f"Failed to send boss waiting room UI to {user_id}: {e}", exc_info=True)

    @discord.ui.button(label="🚶 지나치기", style=discord.ButtonStyle.secondary, custom_id="boss_room_pass")
    async def pass_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """지나치기 선택"""
        await interaction.response.send_message(
            "✅ 보스방을 지나쳤습니다.", ephemeral=True
        )
        logger.info(f"User {interaction.user.id} declined boss room invite")


class BossWaitingRoomView(discord.ui.View):
    """
    보스방 대기실 View (Phase 4)

    보스방 참여 후 나타나는 대기실 UI입니다.
    - "준비 완료" 버튼: 전투 준비 완료 표시
    - "혼자 도전" 버튼: 현재 인원으로 즉시 시작 (리더 전용)
    - "나가기" 버튼: 대기실 퇴장
    """

    def __init__(self, waiting_room: "BossWaitingRoom", timeout: int = 60):
        super().__init__(timeout=timeout)
        self.waiting_room = waiting_room

    @discord.ui.button(label="✅ 준비 완료", style=discord.ButtonStyle.success, custom_id="boss_room_ready")
    async def ready_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """준비 완료"""
        user_id = interaction.user.id

        # Validation: 참여자 확인
        if user_id not in self.waiting_room.participants:
            await interaction.response.send_message(
                "❌ 보스방에 참여하지 않았습니다.", ephemeral=True
            )
            return

        # Validation: 이미 준비 완료
        if self.waiting_room.participants[user_id]:
            await interaction.response.send_message(
                "⚠️ 이미 준비 완료 상태입니다.", ephemeral=True
            )
            return

        # 준비 완료 표시
        self.waiting_room.participants[user_id] = True

        ready_count = sum(1 for ready in self.waiting_room.participants.values() if ready)
        total_count = self.waiting_room.get_participant_count()

        await interaction.response.send_message(
            f"✅ 준비 완료! ({ready_count}/{total_count}명 준비)\n"
            + ("전원 준비 완료! 곧 전투가 시작됩니다." if self.waiting_room.all_ready() else "다른 플레이어를 기다리는 중..."),
            ephemeral=True,
        )
        logger.info(f"User {user_id} ready in boss waiting room ({ready_count}/{total_count})")

    @discord.ui.button(label="⚡ 혼자 도전", style=discord.ButtonStyle.primary, custom_id="boss_room_solo")
    async def solo_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """혼자 도전 (리더 전용, 즉시 시작)"""
        user_id = interaction.user.id

        # Validation: 리더만 가능
        if user_id != self.waiting_room.initiator_id:
            await interaction.response.send_message(
                "❌ 보스방 생성자만 이 버튼을 사용할 수 있습니다.", ephemeral=True
            )
            return

        # 즉시 시작 플래그 설정
        self.waiting_room.started = True

        await interaction.response.send_message(
            "⚡ 현재 인원으로 보스전을 시작합니다!", ephemeral=True
        )
        logger.info(f"Boss waiting room force started by {user_id}")

    @discord.ui.button(label="🚪 나가기", style=discord.ButtonStyle.danger, custom_id="boss_room_leave")
    async def leave_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """나가기 (대기실 퇴장)"""
        user_id = interaction.user.id

        # Validation: 참여자 확인
        if user_id not in self.waiting_room.participants:
            await interaction.response.send_message(
                "❌ 보스방에 참여하지 않았습니다.", ephemeral=True
            )
            return

        # 참여자 제거
        del self.waiting_room.participants[user_id]

        # 리더가 나가면 대기실 취소
        if user_id == self.waiting_room.initiator_id:
            self.waiting_room.cancelled = True
            await interaction.response.send_message(
                "⚠️ 보스방을 나갔습니다. 대기실이 취소됩니다.", ephemeral=True
            )
            logger.info(f"Boss waiting room cancelled by initiator {user_id}")
        else:
            await interaction.response.send_message(
                f"✅ 보스방을 나갔습니다. (남은 인원: {self.waiting_room.get_participant_count()}명)", ephemeral=True
            )
            logger.info(f"User {user_id} left boss waiting room")


# ============================================================
# Phase 4: 동시 조우 Views
# ============================================================


class SimultaneousEncounterChoiceView(discord.ui.View):
    """
    동시 조우 선택 View (Phase 4)

    같은 스텝에서 전투 시작 시 협력/경쟁/독립 선택지를 제공합니다.
    - "협력" 버튼: 양쪽이 협력 선택 시 함께 싸우기 (보상 +20%)
    - "경쟁" 버튼: 한 명이라도 경쟁 선택 시 먼저 처치하기 (승자 150%, 패자 50%)
    - "독립" 버튼: 각자 진행 (정상 보상)
    """

    def __init__(self, user_id: int, responses: dict, timeout: int = 30):
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.responses = responses

    @discord.ui.button(label="🤝 협력", style=discord.ButtonStyle.success, custom_id="simultaneous_cooperate")
    async def cooperate_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """협력 선택"""
        user_id = interaction.user.id

        # Validation
        if user_id != self.user_id:
            await interaction.response.send_message(
                "❌ 이 선택지는 당신의 것이 아닙니다.", ephemeral=True
            )
            return

        if user_id in self.responses:
            await interaction.response.send_message(
                "⚠️ 이미 선택하셨습니다.", ephemeral=True
            )
            return

        # 응답 저장
        self.responses[user_id] = "cooperate"

        await interaction.response.send_message(
            "✅ 협력을 선택했습니다! 상대방의 응답을 기다리는 중...\n"
            "(양쪽이 협력 선택 시 함께 싸우며 보상 +20%)",
            ephemeral=True,
        )
        logger.info(f"User {user_id} selected cooperate in simultaneous encounter")

    @discord.ui.button(label="⚔️ 경쟁", style=discord.ButtonStyle.danger, custom_id="simultaneous_compete")
    async def compete_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """경쟁 선택"""
        user_id = interaction.user.id

        # Validation
        if user_id != self.user_id:
            await interaction.response.send_message(
                "❌ 이 선택지는 당신의 것이 아닙니다.", ephemeral=True
            )
            return

        if user_id in self.responses:
            await interaction.response.send_message(
                "⚠️ 이미 선택하셨습니다.", ephemeral=True
            )
            return

        # 응답 저장
        self.responses[user_id] = "compete"

        await interaction.response.send_message(
            "✅ 경쟁을 선택했습니다! 상대방의 응답을 기다리는 중...\n"
            "(한 명이라도 경쟁 선택 시 레이스 모드, 승자 150% / 패자 50%)",
            ephemeral=True,
        )
        logger.info(f"User {user_id} selected compete in simultaneous encounter")

    @discord.ui.button(label="🚶 독립", style=discord.ButtonStyle.secondary, custom_id="simultaneous_pass")
    async def pass_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """독립 선택"""
        user_id = interaction.user.id

        # Validation
        if user_id != self.user_id:
            await interaction.response.send_message(
                "❌ 이 선택지는 당신의 것이 아닙니다.", ephemeral=True
            )
            return

        if user_id in self.responses:
            await interaction.response.send_message(
                "⚠️ 이미 선택하셨습니다.", ephemeral=True
            )
            return

        # 응답 저장
        self.responses[user_id] = "pass"

        await interaction.response.send_message(
            "✅ 독립을 선택했습니다. 각자의 길을 가십니다. (정상 보상)",
            ephemeral=True,
        )
        logger.info(f"User {user_id} selected pass in simultaneous encounter")


# ============================================================
# Phase 4: 위기 목격 View
# ============================================================


class CrisisWitnessView(discord.ui.View):
    """
    위기 목격 View (Phase 4)

    근처 플레이어의 HP가 30% 미만일 때 구조/응원 옵션을 제공합니다.
    - "달려가기" 버튼: 난입하여 도움 (보상 +30%)
    - "응원하기" 버튼: 원거리 응원 (ATK +5, 1턴)
    - "지나치기" 버튼: 무시하고 계속 탐험
    """

    def __init__(self, crisis_event: "CrisisEvent", victim_session: "DungeonSession", timeout: int = 30):
        super().__init__(timeout=timeout)
        self.crisis_event = crisis_event
        self.victim_session = victim_session

    @discord.ui.button(label="🏃 달려가기", style=discord.ButtonStyle.danger, custom_id="crisis_intervene")
    async def intervene_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """달려가기 (난입)"""
        user_id = interaction.user.id

        # 이미 응답함
        if user_id in self.crisis_event.responders:
            await interaction.response.send_message(
                "⚠️ 이미 응답하셨습니다.", ephemeral=True
            )
            return

        # 응답 저장
        self.crisis_event.responders[user_id] = "intervene"

        # 난입 처리
        from service.intervention.intervention_service import InterventionService
        from service.session import get_session

        try:
            # 난입 요청
            requester_session = get_session(user_id)
            if not requester_session:
                await interaction.response.send_message(
                    "❌ 세션을 찾을 수 없습니다. 먼저 던전을 시작해주세요.", ephemeral=True
                )
                return

            # 위기 구조 보너스 설정 (+30%)
            self.victim_session.explore_buffs["crisis_rescue_bonus"] = {
                "rescuer_id": user_id,
                "bonus": SOCIAL_ENCOUNTER.CRISIS_RESCUE_REWARD_BONUS,
            }

            await InterventionService.request_intervention(
                requester_id=user_id,
                target_user_id=self.victim_session.user_id,
                interaction=interaction,
            )

            await interaction.response.send_message(
                f"✅ {self.victim_session.user.get_name()}을(를) 도우러 갑니다! (보상 +30%)",
                ephemeral=True,
            )
            logger.info(f"User {user_id} intervened for crisis victim {self.victim_session.user_id}")

        except Exception as e:
            logger.error(f"Crisis intervention failed: {e}", exc_info=True)
            await interaction.response.send_message(
                f"❌ 난입 실패: {e}", ephemeral=True
            )

    @discord.ui.button(label="📣 응원하기", style=discord.ButtonStyle.primary, custom_id="crisis_cheer")
    async def cheer_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """응원하기 (원거리 버프)"""
        user_id = interaction.user.id

        # 이미 응답함
        if user_id in self.crisis_event.responders:
            await interaction.response.send_message(
                "⚠️ 이미 응답하셨습니다.", ephemeral=True
            )
            return

        # 응답 저장
        self.crisis_event.responders[user_id] = "cheer"

        # 피해자에게 ATK +5 버프 적용 (1턴)
        victim_user = self.victim_session.user
        victim_user.attack += SOCIAL_ENCOUNTER.CRISIS_CHEER_ATTACK_BONUS

        await interaction.response.send_message(
            f"✅ {victim_user.get_name()}을(를) 응원했습니다!\n"
            f"(ATK +{SOCIAL_ENCOUNTER.CRISIS_CHEER_ATTACK_BONUS}, 1턴)",
            ephemeral=True,
        )
        logger.info(f"User {user_id} cheered for crisis victim {self.victim_session.user_id}")

        # 피해자에게 알림 (옵션)
        try:
            from service.session import get_session
            cheerer_session = get_session(user_id)
            if cheerer_session:
                # 전투 로그에 추가 (옵션)
                pass

        except Exception as e:
            logger.error(f"Failed to notify victim about cheer: {e}")

    @discord.ui.button(label="🚶 지나치기", style=discord.ButtonStyle.secondary, custom_id="crisis_pass")
    async def pass_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """지나치기"""
        user_id = interaction.user.id

        # 이미 응답함
        if user_id in self.crisis_event.responders:
            await interaction.response.send_message(
                "⚠️ 이미 응답하셨습니다.", ephemeral=True
            )
            return

        # 응답 저장
        self.crisis_event.responders[user_id] = "pass"

        await interaction.response.send_message(
            "✅ 지나쳤습니다. 각자의 길을 가십니다.",
            ephemeral=True,
        )
        logger.info(f"User {user_id} passed crisis event")
