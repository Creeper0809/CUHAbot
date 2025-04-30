# inspect_signature.py
import os, asyncio, json
import discord
from dotenv import load_dotenv

load_dotenv()
TOKEN          = os.getenv("DISCORD_TOKEN")
APPLICATION_ID = int(os.getenv("APPLICATION_ID"))
GUILD_ID       = int(os.getenv("GUILD_ID"))

async def main():
    async with discord.Client(intents=discord.Intents.default()) as client:
        await client.login(TOKEN)
        cmds = await client.http.get_guild_commands(APPLICATION_ID, GUILD_ID)
        for c in cmds:
            if c["name"] == "user":  # 그룹이름
                print(json.dumps(c, ensure_ascii=False, indent=2))
                # 서브커맨드 리스트도 뽑아 보려면 다음 라인 추가:
                sub = await client.http.get_guild_command(
                    APPLICATION_ID, GUILD_ID, c["id"]
                )
                print("── 서브커맨드 옵션 ──")
                print(json.dumps(sub.get("options", []), ensure_ascii=False, indent=2))
        await client.close()

asyncio.run(main())
