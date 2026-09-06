"""배경 작업 Cog - 주기적 데이터 정리 (Phase 5)"""
import logging
from discord.ext import commands, tasks

logger = logging.getLogger(__name__)


class BackgroundTasksCog(commands.Cog):
    """주기적 배경 작업 관리"""

    def __init__(self, bot):
        self.bot = bot
        self.cleanup_combat_history.start()
        logger.info("BackgroundTasksCog initialized")

    def cog_unload(self):
        """Cog 언로드 시 작업 정지"""
        self.cleanup_combat_history.cancel()
        logger.info("BackgroundTasksCog unloaded")

    @tasks.loop(hours=6)
    async def cleanup_combat_history(self):
        """만료된 전투 기록 정리 (6시간마다)"""
        try:
            from service.combat_history.history_service import HistoryService

            deleted_count = await HistoryService.cleanup_expired_histories()

            if deleted_count > 0:
                logger.info(f"🧹 Cleaned up {deleted_count} expired combat histories")
            else:
                logger.debug("No expired combat histories to clean up")

            from service.item.box_open_service import BoxOpenService
            receipt_count = await BoxOpenService.cleanup_receipts(days=30)
            if receipt_count > 0:
                logger.info("Cleaned up %s expired box-open receipts", receipt_count)

            from service.telemetry import cleanup_game_events
            telemetry_count = await cleanup_game_events(days=180)
            if telemetry_count > 0:
                logger.info("Cleaned up %s expired gameplay telemetry events", telemetry_count)

        except Exception as e:
            logger.error(f"Failed to cleanup combat histories: {e}", exc_info=True)

    @cleanup_combat_history.before_loop
    async def before_cleanup(self):
        """봇 준비 대기"""
        await self.bot.wait_until_ready()
        logger.info("Background cleanup task ready")


async def setup(bot):
    """Cog 로드"""
    await bot.add_cog(BackgroundTasksCog(bot))
