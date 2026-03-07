"""
전투 알림 View

서버 채널에 게시되는 전투 알림 메시지에 "관전하기" 버튼을 제공합니다.
"""
import discord
import logging

from exceptions import SpectatorError, InterventionError
from service.session import ContentType

logger = logging.getLogger(__name__)


class CombatNotificationView(discord.ui.View):
    """전투 알림 메시지 View (관전하기 + 난입하기 버튼)"""

    def __init__(self, session, distance: int = 0, timeout: int = 300):
        """
        Args:
            session: DungeonSession
            distance: 거리 (exploration_step 차이, Phase 2)
            timeout: View 타임아웃 (초, 기본 5분)
        """
        super().__init__(timeout=timeout)
        self.session = session
        self.distance = distance

        # Phase 2: 거리에 따라 난입 버튼 커스터마이징
        self._customize_intervene_button()

        # 레이드는 난입 버튼 비활성화
        if session and getattr(session, "content_type", None) == ContentType.RAID:
            if len(self.children) >= 2:
                intervene_btn = self.children[1]
                intervene_btn.disabled = True
                intervene_btn.label = "🚫 레이드 난입 불가"
                intervene_btn.style = discord.ButtonStyle.secondary

    def _customize_intervene_button(self):
        """
        거리에 따라 난입 버튼 레이블/스타일 변경

        - ±3 스텝 (IMMEDIATE): "⚔️ 난입하기 (무료)", Primary
        - ±10 스텝 (NEARBY): "⚔️ 난입하기 (100G)", Secondary
        - >10 스텝 (FAR): "⚔️ 난입하기 (500G)", Danger
        """
        from service.notification.proximity_reward_calculator import get_intervention_cost

        cost = get_intervention_cost(self.distance)

        # 난입 버튼은 두 번째 버튼 (인덱스 1)
        if len(self.children) >= 2:
            intervene_btn = self.children[1]

            if cost == 0:
                intervene_btn.label = "⚔️ 난입하기 (무료)"
                intervene_btn.style = discord.ButtonStyle.primary
            elif cost <= 100:
                intervene_btn.label = f"⚔️ 난입하기 ({cost}G)"
                intervene_btn.style = discord.ButtonStyle.secondary
            else:
                intervene_btn.label = f"⚔️ 난입하기 ({cost}G)"
                intervene_btn.style = discord.ButtonStyle.danger

    @discord.ui.button(
        label="👀 관전하기",
        style=discord.ButtonStyle.primary,
        custom_id="spectate_button"
    )
    async def spectate_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        """관전하기 버튼 콜백"""
        try:
            from service.spectator.spectator_service import SpectatorService

            # 관전 시작
            await SpectatorService.start_spectating(
                interaction.user,
                self.session,
                interaction
            )

            await interaction.response.send_message(
                f"👀 {self.session.user.get_name()}님의 전투를 관전합니다!\\n"
                f"DM에서 실시간 전투를 확인하세요.",
                ephemeral=True
            )

        except SpectatorError as e:
            await interaction.response.send_message(
                f"❌ {e.message}",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Failed to start spectating: {e}", exc_info=True)
            await interaction.response.send_message(
                "❌ 관전을 시작할 수 없습니다.",
                ephemeral=True
            )

    @discord.ui.button(
        label="⚔️ 난입하기",
        style=discord.ButtonStyle.danger,
        custom_id="intervene_button"
    )
    async def intervene_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        """난입하기 버튼 콜백"""
        if self.session and getattr(self.session, "content_type", None) == ContentType.RAID:
            await interaction.response.send_message(
                "🚫 레이드 전투는 난입할 수 없습니다.",
                ephemeral=True
            )
            return

        try:
            from service.intervention.intervention_service import InterventionService

            # 난입 요청
            await InterventionService.request_intervention(
                interaction.user,
                self.session,
                interaction
            )

        except InterventionError as e:
            await interaction.response.send_message(
                f"❌ {e.message}",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Failed to request intervention: {e}", exc_info=True)
            await interaction.response.send_message(
                "❌ 난입 요청에 실패했습니다.",
                ephemeral=True
            )

    async def on_timeout(self):
        """타임아웃 시 버튼 비활성화"""
        for child in self.children:
            child.disabled = True

        # 메시지 업데이트 (시도만, 실패해도 무시)
        try:
            if hasattr(self, 'message') and self.message:
                await self.message.edit(view=self)
        except:
            pass
