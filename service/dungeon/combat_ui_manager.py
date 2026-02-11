"""
전투 UI 관리자 (Combat UI Manager)

전투 메시지 생성 및 업데이트를 담당합니다.
"""
import logging
from collections import deque
from typing import TYPE_CHECKING, Optional

import discord

if TYPE_CHECKING:
    from models import User
    from service.dungeon.combat_context import CombatContext
    from service.session import DungeonSession

logger = logging.getLogger(__name__)


class CombatUIManager:
    """전투 UI 생성 및 업데이트 관리"""

    def __init__(self):
        """CombatUIManager 초기화"""
        pass

    async def send_initial_combat_ui(
        self,
        session: "DungeonSession",
        interaction: discord.Interaction,
        user: "User",
        context: "CombatContext",
        combat_log: deque[str]
    ) -> discord.Message:
        """
        초기 전투 UI를 리더 및 참가자들에게 전송

        Args:
            session: 던전 세션
            interaction: Discord 인터랙션
            user: 리더 유저
            context: 전투 컨텍스트
            combat_log: 전투 로그

        Returns:
            리더의 전투 메시지
        """
        from service.dungeon.dungeon_ui import create_battle_embed_multi

        embed = create_battle_embed_multi(user, context, combat_log, session.participants)

        # 리더에게 전투 UI 전송
        combat_message = await interaction.user.send(embed=embed)

        # 난입 참가자들에게도 전투 UI 전송
        session.participant_combat_messages.clear()
        if session.participants:
            for participant_id, participant in session.participants.items():
                try:
                    discord_user = await interaction.client.fetch_user(participant.discord_id)
                    participant_msg = await discord_user.send(embed=embed)
                    session.participant_combat_messages[participant_id] = participant_msg
                    logger.info(f"Combat UI sent to participant: {participant.discord_id}")
                except Exception as e:
                    logger.error(f"Failed to send combat UI to participant {participant_id}: {e}")

        return combat_message

    async def update_all_combat_messages(
        self,
        session: "DungeonSession",
        combat_message: discord.Message,
        user: "User",
        context: "CombatContext",
        combat_log: deque[str]
    ) -> None:
        """
        모든 참가자의 전투 UI 메시지 업데이트 (리더 + 난입자)

        Args:
            session: 던전 세션
            combat_message: 리더의 전투 메시지
            user: 리더 유저
            context: 전투 컨텍스트
            combat_log: 전투 로그
        """
        from service.dungeon.dungeon_ui import create_battle_embed_multi

        embed = create_battle_embed_multi(user, context, combat_log, session.participants)

        # 리더 메시지 업데이트
        try:
            await combat_message.edit(embed=embed)
        except Exception as e:
            logger.error(f"Failed to update leader combat message: {e}")

        # 참가자 메시지 업데이트
        for participant_msg in session.participant_combat_messages.values():
            try:
                await participant_msg.edit(embed=embed)
            except Exception as e:
                logger.error(f"Failed to update participant combat UI: {e}")

    async def send_ui_to_new_participants(
        self,
        session: "DungeonSession",
        user: "User",
        context: "CombatContext",
        combat_log: deque[str]
    ) -> None:
        """
        새로 추가된 난입자들에게 전투 UI 전송

        Args:
            session: 던전 세션
            user: 리더 유저
            context: 전투 컨텍스트
            combat_log: 전투 로그
        """
        from service.dungeon.dungeon_ui import create_battle_embed_multi

        if not session.participants:
            return

        for participant_id, participant in session.participants.items():
            # 이미 UI를 받은 참가자는 건너뛰기
            if participant_id in session.participant_combat_messages:
                continue

            try:
                discord_user = await session.discord_client.fetch_user(participant.discord_id)
                embed = create_battle_embed_multi(user, context, combat_log, session.participants)
                participant_msg = await discord_user.send(embed=embed)
                session.participant_combat_messages[participant_id] = participant_msg
                logger.info(f"Combat UI sent to new intervener: {participant.discord_id}")
            except Exception as e:
                logger.error(f"Failed to send combat UI to intervener {participant_id}: {e}")

    async def send_final_combat_result(
        self,
        session: "DungeonSession",
        combat_message: discord.Message,
        user: "User",
        context: "CombatContext",
        combat_log: deque[str]
    ) -> None:
        """
        최종 전투 결과 UI 업데이트 (리더 + 참가자들)

        Args:
            session: 던전 세션
            combat_message: 리더의 전투 메시지
            user: 리더 유저
            context: 전투 컨텍스트
            combat_log: 전투 로그
        """
        from service.dungeon.dungeon_ui import create_battle_embed_multi

        final_embed = create_battle_embed_multi(user, context, combat_log, session.participants)

        # 리더 메시지 업데이트
        try:
            await combat_message.edit(embed=final_embed)
        except Exception as e:
            logger.error(f"Failed to update leader combat message: {e}")

        # 참가자 메시지 업데이트
        for participant_msg in session.participant_combat_messages.values():
            try:
                await participant_msg.edit(embed=final_embed)
            except Exception as e:
                logger.error(f"Failed to update participant combat message: {e}")

    async def cleanup_combat_messages(
        self,
        session: "DungeonSession",
        combat_message: Optional[discord.Message]
    ) -> None:
        """
        전투 메시지 정리 (리더 + 참가자들)

        Args:
            session: 던전 세션
            combat_message: 리더의 전투 메시지 (None 가능)
        """
        # 리더 전투 메시지 삭제
        if combat_message:
            try:
                await combat_message.delete()
            except Exception as e:
                logger.error(f"Failed to delete leader combat message: {e}")

        # 참가자 전투 메시지 삭제 및 참조 제거
        for participant_id, participant_msg in list(session.participant_combat_messages.items()):
            try:
                await participant_msg.delete()
            except Exception as e:
                logger.error(f"Failed to delete participant {participant_id} combat message: {e}")

        # 메시지 참조 명확히 제거 (메모리 누수 방지)
        session.participant_combat_messages.clear()
