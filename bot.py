# bot.py
import os
import discord
from discord.app_commands import CommandSignatureMismatch
from discord.ext import commands
from dotenv import load_dotenv
from tortoise import Tortoise

import logging

# 로그 기본 설정
logging.basicConfig(
    level=logging.INFO,  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

load_dotenv()

is_dev = os.getenv('DEV')
GUILD_ID = int(os.getenv('GUILD_ID') or 0)
if is_dev == "TRUE":
    APPLICATION_ID = int(os.getenv('DEV_APPLICATION_ID') or 0)
    TOKEN = os.getenv('DEV_DISCORD_TOKEN')
else:
    APPLICATION_ID = int(os.getenv('APPLICATION_ID') or 0)
    TOKEN = os.getenv('DEV_DISCORD_TOKEN')

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
        super().__init__(
            command_prefix="!",
            intents=intents,
            application_id=APPLICATION_ID
        )

    async def setup_hook(self):

        self.tree.clear_commands(guild=None)
        logging.info("전역 커맨드 삭제 완료")

        self.tree.clear_commands(guild=discord.Object(id=GUILD_ID))
        logging.info("길드 커맨드 삭제 완료")

        for fn in os.listdir("./cogs"):
            if fn.endswith(".py"):
                await self.load_extension(f"cogs.{fn[:-3]}")
                logging.info(f"Loaded cogs.{fn[:-3]}")

        guild_synced = await self.tree.sync(guild=discord.Object(id=GUILD_ID))
        logging.info(f"전역 {len(guild_synced)}개 re-synced: {[c.name for c in guild_synced]}")


    async def init_db(self):
        await Tortoise.init(
            db_url=f"mysql://{DATABASE_USER}:{DATABASE_PASSWORD}@{DATABASE_URL}:{DATABASE_PORT}/{DATABASE_TABLE}",
            modules={"models": ["models"]}
        )
        await Tortoise.generate_schemas()

    async def on_ready(self):
        logging.info("데이터 베이스 연결 시작")
        await self.init_db()
        logging.info("데이터 베이스 연결")
        logging.info(f"Logged in as {self.user} (ID: {self.user.id})")

if __name__ == "__main__":
    bot = MyBot()
    @bot.tree.error
    async def on_app_command_error(interaction: discord.Interaction, error):
        if isinstance(error, CommandSignatureMismatch):
            await interaction.response.defer(ephemeral=True, thinking=True)
            synced = await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
            return await interaction.followup.send(
                f"⚠️ 명령 시그니처가 갱신되어 `{', '.join(c.name for c in synced)}` 명령어를 재등록했습니다 .\n "
                "다시 시도해 주세요.",
                ephemeral=True
            )
        raise error

    bot.run(TOKEN)
