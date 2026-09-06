"""
난입 서비스 (Intervention Service)

전투 난입 요청, 검증, 처리를 담당합니다.
"""
import time
import logging
from typing import Optional
import discord
from tortoise.transactions import in_transaction

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
from service.session import ContentType, DungeonSession
from models import User

logger = logging.getLogger(__name__)

# NOTE: 쿨타운은 User.last_intervention_time (DB)로 영속화됨
# 레거시 인메모리 캐시 (하위 호환성 유지, 점진적 제거 예정)
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

        # Phase 2: 근접도 계산 및 저장
        from service.session import get_session
        from service.voice_channel.proximity_calculator import ProximityCalculator
        from service.notification.proximity_reward_calculator import get_intervention_cost

        requester_session = get_session(requester_id)
        if requester_session and requester_session.dungeon:
            distance = ProximityCalculator.calculate_distance(
                target_session.exploration_step,
                requester_session.exploration_step
            )
        else:
            distance = 999  # 던전 미진입 시 최대 거리 취급

        target_session.intervention_distances[requester_id] = distance
        cost = get_intervention_cost(distance)

        # intervention_pending에 등록
        target_session.intervention_pending[requester_id] = time.time()

        # 응답 메시지
        response_msg = f"✅ 다음 라운드에 전투에 참여합니다!\n💰 비용: {cost}G (거리: {distance}걸음)"
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
        # 0. 레이드 콘텐츠는 난입 불가
        if session.content_type == ContentType.RAID:
            raise InterventionError("레이드 전투는 난입할 수 없습니다.")

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

        # 6. 쿨타임 체크 (DB 기반)
        requester_user = await User.get_or_none(discord_id=requester_id)
        if not requester_user:
            raise InterventionError("등록되지 않은 사용자입니다.")

        if requester_user.last_intervention_time:
            from datetime import datetime, timezone
            elapsed = (datetime.now(timezone.utc) - requester_user.last_intervention_time).total_seconds()
            if elapsed < PARTY.INTERVENTION_COOLDOWN_SECONDS:
                remaining = int(PARTY.INTERVENTION_COOLDOWN_SECONDS - elapsed)
                raise InterventionCooldownError(remaining)

        # 7. 레벨 제한 체크 (이미 로드됨)
        if requester_user.level < session.dungeon.require_level:
            raise InsufficientLevelError(
                session.dungeon.require_level,
                requester_user.level
            )

        # 8. 음성 채널 체크 (Phase 1: Voice Channel Shared Dungeon)
        from service.session import get_session as get_requester_session

        requester_session = get_requester_session(requester_id)

        if not requester_session or not requester_session.voice_channel_id:
            raise InterventionError("음성 채널에 접속해야 난입할 수 있습니다.")

        if requester_session.voice_channel_id != session.voice_channel_id:
            raise InterventionError("같은 음성 채널에 있어야 난입할 수 있습니다.")

        # 9. 던전 체크 (Phase 1: Voice Channel Shared Dungeon)
        if not requester_session.dungeon or requester_session.dungeon.id != session.dungeon.id:
            raise InterventionError("같은 던전을 선택한 플레이어만 난입할 수 있습니다.")

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

        # 레이드는 난입 처리 자체를 수행하지 않음
        if session.content_type == ContentType.RAID:
            if session.intervention_pending:
                session.intervention_pending.clear()
            return logs

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

                # Phase 2: 근접도 기반 비용 차감
                from service.notification.proximity_reward_calculator import get_intervention_cost

                distance = session.intervention_distances.get(user_id, 999)
                cost = get_intervention_cost(distance)

                # 트랜잭션으로 골드 차감 및 참가자 추가 원자적 처리
                async with in_transaction() as conn:
                    # 골드 체크 및 차감
                    if cost > 0:
                        # 트랜잭션 내에서 최신 데이터 재조회
                        user = await User.get_or_none(discord_id=user_id, using_db=conn)
                        if not user:
                            logger.warning(f"Intervention user disappeared: {user_id}")
                            continue

                        if user.gold < cost:
                            logs.append(f"❌ **{user.get_name()}** 골드 부족 ({cost}G)")
                            if user_id in session.intervention_distances:
                                del session.intervention_distances[user_id]
                            continue

                        user.gold -= cost
                        await user.save(using_db=conn)
                        logger.info(f"Intervention cost deducted: {user_id} paid {cost}G (distance={distance})")

                    # 트랜잭션 성공 후 전투 초기화 (런타임 필드 + 스킬 덱)
                    if not hasattr(user, 'status') or user.status is None:
                        user._init_runtime_fields()

                    # 스킬 덱 로드
                    from service.skill.skill_deck_service import SkillDeckService
                    await SkillDeckService.load_deck_to_user(user)
                    from service.skill.ultimate_service import load_ultimate_to_user, reset_ultimate_combat_state
                    await load_ultimate_to_user(user)
                    reset_ultimate_combat_state(user)

                    # 장비 스탯 로드
                    from service.item.equipment_service import EquipmentService
                    await EquipmentService.apply_equipment_stats(user)

                    # participants에 추가 (트랜잭션 성공 후에만)
                    previous_members = 1 + len(session.participants)
                    session.participants[user_id] = user
                    context.rescale_for_party(previous_members, previous_members + 1)

                    # 행동 게이지 초기화
                    context.action_gauges[id(user)] = 0

                    # 기여도 초기화
                    session.contribution[user_id] = 0

                    # 쿨타임 기록 (DB 영속화)
                    from datetime import datetime, timezone
                    user.last_intervention_time = datetime.now(timezone.utc)
                    await user.save(update_fields=['last_intervention_time'], using_db=conn)

                    # 로그 추가
                    logs.append(f"💫 **{user.get_name()}** 전투에 난입!")

                    logger.info(
                        f"Intervention processed: user={user_id}, "
                        f"round={context.round_number}"
                    )

            except Exception as e:
                logger.error(f"Failed to process intervention for {user_id}: {e}", exc_info=True)
                # 트랜잭션 실패 시 자동 롤백됨

            finally:
                # pending에서 제거
                if user_id in session.intervention_pending:
                    del session.intervention_pending[user_id]

        return logs

    @staticmethod
    async def get_intervention_cooldown(user_id: int) -> Optional[int]:
        """
        남은 쿨타임 확인 (DB 기반)

        Args:
            user_id: Discord 사용자 ID

        Returns:
            남은 쿨타임 (초), 없으면 None
        """
        user = await User.get_or_none(discord_id=user_id)
        if not user or not user.last_intervention_time:
            return None

        from datetime import datetime, timezone
        elapsed = (datetime.now(timezone.utc) - user.last_intervention_time).total_seconds()

        if elapsed >= PARTY.INTERVENTION_COOLDOWN_SECONDS:
            # 쿨타임 만료
            return None

        return int(PARTY.INTERVENTION_COOLDOWN_SECONDS - elapsed)
