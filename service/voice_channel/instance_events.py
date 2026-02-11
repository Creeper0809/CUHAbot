"""
공유 인스턴스 이벤트 핸들러

음성 채널 상태 변경 시 공유 인스턴스 가입/탈퇴 처리 및 알림을 담당합니다.
"""
import logging
from typing import Optional

from config.voice_channel import VOICE_CHANNEL

logger = logging.getLogger(__name__)


async def handle_voice_state_change(
    user_id: int,
    *,
    joined_channel: Optional[int] = None,
    left_channel: bool = False,
    moved_to: Optional[int] = None
) -> None:
    """
    음성 채널 상태 변경 시 공유 인스턴스 업데이트

    Args:
        user_id: 상태가 변경된 사용자 ID
        joined_channel: 입장한 채널 ID (입장 시)
        left_channel: 퇴장 여부 (퇴장 시 True)
        moved_to: 이동한 채널 ID (이동 시)
    """
    from service.session import get_session
    from service.voice_channel.shared_instance_manager import shared_instance_manager

    session = get_session(user_id)
    if not session or session.ended:
        return

    # 퇴장 또는 이동 시 기존 인스턴스 탈퇴
    if left_channel or moved_to:
        old_instance = await shared_instance_manager.leave_instance(user_id)
        if old_instance and VOICE_CHANNEL.NOTIFICATION_ENABLED:
            await _send_leave_notification(session, old_instance)

    # 입장 또는 이동 시 새 인스턴스 참여
    if (joined_channel or moved_to) and session.dungeon:
        target_channel = joined_channel or moved_to
        instance = await shared_instance_manager.join_instance(
            user_id,
            target_channel,
            session.dungeon.id
        )

        if VOICE_CHANNEL.NOTIFICATION_ENABLED:
            await _send_join_notification(session, instance)


async def _send_join_notification(session, instance) -> None:
    """
    인스턴스 입장 알림 전송

    Args:
        session: 입장한 사용자의 DungeonSession
        instance: SharedDungeonInstance
    """
    # 혼자만 있으면 알림 스킵 (처음 생성 시)
    if instance.get_session_count() <= 1:
        return

    from service.session import get_session as get_other_session

    user_name = session.user.get_name() if session.user else "Unknown"
    dungeon_name = session.dungeon.name if session.dungeon else "Unknown"

    notification_text = (
        f"📣 같은 음성 채널에서 **{user_name}** 님이 {dungeon_name}에 입장했습니다!\n"
        f"현재 탐험 중: {instance.get_session_count()}명"
    )

    # 같은 인스턴스의 다른 사용자들에게 알림
    for other_user_id in instance.session_ids:
        if other_user_id == session.user_id:
            continue

        other_session = get_other_session(other_user_id)
        if not other_session or not other_session.dm_message:
            continue

        try:
            await other_session.dm_message.channel.send(notification_text)
            logger.debug(f"Sent join notification to user {other_user_id}")
        except Exception as e:
            logger.warning(f"Failed to send join notification to user {other_user_id}: {e}")


async def _send_leave_notification(session, instance) -> None:
    """
    인스턴스 퇴장 알림 전송

    Args:
        session: 퇴장한 사용자의 DungeonSession
        instance: SharedDungeonInstance
    """
    # 빈 인스턴스면 알림 스킵
    if instance.is_empty():
        return

    from service.session import get_session as get_other_session

    user_name = session.user.get_name() if session.user else "Unknown"

    notification_text = (
        f"🚪 **{user_name}** 님이 던전을 떠났습니다.\n"
        f"현재 탐험 중: {instance.get_session_count()}명"
    )

    # 남은 사용자들에게 알림
    for other_user_id in instance.session_ids:
        if other_user_id == session.user_id:
            continue

        other_session = get_other_session(other_user_id)
        if not other_session or not other_session.dm_message:
            continue

        try:
            await other_session.dm_message.channel.send(notification_text)
            logger.debug(f"Sent leave notification to user {other_user_id}")
        except Exception as e:
            logger.warning(f"Failed to send leave notification to user {other_user_id}: {e}")
