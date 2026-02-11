"""
멀티유저 만남 이벤트 타입 정의 (Phase 3 + 4)

교차로 만남, 캠프파이어, 보스방 대기실, 동시 조우, 위기 목격 이벤트를 구현합니다.
"""
import asyncio
import logging
import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

import discord

from config.social_encounter import SOCIAL_ENCOUNTER
from exceptions import NoEligiblePartnersError, EncounterTimeoutError
from service.dungeon.encounter_types import Encounter, EncounterType, EncounterResult
from service.session import SessionType, get_session, get_sessions_in_voice_channel
from service.voice_channel.proximity_calculator import ProximityCalculator

if TYPE_CHECKING:
    from service.session import DungeonSession
    from models import Monster

logger = logging.getLogger(__name__)


@dataclass
class MultiUserEncounterEvent:
    """
    멀티유저 encounter 이벤트 상태 추적

    교차로 만남과 캠프파이어 등 여러 플레이어가 참여하는
    이벤트의 상태를 추적합니다.
    """

    event_type: str
    """이벤트 타입: "crossroads" 또는 "campfire" """

    initiator_id: int
    """이벤트 발생 시작자 user_id"""

    participant_ids: set[int] = field(default_factory=set)
    """참여 가능한 플레이어 user_id 집합"""

    responses: dict[int, str] = field(default_factory=dict)
    """user_id → 선택한 응답 매핑"""

    created_at: float = field(default_factory=lambda: asyncio.get_event_loop().time())
    """이벤트 생성 시간"""

    timeout_seconds: float = 30.0
    """타임아웃 시간 (초)"""

    resolved: bool = False
    """이벤트 종료 여부"""

    def is_timeout(self) -> bool:
        """타임아웃 체크"""
        elapsed = asyncio.get_event_loop().time() - self.created_at
        return elapsed >= self.timeout_seconds

    def mark_resolved(self) -> None:
        """이벤트 종료 표시"""
        self.resolved = True


class CrossroadsEncounter(Encounter):
    """
    교차로 만남 Encounter

    근처 플레이어(±2 스텝)와 우연히 만나는 이벤트입니다.
    양쪽이 "찾아가기"를 선택하면 만남이 성립되며,
    이후 "같이 가기", "대화하기", "헤어지기" 중 선택할 수 있습니다.
    """

    encounter_type = EncounterType.EVENT

    async def execute(
        self, session: "DungeonSession", interaction: discord.Interaction
    ) -> Optional[EncounterResult]:
        """교차로 만남 실행"""
        from service.dungeon.social_encounter_checker import get_nearby_sessions
        from views.social_encounter_view import CrossroadsInviteView, CrossroadsMeetingView

        # 1. 근처 세션 찾기 (±2 스텝)
        other_sessions = get_sessions_in_voice_channel(session.voice_channel_id)
        eligible = [
            s for s in other_sessions
            if s.user_id != session.user_id
            and s.dungeon
            and s.dungeon.id == session.dungeon.id
            and not s.in_combat
            and not s.ended
        ]

        nearby = get_nearby_sessions(session, eligible, SOCIAL_ENCOUNTER.CROSSROADS_DISTANCE_THRESHOLD)
        if not nearby:
            logger.warning(f"Crossroads triggered but no nearby players for user {session.user_id}")
            raise NoEligiblePartnersError()

        # 2. 파트너 선정 (1명만)
        partner_session = random.choice(nearby)

        # 3. 이벤트 생성
        event = MultiUserEncounterEvent(
            event_type="crossroads",
            initiator_id=session.user_id,
            participant_ids={partner_session.user_id},
            timeout_seconds=SOCIAL_ENCOUNTER.CROSSROADS_TIMEOUT,
        )
        session.active_encounter_event = event
        partner_session.active_encounter_event = event

        # 4. 양쪽에 초대 DM 전송
        try:
            initiator_user = await interaction.client.fetch_user(session.user_id)
            partner_user = await interaction.client.fetch_user(partner_session.user_id)

            embed = discord.Embed(
                title="🚶 기척이 들린다...",
                description=(
                    f"근처에서 {partner_user.display_name if session.user_id == interaction.user.id else initiator_user.display_name}님의 기척이 들립니다.\n"
                    f"찾아가시겠습니까?"
                ),
                color=discord.Color.blue(),
            )

            view1 = CrossroadsInviteView(event, timeout=SOCIAL_ENCOUNTER.CROSSROADS_TIMEOUT)
            view2 = CrossroadsInviteView(event, timeout=SOCIAL_ENCOUNTER.CROSSROADS_TIMEOUT)

            msg1 = await initiator_user.send(embed=embed, view=view1)
            msg2 = await partner_user.send(embed=embed, view=view2)

        except discord.Forbidden:
            logger.warning(f"Failed to send crossroads invite DM")
            session.active_encounter_event = None
            partner_session.active_encounter_event = None
            return EncounterResult(
                encounter_type=EncounterType.EVENT,
                message="근처에서 기척이 들렸지만... 아무도 없는 것 같다.",
            )

        # 5. 응답 대기
        try:
            await asyncio.wait_for(
                self._wait_for_responses(event, [session.user_id, partner_session.user_id]),
                timeout=SOCIAL_ENCOUNTER.CROSSROADS_TIMEOUT,
            )
        except asyncio.TimeoutError:
            logger.info(f"Crossroads invite timeout for {session.user_id}")
            session.active_encounter_event = None
            partner_session.active_encounter_event = None
            return EncounterResult(
                encounter_type=EncounterType.EVENT,
                message="기척이 점점 멀어진다...",
            )

        # 6. 응답 처리
        initiator_choice = event.responses.get(session.user_id)
        partner_choice = event.responses.get(partner_session.user_id)

        if initiator_choice == "meet" and partner_choice == "meet":
            # 만남 성립 → 추가 선택지
            return await self._handle_meeting(event, session, partner_session, interaction)
        else:
            # 만남 불발
            session.active_encounter_event = None
            partner_session.active_encounter_event = None
            return EncounterResult(
                encounter_type=EncounterType.EVENT,
                message="아쉽게도 만남이 성사되지 않았다.",
            )

    async def _wait_for_responses(self, event: MultiUserEncounterEvent, user_ids: list[int]) -> None:
        """모든 플레이어의 응답 대기"""
        while not event.is_timeout():
            if all(uid in event.responses for uid in user_ids):
                return
            await asyncio.sleep(0.5)

        raise asyncio.TimeoutError()

    async def _handle_meeting(
        self,
        event: MultiUserEncounterEvent,
        session: "DungeonSession",
        partner_session: "DungeonSession",
        interaction: discord.Interaction,
    ) -> EncounterResult:
        """만남 성립 후 추가 선택지 처리"""
        from views.social_encounter_view import CrossroadsMeetingView

        # 응답 초기화
        event.responses.clear()
        event.timeout_seconds = SOCIAL_ENCOUNTER.CROSSROADS_MEETING_TIMEOUT

        try:
            initiator_user = await interaction.client.fetch_user(session.user_id)
            partner_user = await interaction.client.fetch_user(partner_session.user_id)

            embed = discord.Embed(
                title="🤝 만남이 성사되었습니다!",
                description=(
                    f"{initiator_user.display_name}님과 {partner_user.display_name}님이 만났습니다.\n\n"
                    "- **같이 가기**: 다음 전투에서 자동으로 함께 싸웁니다\n"
                    "- **대화하기**: 채널 EXP +30\n"
                    "- **헤어지기**: 각자의 길을 갑니다"
                ),
                color=discord.Color.green(),
            )

            view1 = CrossroadsMeetingView(event, timeout=SOCIAL_ENCOUNTER.CROSSROADS_MEETING_TIMEOUT)
            view2 = CrossroadsMeetingView(event, timeout=SOCIAL_ENCOUNTER.CROSSROADS_MEETING_TIMEOUT)

            await initiator_user.send(embed=embed, view=view1)
            await partner_user.send(embed=embed, view=view2)

        except discord.Forbidden:
            logger.warning(f"Failed to send meeting choice DM")
            session.active_encounter_event = None
            partner_session.active_encounter_event = None
            return EncounterResult(
                encounter_type=EncounterType.EVENT,
                message="만남은 성사되었지만, 무슨 일인지 대화가 이루어지지 않았다.",
            )

        # 선택 대기
        try:
            await asyncio.wait_for(
                self._wait_for_responses(event, [session.user_id, partner_session.user_id]),
                timeout=SOCIAL_ENCOUNTER.CROSSROADS_MEETING_TIMEOUT,
            )
        except asyncio.TimeoutError:
            logger.info(f"Crossroads meeting timeout")
            session.active_encounter_event = None
            partner_session.active_encounter_event = None
            return EncounterResult(
                encounter_type=EncounterType.EVENT,
                message="오랜 침묵 끝에 각자의 길을 갔다.",
            )

        # 최종 선택 처리
        initiator_choice = event.responses.get(session.user_id)
        partner_choice = event.responses.get(partner_session.user_id)

        session.active_encounter_event = None
        partner_session.active_encounter_event = None
        event.mark_resolved()

        # "같이 가기" 선택 시 팀업 버프 저장
        if "team_up" in [initiator_choice, partner_choice]:
            session.explore_buffs["team_up_partner"] = partner_session.user_id
            partner_session.explore_buffs["team_up_partner"] = session.user_id
            return EncounterResult(
                encounter_type=EncounterType.EVENT,
                message=f"🤝 {partner_user.display_name}님과 함께 가기로 했다! 다음 전투에서 만날 것이다.",
            )

        # "대화하기" 선택 시 채널 EXP 보상
        if "chat" in [initiator_choice, partner_choice]:
            # TODO: 채널 EXP 시스템 구현 시 적용
            return EncounterResult(
                encounter_type=EncounterType.EVENT,
                message=f"💬 {partner_user.display_name}님과 유쾌한 대화를 나눴다. (채널 EXP +{SOCIAL_ENCOUNTER.CROSSROADS_EXP_REWARD})",
            )

        # "헤어지기" 또는 선택 불일치
        return EncounterResult(
            encounter_type=EncounterType.EVENT,
            message="👋 서로 인사를 나누고 각자의 길을 갔다.",
        )


class CampfireEncounter(Encounter):
    """
    캠프파이어 Encounter

    던전 내에서 캠프파이어를 발견하는 이벤트입니다.
    근처 플레이어들에게 알림을 보내고, 60초간 대기한 후
    참여 인원에 따라 HP 회복 및 ATK 버프를 제공합니다.
    """

    encounter_type = EncounterType.EVENT

    async def execute(
        self, session: "DungeonSession", interaction: discord.Interaction
    ) -> Optional[EncounterResult]:
        """캠프파이어 실행"""
        from service.notification.notification_service import NotificationService
        from views.social_encounter_view import CampfireJoinView, CampfireMenuView

        # 1. 캠프파이어 발견 알림
        embed = discord.Embed(
            title="🔥 캠프파이어를 발견했다!",
            description=(
                "던전 안에 누군가가 피워둔 캠프파이어가 있습니다.\n"
                "근처 플레이어들에게 알림을 보내는 중...\n\n"
                f"**60초 동안 대기합니다.**\n"
                "참여 인원에 따라 효과가 달라집니다:\n"
                "- 1명: HP +30%\n"
                "- 2명: HP +40%, ATK +10% (1전투)\n"
                "- 3+명: HP +50%, ATK +10% (2전투)"
            ),
            color=discord.Color.orange(),
        )

        await interaction.followup.send(embed=embed, ephemeral=True)

        # 2. 이벤트 생성
        event = MultiUserEncounterEvent(
            event_type="campfire",
            initiator_id=session.user_id,
            timeout_seconds=SOCIAL_ENCOUNTER.CAMPFIRE_TIMEOUT,
        )
        session.active_encounter_event = event
        session.status = SessionType.REST

        # 발견자는 자동 참여
        event.responses[session.user_id] = "join"

        # 3. 근처 플레이어 찾기
        other_sessions = get_sessions_in_voice_channel(session.voice_channel_id)
        eligible = [
            s for s in other_sessions
            if s.user_id != session.user_id
            and s.dungeon
            and s.dungeon.id == session.dungeon.id
            and not s.in_combat
            and not s.ended
        ]

        if eligible:
            event.participant_ids = {s.user_id for s in eligible}

            # 4. 거리별 초대 전송 (0초/5초 지연)
            for other_session in eligible:
                distance = ProximityCalculator.calculate_distance(
                    session.exploration_step, other_session.exploration_step
                )

                # 거리 체크
                if distance > SOCIAL_ENCOUNTER.CAMPFIRE_DISTANCE_THRESHOLD:
                    continue  # 너무 멀면 알림 안 보냄

                delay = 0 if distance <= 3 else 5

                asyncio.create_task(
                    self._send_campfire_invite(
                        interaction.client, other_session.user_id, event, delay
                    )
                )

        # 5. 60초 대기
        await asyncio.sleep(SOCIAL_ENCOUNTER.CAMPFIRE_TIMEOUT)

        # 6. 참여자 집계
        participants = [session]
        for other_session in eligible:
            if event.responses.get(other_session.user_id) == "join":
                participants.append(other_session)
                other_session.active_encounter_event = event
                other_session.status = SessionType.REST

        participant_count = len(participants)

        # 7. HP 회복 적용
        heal_pct = self._get_heal_percent(participant_count)
        for participant_session in participants:
            user = participant_session.user
            heal_amount = int(user.max_hp * heal_pct)
            user.now_hp = min(user.max_hp, user.now_hp + heal_amount)
            await user.save()

        # 8. ATK 버프 적용 (2+명)
        if participant_count >= 2:
            buff_combats = (
                SOCIAL_ENCOUNTER.CAMPFIRE_BUFF_COMBATS_2P
                if participant_count == 2
                else SOCIAL_ENCOUNTER.CAMPFIRE_BUFF_COMBATS_3P
            )

            for participant_session in participants:
                participant_session.explore_buffs["campfire_atk_bonus"] = {
                    "percent": SOCIAL_ENCOUNTER.CAMPFIRE_BUFF_ATTACK_PCT,
                    "remaining_combats": buff_combats,
                }

        # 9. 캠프파이어 메뉴 제공
        for participant_session in participants:
            try:
                user = await interaction.client.fetch_user(participant_session.user_id)
                menu_view = CampfireMenuView(event, timeout=300)

                result_embed = discord.Embed(
                    title="🔥 캠프파이어에서 휴식을 취했습니다",
                    description=(
                        f"**참여 인원**: {participant_count}명\n"
                        f"**HP 회복**: +{int(heal_pct * 100)}%\n"
                        + (
                            f"**ATK 버프**: +{int(SOCIAL_ENCOUNTER.CAMPFIRE_BUFF_ATTACK_PCT * 100)}% "
                            f"({buff_combats}전투)\n"
                            if participant_count >= 2
                            else ""
                        )
                        + "\n캠프파이어 메뉴:"
                    ),
                    color=discord.Color.green(),
                )

                await user.send(embed=result_embed, view=menu_view)
            except discord.Forbidden:
                logger.warning(f"Failed to send campfire result to {participant_session.user_id}")

        # 10. 이벤트 종료
        for participant_session in participants:
            participant_session.active_encounter_event = None
            participant_session.status = SessionType.IDLE

        event.mark_resolved()

        return EncounterResult(
            encounter_type=EncounterType.EVENT,
            message=f"🔥 캠프파이어에서 {participant_count}명이 함께 휴식을 취했다.",
            healing_received=int(session.user.max_hp * heal_pct),
        )

    async def _send_campfire_invite(
        self, client: discord.Client, user_id: int, event: MultiUserEncounterEvent, delay: int
    ) -> None:
        """캠프파이어 초대 DM 전송 (지연 가능)"""
        if delay > 0:
            await asyncio.sleep(delay)

        try:
            user = await client.fetch_user(user_id)
            embed = discord.Embed(
                title="🔥 근처에 캠프파이어가 있습니다!",
                description=(
                    "누군가가 캠프파이어를 발견했습니다.\n"
                    "합류하시겠습니까?\n\n"
                    "참여 인원에 따라 효과가 달라집니다."
                ),
                color=discord.Color.orange(),
            )

            view = CampfireJoinView(event, timeout=SOCIAL_ENCOUNTER.CAMPFIRE_TIMEOUT)
            await user.send(embed=embed, view=view)
            logger.info(f"Sent campfire invite to {user_id} with {delay}s delay")

        except discord.Forbidden:
            logger.warning(f"Failed to send campfire invite to {user_id}")
        except Exception as e:
            logger.error(f"Error sending campfire invite to {user_id}: {e}", exc_info=True)

    def _get_heal_percent(self, participant_count: int) -> float:
        """참여 인원에 따른 HP 회복 비율"""
        if participant_count >= 3:
            return SOCIAL_ENCOUNTER.CAMPFIRE_HEAL_3P
        elif participant_count == 2:
            return SOCIAL_ENCOUNTER.CAMPFIRE_HEAL_2P
        else:
            return SOCIAL_ENCOUNTER.CAMPFIRE_HEAL_1P


# ============================================================
# Phase 4: 보스방 대기실 (Boss Waiting Room)
# ============================================================


@dataclass
class BossWaitingRoom:
    """
    보스방 대기실 상태 추적 (Phase 4)

    보스 스폰 시 60초 대기하며 파티원을 모집합니다.
    """

    boss_monster: "Monster"
    """보스 몬스터 인스턴스"""

    initiator_id: int
    """대기실 생성자 user_id"""

    participants: dict[int, bool] = field(default_factory=dict)
    """user_id → ready_status 매핑 (True = 준비 완료)"""

    max_participants: int = SOCIAL_ENCOUNTER.BOSS_WAITING_ROOM_MAX_PARTICIPANTS
    """최대 참여 인원 (기본 3명)"""

    timeout_seconds: float = SOCIAL_ENCOUNTER.BOSS_WAITING_ROOM_TIMEOUT
    """대기 타임아웃 (기본 60초)"""

    started: bool = False
    """전투 시작 여부"""

    cancelled: bool = False
    """대기실 취소 여부"""

    created_at: float = field(default_factory=lambda: asyncio.get_event_loop().time())
    """생성 시간"""

    def is_full(self) -> bool:
        """최대 인원 도달 여부"""
        return len(self.participants) >= self.max_participants

    def all_ready(self) -> bool:
        """전원 준비 완료 여부"""
        return all(self.participants.values()) if self.participants else False

    def get_participant_count(self) -> int:
        """현재 참여 인원 수"""
        return len(self.participants)


class BossRoomEncounter(Encounter):
    """
    보스방 대기실 Encounter (Phase 4)

    보스 발견 시 60초 대기하며 근처 플레이어에게 초대를 보냅니다.
    전원 준비 또는 타임아웃 시 보스 전투를 시작합니다.
    """

    encounter_type = EncounterType.EVENT

    def __init__(self, boss_monster: "Monster"):
        self.boss_monster = boss_monster

    async def execute(self, session: "DungeonSession", interaction: discord.Interaction) -> Optional[EncounterResult]:
        """
        보스방 대기실 실행

        Args:
            session: 보스를 발견한 세션
            interaction: Discord interaction

        Returns:
            멀티플레이어 CombatContext가 포함된 EncounterResult 또는 None (취소 시)
        """
        # 1. 대기실 생성
        waiting_room = BossWaitingRoom(
            boss_monster=self.boss_monster,
            initiator_id=session.user_id,
        )

        # 생성자 참여 (미준비 상태)
        waiting_room.participants[session.user_id] = False

        # 세션에 대기실 연결
        session.active_encounter_event = waiting_room
        session.status = SessionType.EVENT

        logger.info(
            f"Boss waiting room created: boss={self.boss_monster.name}, "
            f"initiator={session.user_id}"
        )

        # 2. 근처 플레이어 찾기 (±10 스텝)
        from service.dungeon.social_encounter_checker import get_nearby_sessions

        other_sessions = get_sessions_in_voice_channel(session.voice_channel_id)
        eligible = [
            s
            for s in other_sessions
            if s.user_id != session.user_id
            and s.dungeon
            and s.dungeon.id == session.dungeon.id
            and not s.in_combat
            and not s.ended
        ]

        nearby = get_nearby_sessions(session, eligible, 10)

        # 3. 초대 DM 전송 (거리별 지연: 0s/5s)
        client = session.discord_client or interaction.client

        invite_tasks = []
        for other_session in nearby:
            if waiting_room.is_full():
                break

            distance = ProximityCalculator.calculate_distance(
                session.exploration_step, other_session.exploration_step
            )
            delay = 0 if distance <= 3 else 5

            task = asyncio.create_task(
                self._send_boss_invite(client, other_session.user_id, waiting_room, delay)
            )
            invite_tasks.append(task)

        # 4. 생성자 DM: 대기실 UI
        try:
            user = await client.fetch_user(session.user_id)
            embed = discord.Embed(
                title=f"👑 보스 발견: {self.boss_monster.name}",
                description=(
                    f"**{self.boss_monster.name}**을(를) 발견했습니다!\n\n"
                    "60초 동안 대기하며 파티원을 모집합니다.\n"
                    "근처 플레이어에게 초대를 보냈습니다.\n\n"
                    "**대기실 상태:**\n"
                    f"참여 인원: {waiting_room.get_participant_count()}/{waiting_room.max_participants}\n"
                ),
                color=discord.Color.red(),
            )

            from views.social_encounter_view import BossWaitingRoomView

            view = BossWaitingRoomView(waiting_room, timeout=waiting_room.timeout_seconds)
            await user.send(embed=embed, view=view)
            logger.info(f"Sent boss waiting room UI to initiator {session.user_id}")

        except discord.Forbidden:
            logger.warning(f"Failed to send boss waiting room UI to {session.user_id}")

        # 5. 초대 전송 완료 대기
        if invite_tasks:
            await asyncio.gather(*invite_tasks, return_exceptions=True)

        # 6. 60초 대기 (또는 전원 준비)
        timeout_time = waiting_room.created_at + waiting_room.timeout_seconds
        check_interval = 2  # 2초마다 상태 체크

        while True:
            current_time = asyncio.get_event_loop().time()

            # 타임아웃 체크
            if current_time >= timeout_time:
                logger.info(f"Boss waiting room timeout: {session.user_id}")
                break

            # 취소 체크
            if waiting_room.cancelled:
                logger.info(f"Boss waiting room cancelled: {session.user_id}")
                session.active_encounter_event = None
                session.status = SessionType.IDLE
                return None

            # 전원 준비 체크
            if waiting_room.all_ready() and waiting_room.get_participant_count() > 0:
                logger.info(f"Boss waiting room ready: {session.user_id}, count={waiting_room.get_participant_count()}")
                break

            # 시작 플래그 체크 (리더가 "혼자 도전" 선택)
            if waiting_room.started:
                logger.info(f"Boss waiting room force started: {session.user_id}")
                break

            await asyncio.sleep(check_interval)

        # 7. 전투 시작 (멀티플레이어 CombatContext 생성)
        if waiting_room.cancelled:
            return None

        # 참여자 세션 수집
        participant_sessions = []
        for user_id in waiting_room.participants.keys():
            if user_id == session.user_id:
                continue  # 리더는 session에 있음

            participant_session = get_session(user_id)
            if participant_session and not participant_session.in_combat and not participant_session.ended:
                participant_sessions.append(participant_session)

        # CombatContext 생성 (멀티플레이어)
        from service.dungeon.combat_context import CombatContext

        session.participants.clear()
        session.contribution.clear()

        for participant_session in participant_sessions:
            session.participants[participant_session.user_id] = participant_session.user
            session.contribution[participant_session.user_id] = 0

        context = CombatContext.from_group([self.boss_monster])
        session.combat_context = context
        session.in_combat = True
        session.status = SessionType.FIGHT

        # 8. 참여자 세션 상태 업데이트
        for participant_session in participant_sessions:
            participant_session.in_combat = True
            participant_session.status = SessionType.FIGHT
            participant_session.combat_context = context

        # 9. 대기실 정리
        session.active_encounter_event = None

        participant_count = 1 + len(participant_sessions)

        logger.info(
            f"Boss waiting room started: boss={self.boss_monster.name}, "
            f"participants={participant_count}"
        )

        return EncounterResult(
            encounter_type=EncounterType.ELITE_MONSTER,
            message=(
                f"👑 **{self.boss_monster.name}**과(와) 조우했다! "
                f"({participant_count}명이 함께 싸운다)"
            ),
            context=context,
        )

    async def _send_boss_invite(
        self, client: discord.Client, user_id: int, waiting_room: BossWaitingRoom, delay: int
    ) -> None:
        """보스방 초대 DM 전송 (지연 가능)"""
        if delay > 0:
            await asyncio.sleep(delay)

        # 최대 인원 체크
        if waiting_room.is_full():
            logger.debug(f"Boss waiting room full, skipping invite to {user_id}")
            return

        try:
            user = await client.fetch_user(user_id)
            embed = discord.Embed(
                title=f"👑 보스방 초대: {waiting_room.boss_monster.name}",
                description=(
                    f"근처 플레이어가 **{waiting_room.boss_monster.name}**를 발견했습니다!\n\n"
                    "보스방에 참여하시겠습니까?\n"
                    f"현재 참여 인원: {waiting_room.get_participant_count()}/{waiting_room.max_participants}"
                ),
                color=discord.Color.red(),
            )

            from views.social_encounter_view import BossWaitingRoomInviteView

            view = BossWaitingRoomInviteView(waiting_room, timeout=waiting_room.timeout_seconds)
            await user.send(embed=embed, view=view)
            logger.info(f"Sent boss room invite to {user_id} with {delay}s delay")

        except discord.Forbidden:
            logger.warning(f"Failed to send boss room invite to {user_id}")
        except Exception as e:
            logger.error(f"Error sending boss room invite to {user_id}: {e}", exc_info=True)


# ============================================================
# Phase 4: 동시 조우 (Simultaneous Encounter) - 경쟁 모드
# ============================================================


@dataclass
class RaceState:
    """
    경쟁 모드 레이스 상태 (Phase 4)

    두 플레이어가 동시에 전투를 시작했을 때 협력 또는 경쟁 선택 시
    경쟁 모드의 실시간 진행도를 추적합니다.
    """

    racer1_id: int
    """레이서 1 user_id"""

    racer2_id: int
    """레이서 2 user_id"""

    mode: str = "competitive"
    """모드: "competitive" 또는 "cooperative" """

    # 실시간 HP 추적 (0.0~1.0 백분율)
    racer1_monster_hp_pct: float = 1.0
    """레이서 1의 몬스터 HP 백분율"""

    racer2_monster_hp_pct: float = 1.0
    """레이서 2의 몬스터 HP 백분율"""

    racer1_hp_pct: float = 1.0
    """레이서 1의 HP 백분율"""

    racer2_hp_pct: float = 1.0
    """레이서 2의 HP 백분율"""

    winner_id: Optional[int] = None
    """승자 user_id (전투 종료 시)"""

    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    """동기화 락 (race condition 방지)"""

    created_at: float = field(default_factory=lambda: asyncio.get_event_loop().time())
    """생성 시간"""

    def is_finished(self) -> bool:
        """레이스 종료 여부 (승자 결정됨)"""
        return self.winner_id is not None


class SimultaneousEncounter(Encounter):
    """
    동시 조우 Encounter (Phase 4)

    같은 스텝에서 전투를 시작한 플레이어를 발견하면
    협력 또는 경쟁 선택지를 제공합니다.
    """

    encounter_type = EncounterType.EVENT

    def __init__(self, partner_session: "DungeonSession"):
        self.partner_session = partner_session

    async def execute(self, session: "DungeonSession", interaction: discord.Interaction) -> Optional[EncounterResult]:
        """
        동시 조우 실행

        Args:
            session: 현재 세션 (방금 전투 시작)
            partner_session: 동시 전투 시작한 파트너 세션

        Returns:
            EncounterResult 또는 None (독립 전투)
        """
        # 1. 양쪽에 선택지 DM 전송 (30초)
        client = session.discord_client or interaction.client

        # 이벤트 상태 생성
        responses = {}

        # 동시 DM 전송
        tasks = [
            self._send_choice_dm(client, session.user_id, self.partner_session.user.get_name(), responses),
            self._send_choice_dm(client, self.partner_session.user_id, session.user.get_name(), responses),
        ]

        await asyncio.gather(*tasks, return_exceptions=True)

        # 2. 30초 대기 (응답 수집)
        timeout_time = asyncio.get_event_loop().time() + 30.0
        check_interval = 2

        while True:
            current_time = asyncio.get_event_loop().time()

            if current_time >= timeout_time:
                logger.info(f"Simultaneous encounter timeout: {session.user_id}, {self.partner_session.user_id}")
                break

            if session.user_id in responses and self.partner_session.user_id in responses:
                logger.info(f"Simultaneous encounter both responded")
                break

            await asyncio.sleep(check_interval)

        # 3. 응답 처리
        choice1 = responses.get(session.user_id, "pass")
        choice2 = responses.get(self.partner_session.user_id, "pass")

        # Case 1: 양쪽 협력 → 즉시 멀티플레이어
        if choice1 == "cooperate" and choice2 == "cooperate":
            logger.info(f"Simultaneous encounter: cooperative mode")

            # 파트너 자동 합류
            session.participants[self.partner_session.user_id] = self.partner_session.user
            session.contribution[self.partner_session.user_id] = 0

            # 파트너 세션 상태 업데이트
            self.partner_session.in_combat = True
            self.partner_session.status = SessionType.FIGHT
            self.partner_session.combat_context = session.combat_context

            # +20% 보상 보너스 설정
            session.explore_buffs["simultaneous_coop_bonus"] = 1.2

            return EncounterResult(
                encounter_type=EncounterType.EVENT,
                message=f"🤝 {self.partner_session.user.get_name()}와(과) 협력하기로 했다! (보상 +20%)",
            )

        # Case 2: 한 명이라도 경쟁 → 레이스 모드
        elif choice1 == "compete" or choice2 == "compete":
            logger.info(f"Simultaneous encounter: competitive mode")

            # 레이스 상태 생성
            race_state = RaceState(
                racer1_id=session.user_id,
                racer2_id=self.partner_session.user_id,
                mode="competitive",
            )

            # 세션에 레이스 상태 저장
            session.active_encounter_event = race_state
            self.partner_session.active_encounter_event = race_state

            # 쿨타임 설정
            session.encounter_event_cooldown = session.exploration_step
            self.partner_session.encounter_event_cooldown = self.partner_session.exploration_step

            return EncounterResult(
                encounter_type=EncounterType.EVENT,
                message=(
                    f"⚔️ {self.partner_session.user.get_name()}와(과) 경쟁하기로 했다!\n"
                    "먼저 몬스터를 처치하는 사람이 승리! (승자 150%, 패자 50%)"
                ),
            )

        # Case 3: 혼합 또는 타임아웃 → 독립 전투
        else:
            logger.info(f"Simultaneous encounter: independent mode (choice1={choice1}, choice2={choice2})")
            return None  # 각자 진행

    async def _send_choice_dm(
        self, client: discord.Client, user_id: int, partner_name: str, responses: dict
    ) -> None:
        """협력/경쟁 선택 DM 전송"""
        try:
            user = await client.fetch_user(user_id)
            embed = discord.Embed(
                title="⚔️ 동시 조우!",
                description=(
                    f"근처에서 **{partner_name}**도 전투를 시작했습니다!\n\n"
                    "협력할까요, 경쟁할까요?\n\n"
                    "**협력**: 함께 싸우기 (보상 +20%)\n"
                    "**경쟁**: 먼저 처치하기 (승자 150%, 패자 50%)\n"
                    "**독립**: 각자 진행 (정상 보상)"
                ),
                color=discord.Color.orange(),
            )

            from views.social_encounter_view import SimultaneousEncounterChoiceView

            view = SimultaneousEncounterChoiceView(user_id, responses, timeout=30)
            await user.send(embed=embed, view=view)
            logger.info(f"Sent simultaneous encounter choice to {user_id}")

        except discord.Forbidden:
            logger.warning(f"Failed to send simultaneous encounter choice to {user_id}")
        except Exception as e:
            logger.error(f"Error sending simultaneous encounter choice to {user_id}: {e}", exc_info=True)


# ============================================================
# Phase 4: 위기 목격 (Crisis Witness)
# ============================================================


@dataclass
class CrisisEvent:
    """
    위기 이벤트 상태 (Phase 4)

    전투 중 HP < 30%인 플레이어를 발견했을 때 구조/응원 옵션을 제공합니다.
    """

    victim_id: int
    """피해자 user_id"""

    victim_hp_percent: float
    """피해자 HP 백분율"""

    notified_players: set[int] = field(default_factory=set)
    """알림을 받은 플레이어 user_id 집합"""

    responders: dict[int, str] = field(default_factory=dict)
    """user_id → 응답 ("intervene", "cheer", "pass")"""

    created_at: float = field(default_factory=lambda: asyncio.get_event_loop().time())
    """생성 시간"""


async def send_crisis_witness_alert(
    victim_session: "DungeonSession",
    nearby_sessions: list["DungeonSession"],
    client: discord.Client
) -> None:
    """
    위기 목격 알림 전송 (Phase 4)

    HP < 30%인 플레이어 근처의 다른 플레이어들에게 긴급 알림을 보냅니다.

    Args:
        victim_session: 위기 상태 플레이어 세션
        nearby_sessions: 근처 플레이어 세션 목록 (±2 스텝)
        client: Discord client
    """
    victim_user = victim_session.user
    hp_percent = victim_user.now_hp / victim_user.max_hp if victim_user.max_hp > 0 else 0.0

    # 이벤트 생성
    crisis_event = CrisisEvent(
        victim_id=victim_session.user_id,
        victim_hp_percent=hp_percent,
    )

    # 근처 플레이어들에게 알림
    for other_session in nearby_sessions:
        user_id = other_session.user_id

        # 이미 알림받음
        if user_id in crisis_event.notified_players:
            continue

        crisis_event.notified_players.add(user_id)

        try:
            user = await client.fetch_user(user_id)
            embed = discord.Embed(
                title="🚨 위기 목격!",
                description=(
                    f"근처에서 **{victim_user.get_name()}**이(가) 위험합니다!\n"
                    f"현재 HP: **{hp_percent:.0%}**\n\n"
                    "어떻게 하시겠습니까?\n\n"
                    "**달려가기**: 난입하여 도움 (보상 +30%)\n"
                    "**응원하기**: 원거리 응원 (ATK +5, 1턴)\n"
                    "**지나치기**: 무시하고 계속 탐험"
                ),
                color=discord.Color.red(),
            )

            from views.social_encounter_view import CrisisWitnessView

            view = CrisisWitnessView(crisis_event, victim_session, timeout=30)
            await user.send(embed=embed, view=view)
            logger.info(f"Sent crisis witness alert to {user_id} for victim {victim_session.user_id}")

        except discord.Forbidden:
            logger.warning(f"Failed to send crisis witness alert to {user_id}")
        except Exception as e:
            logger.error(f"Error sending crisis witness alert to {user_id}: {e}", exc_info=True)
