"""
관전 서비스 - 핵심 비즈니스 로직

전투 알림 게시, 관전 시작/종료, 실시간 업데이트, 관전자 정리 등을 담당합니다.
"""
import logging
from typing import Optional
import discord

from exceptions import SpectatorError, SpectatorTargetNotInDungeonError, SpectatorDMFailedError
from service.spectator.spectator_state import (
    start_spectating,
    stop_spectating,
    get_spectator_state,
    is_spectating,
)
from service.spectator.spectator_ui import (
    create_combat_notification_embed,
    create_spectator_combat_embed,
)

logger = logging.getLogger(__name__)


class SpectatorService:
    """관전 시스템 서비스"""

    @staticmethod
    async def post_combat_notification(session, channel: discord.TextChannel) -> Optional[discord.Message]:
        """
        서버 채널에 전투 알림 메시지 + 관전 버튼 게시

        Args:
            session: DungeonSession
            channel: Discord 텍스트 채널

        Returns:
            게시된 메시지 (또는 None, 실패 시)
        """
        try:
            from views.combat_notification_view import CombatNotificationView

            embed = create_combat_notification_embed(session)
            view = CombatNotificationView(session)

            message = await channel.send(embed=embed, view=view)

            logger.info(
                f"Combat notification posted: user={session.user_id}, "
                f"dungeon={session.dungeon.id if session.dungeon else None}, "
                f"channel={channel.id}"
            )

            return message

        except Exception as e:
            logger.error(f"Failed to post combat notification: {e}")
            return None

    @staticmethod
    async def start_spectating(
        spectator: discord.User,
        target_session,
        interaction: discord.Interaction
    ) -> discord.Message:
        """
        관전 시작 (버튼 콜백에서 호출)

        관전자에게 DM으로 실시간 전투 화면을 전송합니다.

        Args:
            spectator: 관전자 (Discord User)
            target_session: 관전 대상의 DungeonSession
            interaction: Discord interaction

        Returns:
            관전자 DM 메시지

        Raises:
            SpectatorTargetNotInDungeonError: 대상이 던전에 없음
            SpectatorDMFailedError: DM 전송 실패
        """
        # 대상이 던전에 있는지 확인
        if not target_session or target_session.ended:
            target_name = target_session.user.get_name() if target_session and target_session.user else None
            raise SpectatorTargetNotInDungeonError(target_name)

        # 관전자 상태 등록
        spectator_state = start_spectating(spectator.id, target_session.user_id)
        target_session.spectators.add(spectator.id)

        logger.info(
            f"Spectator started: spectator={spectator.id}, "
            f"target={target_session.user_id}, "
            f"dungeon={target_session.dungeon.name if target_session.dungeon else None}"
        )

        # 관전 UI 생성
        from views.spectator_view import SpectatorView

        # 전투 중이면 전투 화면, 아니면 대기 화면
        if target_session.in_combat and target_session.combat_context:
            embed = create_spectator_combat_embed(
                target_session.user,
                target_session.combat_context
            )
        else:
            # 대기 화면
            embed = discord.Embed(
                title=f"👀 {target_session.user.get_name()}님의 던전 관전",
                description=(
                    f"**던전**: {target_session.dungeon.name}\\n"
                    f"**진행도**: {target_session.exploration_step}/{target_session.max_steps}\\n\\n"
                    f"전투가 시작되면 실시간으로 업데이트됩니다."
                ),
                color=discord.Color.from_rgb(155, 89, 182)  # SPECTATOR 색상
            )
            embed.set_footer(text="👀 관전 대기 중...")

        view = SpectatorView(spectator, target_session)

        # DM 전송
        try:
            # 이미 관전 중이면 기존 메시지 업데이트, 아니면 새 메시지
            if spectator.id in target_session.spectator_messages:
                spectator_msg = target_session.spectator_messages[spectator.id]
                try:
                    await spectator_msg.edit(embed=embed, view=view)
                    logger.info(f"Updated existing spectator message for {spectator.id}")
                except discord.NotFound:
                    # 메시지가 삭제됨 - 새로 생성
                    spectator_msg = await spectator.send(embed=embed, view=view)
                    target_session.spectator_messages[spectator.id] = spectator_msg
            else:
                spectator_msg = await spectator.send(embed=embed, view=view)
                target_session.spectator_messages[spectator.id] = spectator_msg

            view.message = spectator_msg

            logger.debug(f"Spectator DM sent: spectator={spectator.id}")

            return spectator_msg

        except discord.Forbidden:
            # DM 전송 실패 - 정리
            stop_spectating(spectator.id)
            target_session.spectators.discard(spectator.id)
            raise SpectatorDMFailedError()

    @staticmethod
    async def stop_spectating(spectator_id: int) -> None:
        """
        관전 종료

        Args:
            spectator_id: 관전자 Discord 유저 ID
        """
        state = get_spectator_state(spectator_id)
        if not state:
            return

        # 대상 세션에서 제거
        from service.session import get_session
        target_session = get_session(state.target_id)

        if target_session:
            target_session.spectators.discard(spectator_id)

            # 관전자 메시지 삭제
            if spectator_id in target_session.spectator_messages:
                msg = target_session.spectator_messages[spectator_id]
                try:
                    await msg.delete()
                except discord.NotFound:
                    pass
                del target_session.spectator_messages[spectator_id]

        # 상태 제거
        stop_spectating(spectator_id)

        logger.info(f"Spectator stopped: spectator={spectator_id}")

    @staticmethod
    async def update_all_spectators(session) -> None:
        """
        전투 상태 변경 시 모든 관전자 메시지 업데이트

        Args:
            session: DungeonSession
        """
        if not session.spectators:
            return

        if not session.combat_context:
            logger.warning(f"update_all_spectators called but no combat_context for session {session.user_id}")
            return

        # 전투 embed 생성
        embed = create_spectator_combat_embed(session.user, session.combat_context)

        # 모든 관전자 메시지 업데이트
        for spectator_id in list(session.spectators):
            if spectator_id not in session.spectator_messages:
                continue

            msg = session.spectator_messages[spectator_id]

            try:
                await msg.edit(embed=embed)
            except discord.NotFound:
                # 메시지가 삭제됨 - 정리
                session.spectators.discard(spectator_id)
                del session.spectator_messages[spectator_id]
                stop_spectating(spectator_id)
                logger.debug(f"Spectator message not found, cleaned up: {spectator_id}")
            except Exception as e:
                logger.error(f"Failed to update spectator {spectator_id}: {e}")

    @staticmethod
    async def cleanup_spectators(session) -> None:
        """
        세션 종료 시 모든 관전자 정리 및 전투 알림 메시지 삭제

        Args:
            session: DungeonSession
        """
        for spectator_id in list(session.spectators):
            await SpectatorService.stop_spectating(spectator_id)

        session.spectators.clear()
        session.spectator_messages.clear()

        # 전투 알림 메시지 삭제
        if session.combat_notification_message:
            try:
                await session.combat_notification_message.delete()
                logger.debug(f"Deleted combat notification message for session {session.user_id}")
            except discord.NotFound:
                logger.debug(f"Combat notification message already deleted for session {session.user_id}")
            except Exception as e:
                logger.error(f"Failed to delete combat notification message: {e}")
            finally:
                session.combat_notification_message = None

        logger.info(f"All spectators cleaned up for session {session.user_id}")
