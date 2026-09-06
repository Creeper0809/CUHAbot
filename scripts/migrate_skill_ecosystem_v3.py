"""Idempotent PostgreSQL migration for Skill Ecosystem V3."""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from tortoise import Tortoise


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv()


def database_url() -> str:
    explicit = os.getenv("DATABASE_URL", "")
    if explicit.startswith(("postgres://", "postgresql://")):
        return explicit
    return (
        f"postgres://{os.getenv('DATABASE_USER')}:{os.getenv('DATABASE_PASSWORD')}"
        f"@{explicit}:{os.getenv('DATABASE_PORT', '5432')}/{os.getenv('DATABASE_TABLE')}"
    )


STATEMENTS = (
    "ALTER TABLE monster ADD COLUMN IF NOT EXISTS action_profile JSONB NOT NULL DEFAULT '{}'::jsonb",
    "CREATE INDEX IF NOT EXISTS idx_monster_action_profile_revision ON monster ((action_profile->>'revision'))",
)


async def migrate() -> None:
    await Tortoise.init(db_url=database_url(), modules={"models": ["models"]})
    connection = Tortoise.get_connection("default")
    try:
        for statement in STATEMENTS:
            await connection.execute_query(statement)
    finally:
        await Tortoise.close_connections()


if __name__ == "__main__":
    asyncio.run(migrate())
