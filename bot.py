# bot.py
import os
import discord
from discord.app_commands import CommandSignatureMismatch
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

is_dev = os.getenv('DEV')
GUILD_ID = int(os.getenv('GUILD_ID') or 0)
if is_dev == "TRUE":
    APPLICATION_ID = int(os.getenv('DEV_APPLICATION_ID') or 0)
    TOKEN          = os.getenv('DEV_DISCORD_TOKEN')
else:
    APPLICATION_ID = int(os.getenv('APPLICATION_ID') or 0)
    TOKEN = os.getenv('DEV_DISCORD_TOKEN')


if not TOKEN or not APPLICATION_ID or not GUILD_ID:
    raise RuntimeError("환경변수 DISCORD_TOKEN, APPLICATION_ID, GUILD_ID를 .env에 모두 설정해주세요")

class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(
            command_prefix="!",
            intents=intents,
            application_id=APPLICATION_ID
        )

    async def setup_hook(self):
        # 1) 전역(Global) 커맨드 전부 삭제
        self.tree.clear_commands(guild=None)
        print("🗑 전역 커맨드 삭제 완료")

        # 2) 길드(GUILD_ID) 전용 커맨드 전부 삭제
        self.tree.clear_commands(guild=discord.Object(id=GUILD_ID))
        print("🗑 길드 커맨드 삭제 완료")

        # 3) Cog 로딩
        for fn in os.listdir("./cogs"):
            if fn.endswith(".py"):
                await self.load_extension(f"cogs.{fn[:-3]}")
                print(f"✅ Loaded cogs.{fn[:-3]}")

        # 4) 전역 커맨드 Sync (인자 없이 호출해야 전역이 갱신됩니다)
        global_synced = await self.tree.sync()
        print(f"🌐 전역 {len(global_synced)}개 re-synced:", [c.name for c in global_synced])

        # 5) 길드 커맨드 Sync
        guild_synced = await self.tree.sync(guild=discord.Object(id=GUILD_ID))
        print(f"🏷 길드 {len(guild_synced)}개 re-synced:", [c.name for c in guild_synced])

    async def on_ready(self):
        print(f"Logged in as {self.user} (ID: {self.user.id})")

if __name__ == "__main__":
    bot = MyBot()


    @bot.tree.error
    async def on_app_command_error(interaction: discord.Interaction, error):
        # 1) 시그니처 불일치 감지
        if isinstance(error, CommandSignatureMismatch):
            await interaction.response.defer(ephemeral=True, thinking=True)

            # 2) 문제 생긴 길드에서 전역이 아닌 “길드 전용”만 Sync
            synced = await bot.tree.sync(guild=discord.Object(id=GUILD_ID))

            # 3) 유저에게 안내
            return await interaction.followup.send(
                f"⚠️ 명령 시그니처가 갱신되어 `{', '.join(c.name for c in synced)}` 명령어를 재등록했습니다.\n"
                "다시 시도해 주세요.",
                ephemeral=True
            )

        # 그 외 에러는 원래 대로 핸들링
        raise error
    bot.run(TOKEN)
