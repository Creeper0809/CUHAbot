# bot.py
import os
import discord
from discord.app_commands import CommandSignatureMismatch
from discord.ext import commands, tasks
from dotenv import load_dotenv
from tortoise import Tortoise

import logging

from models.repos.static_cache import load_static_data
from resources.item_emoji import ItemEmoji  # 이모지 매니저 임포트
from service.event import EventBus
from service.achievement import AchievementProgressTracker
from service.tower.tower_season_service import start_season_reset_task

# 로그 기본 설정
logging.basicConfig(
    level=logging.INFO,  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

load_dotenv()

is_dev = os.getenv('DEV')
FORCE_SYNC = os.getenv('FORCE_SYNC') == "TRUE"
GUILD_ID = int(os.getenv('GUILD_ID') or 0)
GUILD_IDS = [GUILD_ID, 1470048099379576886]
if is_dev == "TRUE":
    APPLICATION_ID = int(os.getenv('DEV_APPLICATION_ID') or 0)
    TOKEN = os.getenv('DEV_DISCORD_TOKEN')
else:
    APPLICATION_ID = int(os.getenv('APPLICATION_ID') or 0)
    TOKEN = os.getenv('DISCORD_TOKEN')

DATABASE_URL = os.getenv('DATABASE_URL')
DATABASE_USER = os.getenv('DATABASE_USER')
DATABASE_PASSWORD = os.getenv('DATABASE_PASSWORD')
DATABASE_PORT = int(os.getenv('DATABASE_PORT') or 0)
DATABASE_TABLE = os.getenv('DATABASE_TABLE')

if not TOKEN or not APPLICATION_ID or not GUILD_ID:
    raise RuntimeError("환경변수 DISCORD_TOKEN, APPLICATION_ID, GUILD_ID를 .env에 모두 설정해주세요")

if not DATABASE_URL or not DATABASE_USER or not DATABASE_PASSWORD or not DATABASE_PORT or not DATABASE_TABLE:
    raise RuntimeError("데이터 베이스 설정에 필요한 정보가 부족합니다 .env를 확인해주세요")

class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.emojis = True  # 이모지 권한 추가
        intents.voice_states = True  # 음성 채널 상태 추적
        super().__init__(
            command_prefix="!",
            intents=intents,
            application_id=APPLICATION_ID
        )

        # 이벤트 시스템 (싱글톤)
        self.event_bus = None
        self.achievement_tracker = None

    async def setup_hook(self):
        should_sync = is_dev == "TRUE" or FORCE_SYNC

        if should_sync:
            self.tree.clear_commands(guild=None)
            logging.info("전역 커맨드 삭제 완료")

            for gid in [gid for gid in GUILD_IDS if gid]:
                try:
                    self.tree.clear_commands(guild=discord.Object(id=gid))
                except (discord.Forbidden, discord.NotFound, discord.HTTPException) as e:
                    logging.warning(
                        f"길드 {gid} 커맨드 삭제 실패: {e}"
                    )
                except Exception as e:
                    logging.error(
                        f"길드 {gid} 커맨드 삭제 중 예외 발생: {e}",
                        exc_info=True
                    )
            logging.info("길드 커맨드 삭제 완료")
        else:
            logging.info("커맨드 삭제/동기화를 건너뜁니다 (FORCE_SYNC=TRUE 또는 DEV=TRUE에서만 수행)")

        for fn in os.listdir("./cogs"):
            if fn.endswith(".py"):
                await self.load_extension(f"cogs.{fn[:-3]}")
                logging.info(f"Loaded cogs.{fn[:-3]}")

        if should_sync:
            for gid in [gid for gid in GUILD_IDS if gid]:
                try:
                    guild_synced = await self.tree.sync(guild=discord.Object(id=gid))
                    logging.info(f"길드 {gid}: {len(guild_synced)}개 synced")
                except (discord.Forbidden, discord.NotFound, discord.HTTPException) as e:
                    logging.warning(
                        f"길드 {gid} 커맨드 동기화 실패: {e}"
                    )
                except Exception as e:
                    logging.error(
                        f"길드 {gid} 커맨드 동기화 중 예외 발생: {e}",
                        exc_info=True
                    )


    async def init_db(self):
        await Tortoise.init(
            db_url=f"postgres://{DATABASE_USER}:{DATABASE_PASSWORD}@{DATABASE_URL}:{DATABASE_PORT}/{DATABASE_TABLE}",
            modules={"models": ["models"]}
        )

        # NOTE: generate_schemas() 제거됨
        # 모든 테이블은 마이그레이션 스크립트로 생성됨
        # generate_schemas()는 기존 테이블을 재생성하여 수동 추가한 컬럼을 날림

        await load_static_data()

    @tasks.loop(minutes=5)
    async def process_auction_expirations(self):
        """
        5분마다 만료된 경매/구매 주문 처리

        - 만료된 경매: 입찰 있으면 최고 입찰자에게 낙찰, 없으면 EXPIRED 처리
        - 만료된 구매 주문: 에스크로 골드 환불
        """
        try:
            from service.auction.auction_service import AuctionService

            expired_listings = await AuctionService.process_expired_listings()
            expired_orders = await AuctionService.process_expired_buy_orders()

            if expired_listings > 0 or expired_orders > 0:
                logging.info(
                    f"경매 만료 처리 완료: 리스팅 {expired_listings}건, 구매 주문 {expired_orders}건"
                )
        except Exception as e:
            logging.error(f"경매 만료 처리 중 오류: {e}", exc_info=True)

    @process_auction_expirations.before_loop
    async def before_auction_expiration_loop(self):
        """루프 시작 전 봇이 준비될 때까지 대기"""
        await self.wait_until_ready()

    async def on_ready(self):
        logging.info("데이터 베이스 연결 시작")
        await self.init_db()
        logging.info("데이터 베이스 연결 완료")

        # 이모지 초기화
        try:
            ItemEmoji.initialize(self)
            logging.info("이모지 초기화 완료")
        except Exception as e:
            logging.error(f"이모지 초기화 실패: {e}")

        # 이벤트 시스템 초기화
        try:
            self.event_bus = EventBus()
            self.achievement_tracker = AchievementProgressTracker(self.event_bus)
            logging.info("이벤트 시스템 및 업적 추적기 초기화 완료")
        except Exception as e:
            logging.error(f"이벤트 시스템 초기화 실패: {e}")

        # 경매 만료 처리 루프 시작
        if not self.process_auction_expirations.is_running():
            self.process_auction_expirations.start()
            logging.info("경매 만료 처리 루프 시작 (5분 간격)")

        await start_season_reset_task()
        logging.info("주간 타워 시즌 리셋 태스크 시작")

        logging.info(f"Logged in as {self.user} (ID: {self.user.id})")

    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState
    ):
        """
        음성 채널 상태 변경 이벤트 핸들러

        사용자가 음성 채널에 입장/퇴장/이동할 때 호출됩니다.
        """
        from service.voice_channel.voice_channel_service import voice_channel_service
        from service.voice_channel.instance_events import handle_voice_state_change
        from service.session import get_session, set_voice_channel

        user_id = member.id

        # Case 1: 퇴장 (before에는 있었지만 after에는 없음)
        if before.channel and not after.channel:
            logging.info(f"User {user_id} left voice channel {before.channel.id}")
            await voice_channel_service.user_left_channel(user_id)
            await handle_voice_state_change(user_id, left_channel=True)
            set_voice_channel(user_id, None)

        # Case 2: 입장 (before에는 없었지만 after에는 있음)
        elif not before.channel and after.channel:
            logging.info(f"User {user_id} joined voice channel {after.channel.id}")
            await voice_channel_service.user_joined_channel(user_id, after.channel.id)
            await handle_voice_state_change(user_id, joined_channel=after.channel.id)
            set_voice_channel(user_id, after.channel.id)

        # Case 3: 이동 (before와 after 채널이 다름)
        elif before.channel and after.channel and before.channel.id != after.channel.id:
            logging.info(f"User {user_id} moved from {before.channel.id} to {after.channel.id}")
            await voice_channel_service.user_left_channel(user_id)
            await voice_channel_service.user_joined_channel(user_id, after.channel.id)
            await handle_voice_state_change(user_id, moved_to=after.channel.id)
            set_voice_channel(user_id, after.channel.id)

if __name__ == "__main__":
    bot = MyBot()
    @bot.tree.error
    async def on_app_command_error(interaction: discord.Interaction, error):
        if isinstance(error, CommandSignatureMismatch):
            await interaction.response.defer(ephemeral=True, thinking=True)
            guild_obj = discord.Object(id=interaction.guild_id) if interaction.guild_id else discord.Object(id=GUILD_ID)
            synced = await bot.tree.sync(guild=guild_obj)
            return await interaction.followup.send(
                f"⚠️ 명령 시그니처가 갱신되어 `{', '.join(c.name for c in synced)}` 명령어를 재등록했습니다 .\n "
                "다시 시도해 주세요.",
                ephemeral=True
            )
        raise error

    bot.run(TOKEN)