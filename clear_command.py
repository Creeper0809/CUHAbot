# clear_commands.py
import os
import asyncio
import discord
from dotenv import load_dotenv

load_dotenv()
TOKEN          = os.getenv("DISCORD_TOKEN")
APPLICATION_ID = int(os.getenv("APPLICATION_ID", 0))
GUILD_ID       = int(os.getenv("GUILD_ID", 0))

if not (TOKEN and APPLICATION_ID and GUILD_ID):
    raise RuntimeError("환경변수 DISCORD_TOKEN, APPLICATION_ID, GUILD_ID를 모두 설정해주세요")

async def main():
    # 1) Client를 async context manager로 열어서 자동으로 close() 되게 함
    async with discord.Client(intents=discord.Intents.default()) as client:
        # 2) 로그인
        await client.login(TOKEN)

        # 3) 전역(Global) 커맨드 모두 삭제
        await client.http.bulk_upsert_global_commands(APPLICATION_ID, [])
        print("✅ 전역 커맨드 삭제 완료")

        # 4) 길드(Guild) 커맨드 모두 삭제
        await client.http.bulk_upsert_guild_commands(APPLICATION_ID, GUILD_ID, [])
        print("✅ 길드 커맨드 삭제 완료")

if __name__ == "__main__":
    asyncio.run(main())
