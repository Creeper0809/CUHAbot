"""
난입 서비스 (Intervention Service)

전투 난입 요청, 검증, 처리를 담당합니다.
"""
import time
import logging
from typing import Optional
import discord

from exceptions import (
    InterventionError,
    InterventionWindowClosedError,
    InterventionCooldownError,
    CombatFullError,
    AlreadyParticipatingError,
    InsufficientLevelError,
    InterventionNotAllowedError,
)
from config.multiplayer import PARTY
from service.session import DungeonSession
from models import User

logger = logging.getLogger(__name__)

# 난입 쿨타임 저장소 (user_id → 마지막 난입 시간)
# TODO: DB에 영구 저장
_intervention_cooldowns: dict[int, float] = {}


class InterventionService:
    """난입 시스템 서비스"""

    @staticmethod
    async def request_intervention(
        requester: discord.User,
        target_session: DungeonSession,
        interaction: discord.Interaction
    ) -> None:
        """
        난입 요청 처리

        Args:
            requester: 난입 요청자 (Discord User)
            target_session: 대상 전투 세션
            interaction: Discord 인터랙션

        Raises:
            InterventionError: 난입 불가 조건
        """
        requester_id = requester.id

        # 조건 검증
        await InterventionService._validate_intervention(
            requester_id, target_session
        )

        # User 엔티티 로드
        requester_user = await User.get_or_none(discord_id=requester_id)
        if not requester_user:
            raise InterventionError("등록되지 않은 사용자입니다.")

        # 레벨 차이 경고 메시지
        warning_msg = InterventionService._get_level_warning(
            requester_user.level,
            target_session.user.level
        )

        # intervention_pending에 등록
        target_session.intervention_pending[requester_id] = time.time()

        # 응답 메시지
        response_msg = "✅ 다음 라운드에 전투에 참여합니다!"
        if warning_msg:
            response_msg += f"\n\n{warning_msg}"

        await interaction.response.send_message(response_msg, ephemeral=True)

        logger.info(
            f"Intervention requested: requester={requester_id}, "
            f"target={target_session.user_id}, level_diff={requester_user.level - target_session.user.level}"
        )

    @staticmethod
    async def _validate_intervention(
        requester_id: int,
        session: DungeonSession
    ) -> None:
        """
        난입 가능 여부 검증

        Args:
            requester_id: 난입 요청자 Discord ID
            session: 대상 세션

        Raises:
            InterventionError: 난입 불가 조건
        """
        # 1. 난입 허용 여부
        if not session.allow_intervention:
            raise InterventionNotAllowedError()

        # 2. 전투 중인지 확인
        if not session.in_combat or not session.combat_context:
            raise InterventionError("대상이 전투 중이 아닙니다.")

        # 3. 3턴 이내인지 확인
        current_round = session.combat_context.round_number
        if current_round > PARTY.INTERVENTION_WINDOW_TURNS:
            raise InterventionWindowClosedError(current_round)

        # 4. 이미 참여 중인지 확인
        if requester_id == session.user_id:
            raise AlreadyParticipatingError()
        if requester_id in session.participants:
            raise AlreadyParticipatingError()
        if requester_id in session.intervention_pending:
            raise AlreadyParticipatingError()

        # 5. 파티 인원 체크 (리더 포함)
        current_participants = 1 + len(session.participants)  # 리더 + 참가자
        if current_participants >= PARTY.MAX_COMBAT_PARTICIPANTS:
            raise CombatFullError(PARTY.MAX_COMBAT_PARTICIPANTS)

        # 6. 쿨타임 체크
        if requester_id in _intervention_cooldowns:
            last_intervention = _intervention_cooldowns[requester_id]
            elapsed = time.time() - last_intervention
            if elapsed < PARTY.INTERVENTION_COOLDOWN_SECONDS:
                remaining = int(PARTY.INTERVENTION_COOLDOWN_SECONDS - elapsed)
                raise InterventionCooldownError(remaining)

        # 7. 레벨 제한 체크
        requester_user = await User.get_or_none(discord_id=requester_id)
        if not requester_user:
            raise InterventionError("등록되지 않은 사용자입니다.")

        if requester_user.level < session.dungeon.require_level:
            raise InsufficientLevelError(
                session.dungeon.require_level,
                requester_user.level
            )

    @staticmethod
    def _get_level_warning(requester_level: int, leader_level: int) -> Optional[str]:
        """
        레벨 차이에 따른 경고 메시지

        Args:
            requester_level: 난입자 레벨
            leader_level: 파티 리더 레벨

        Returns:
            경고 메시지 (없으면 None)
        """
        level_diff = requester_level - leader_level

        if level_diff >= 15:
            return "⚠️ 레벨 차이가 너무 커서 보상을 받을 수 없습니다 (0%)"
        elif level_diff >= 10:
            return "⚠️ 레벨 차이로 인해 보상이 대폭 감소합니다 (5%)"
        elif level_diff >= 5:
            return "⚠️ 레벨 차이로 인해 보상이 감소합니다 (20%)"

        return None

    @staticmethod
    async def process_pending_interventions(
        session: DungeonSession,
        context
    ) -> list[str]:
        """
        대기 중인 난입자를 전투에 추가

        Args:
            session: 던전 세션
            context: 전투 컨텍스트

        Returns:
            전투 로그 메시지 리스트
        """
        logs = []

        if not session.intervention_pending:
            return logs

        # 대기 중인 난입자 처리
        for user_id, request_time in list(session.intervention_pending.items()):
            try:
                # User 엔티티 로드
                user = await User.get_or_none(discord_id=user_id)
                if not user:
                    logger.warning(f"Intervention user not found: {user_id}")
                    del session.intervention_pending[user_id]
                    continue

                # 전투 초기화 (런타임 필드 + 스킬 덱)
                if not hasattr(user, 'status') or user.status is None:
                    user._init_runtime_fields()

                # 스킬 덱 로드
                from service.skill.skill_deck_service import SkillDeckService
                await SkillDeckService.load_deck_to_user(user)

                # 장비 스탯 로드
                from service.item.equipment_service import EquipmentService
                await EquipmentService.apply_equipment_stats(user)

                # participants에 추가
                session.participants[user_id] = user

                # 행동 게이지 초기화
                context.action_gauges[id(user)] = 0

                # 기여도 초기화
                session.contribution[user_id] = 0

                # 쿨타임 기록
                _intervention_cooldowns[user_id] = time.time()

                # 로그 추가
                logs.append(f"💫 **{user.get_name()}** 전투에 난입!")

                logger.info(
                    f"Intervention processed: user={user_id}, "
                    f"round={context.round_number}"
                )

            except Exception as e:
                logger.error(f"Failed to process intervention for {user_id}: {e}")

            finally:
                # pending에서 제거
                del session.intervention_pending[user_id]

        return logs

    @staticmethod
    def get_intervention_cooldown(user_id: int) -> Optional[int]:
        """
        남은 쿨타임 확인

        Args:
            user_id: Discord 사용자 ID

        Returns:
            남은 쿨타임 (초), 없으면 None
        """
        if user_id not in _intervention_cooldowns:
            return None

        last_intervention = _intervention_cooldowns[user_id]
        elapsed = time.time() - last_intervention

        if elapsed >= PARTY.INTERVENTION_COOLDOWN_SECONDS:
            # 쿨타임 만료
            del _intervention_cooldowns[user_id]
            return None

        return int(PARTY.INTERVENTION_COOLDOWN_SECONDS - elapsed)
