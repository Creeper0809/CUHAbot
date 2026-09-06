#!/usr/bin/env python3
"""Additive starter repair receipt. No user progress is rewritten here."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.migrate_roguelike_reward_system import init_db
from tortoise import Tortoise


async def migrate():
    await Tortoise.get_connection("default").execute_script("""
        CREATE TABLE IF NOT EXISTS user_starter_recovery (
            user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
            revision INTEGER NOT NULL DEFAULT 1,
            hp_recovered BOOLEAN NOT NULL DEFAULT FALSE,
            details JSONB NOT NULL DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
    """)


async def main():
    try:
        await init_db()
        await migrate()
        print("Beginner receipt migration complete (no progress reset)")
    finally:
        await Tortoise.close_connections()


if __name__ == "__main__":
    asyncio.run(main())
