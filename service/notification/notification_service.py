"""
계층화된 알림 서비스 (Phase 2)

근접도(exploration_step 차이)에 따라 알림 지연 시간을 조절합니다.
- 즉시 거리 (±3 스텝): 0초 즉시 알림
- 근처 거리 (±10 스텝): 5초 후 알림
- 먼 거리 (>10 스텝): 15초 후 알림
"""
import asyncio
import logging
from typing import Optional

import discord

from config.notification import NOTIFICATION as NOTIF_CONFIG
from service.session import get_session, get_sessions_in_voice_channel
from service.session import ContentType
from service.voice_channel.proximity_calculator import ProximityCalculator

logger = logging.getLogger(__name__)


class NotificationService:
    """
    계층화된 알림 서비스

    거리에 따라 알림 지연 시간을 조절하여 전송합니다.
    Phase 2에서는 전투 알림에만 적용됩니다.
    """

    @staticmethod
    async def send_tiered_combat_notifications(
        session,
        channel: discord.TextChannel,
        client: discord.Client,
        view: discord.ui.View
    ) -> Optional[discord.Message]:
        """
        계층화된 전투 알림 발송

        같은 음성 채널의 다른 플레이어들에게 거리에 따라
        차등화된 지연 시간으로 알림을 전송합니다.

        Args:
            session: DungeonSession (전투 시작한 세션)
            channel: 알림을 보낼 텍스트 채널
            client: Discord 클라이언트
            view: 알림 메시지에 첨부할 View (난입/관전 버튼)

        Returns:
            채널에 전송된 메시지 (없으면 None)
        """
        if not session.voice_channel_id:
            logger.debug(f"User {session.user_id} not in voice channel, skipping tiered notifications")
            return None

        # 1. 같은 음성 채널의 다른 세션 조회
        other_sessions = get_sessions_in_voice_channel(session.voice_channel_id)
        other_sessions = [s for s in other_sessions if s.user_id != session.user_id]

        if not other_sessions:
            logger.debug(f"No other users in voice channel {session.voice_channel_id}")
            return None

        # 2. 거리별 분류 및 알림 발송
        for other_session in other_sessions:
            # 다른 던전은 원거리 취급 (관전만 가능)
            if not other_session.dungeon or other_session.dungeon.id != session.dungeon.id:
                distance = 999
            else:
                distance = ProximityCalculator.calculate_distance(
                    session.exploration_step,
                    other_session.exploration_step
                )

            # 거리에 따른 지연 시간 결정
            if distance <= 3:
                delay = NOTIF_CONFIG.IMMEDIATE_DELAY
                tier = "IMMEDIATE"
            elif distance <= 10:
                delay = NOTIF_CONFIG.NEARBY_DELAY
                tier = "NEARBY"
            else:
                delay = NOTIF_CONFIG.FAR_DELAY
                tier = "FAR"

            logger.info(
                f"Combat notification: {session.user_id} → {other_session.user_id}, "
                f"distance={distance}, tier={tier}, delay={delay}s"
            )

            # 비차단 알림 전송
            if delay == 0:
                await NotificationService._send_notification(
                    client, other_session.user_id, session, channel, view, distance
                )
            else:
                asyncio.create_task(
                    NotificationService._send_delayed_notification(
                        client, other_session.user_id, session, channel, view, distance, delay
                    )
                )

        # 3. 채널 메시지 반환 (기존 spectator 호환성)
        # 채널 메시지는 별도로 전송하지 않고, DM만 전송
        return None

    @staticmethod
    async def _send_delayed_notification(
        client: discord.Client,
        target_user_id: int,
        session,
        channel: discord.TextChannel,
        view: discord.ui.View,
        distance: int,
        delay: int
    ) -> None:
        """
        지연된 알림 전송

        Args:
            client: Discord 클라이언트
            target_user_id: 알림받을 유저 ID
            session: 전투 중인 세션
            channel: 텍스트 채널
            view: View
            distance: 거리
            delay: 지연 시간 (초)
        """
        try:
            await asyncio.sleep(delay)

            # 지연 시간 후 세션 상태 재확인
            current_session = get_session(session.user_id)
            if not current_session or not current_session.in_combat:
                logger.debug(f"Combat ended before delayed notification to {target_user_id}")
                return

            await NotificationService._send_notification(
                client, target_user_id, session, channel, view, distance
            )
        except Exception as e:
            logger.error(
                f"Failed to send delayed notification to {target_user_id}: {e}",
                exc_info=True
            )

    @staticmethod
    async def _send_notification(
        client: discord.Client,
        target_user_id: int,
        session,
        channel: discord.TextChannel,
        view: discord.ui.View,
        distance: int
    ) -> None:
        """
        실제 알림 전송 (DM)

        Args:
            client: Discord 클라이언트
            target_user_id: 알림받을 유저 ID
            session: 전투 중인 세션
            channel: 텍스트 채널
            view: View
            distance: 거리
        """
        try:
            if target_user_id == session.user_id:
                return
            target_user = await client.fetch_user(target_user_id)
            if not target_user:
                return

            # 거리 정보 포함한 알림 메시지
            if distance <= 3:
                distance_info = f"🔥 **즉시 근접!** (거리: {distance}걸음)"
            elif distance <= 10:
                distance_info = f"⚡ **근처** (거리: {distance}걸음)"
            elif distance == 999:
                distance_info = "🌐 **다른 던전**"
            else:
                distance_info = f"📡 **원거리** (거리: {distance}걸음)"

            embed = discord.Embed(
                title="⚔️ 전투 발생!",
                description=(
                    f"{session.user.get_name()}님이 {session.dungeon.name}에서 전투 중입니다!\n\n"
                    f"{distance_info}\n\n"
                    f"{'관전할 수 있습니다.' if session.content_type == ContentType.RAID else '난입하거나 관전할 수 있습니다.'}"
                ),
                color=discord.Color.red()
            )

            # 거리 정보를 View에 전달 (버튼 커스터마이징용)
            if hasattr(view, 'distance'):
                view.distance = distance

            await target_user.send(embed=embed, view=view)
            logger.info(f"Sent combat notification DM to {target_user_id} (distance={distance})")

        except discord.Forbidden:
            logger.warning(f"Cannot send DM to {target_user_id} (DM disabled)")
        except Exception as e:
            logger.error(f"Error sending notification to {target_user_id}: {e}", exc_info=True)
