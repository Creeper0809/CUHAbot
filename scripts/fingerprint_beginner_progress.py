"""Read-only content hashes for pre/post-release user-progress verification."""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tortoise import Tortoise
from scripts.migrate_roguelike_reward_system import init_db
from scripts.verify_beginner_upgrade import fingerprints


async def main():
    try:
        await init_db()
        print(json.dumps(await fingerprints(), sort_keys=True))
    finally:
        await Tortoise.close_connections()


if __name__ == "__main__":
    asyncio.run(main())
