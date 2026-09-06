#!/usr/bin/env python3
"""Additive PostgreSQL migration for roguelike and box reveal state."""

from __future__ import annotations

import asyncio
import os
import sys

from dotenv import load_dotenv
from tortoise import Tortoise

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
load_dotenv()


async def init_db() -> None:
    db_url = (
        f"postgres://{os.getenv('DATABASE_USER')}:{os.getenv('DATABASE_PASSWORD')}@"
        f"{os.getenv('DATABASE_URL')}:{os.getenv('DATABASE_PORT')}/{os.getenv('DATABASE_TABLE')}"
    )
    await Tortoise.init(db_url=db_url, modules={"models": ["models"]})


async def migrate() -> None:
    conn = Tortoise.get_connection("default")
    await conn.execute_script(
        """
        CREATE TABLE IF NOT EXISTS guild_game_settings (
            guild_id BIGINT PRIMARY KEY,
            roguelike_enabled BOOLEAN NULL,
            brag_channel_id BIGINT NULL,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS user_box_pity (
            id BIGSERIAL PRIMARY KEY,
            pity_group VARCHAR(16) NOT NULL,
            failure_count INTEGER NOT NULL DEFAULT 0 CHECK (failure_count >= 0),
            last_opened_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            CONSTRAINT uq_user_box_pity_user_group UNIQUE (user_id, pity_group)
        );

        CREATE TABLE IF NOT EXISTS box_open_receipt (
            id BIGSERIAL PRIMARY KEY,
            interaction_id VARCHAR(64) NOT NULL UNIQUE,
            box_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 1 CHECK (quantity > 0),
            outcomes JSONB NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_box_open_receipt_created_at
            ON box_open_receipt(created_at);
        CREATE INDEX IF NOT EXISTS idx_box_open_receipt_user_id
            ON box_open_receipt(user_id);

        CREATE TABLE IF NOT EXISTS dungeon_run_record (
            id BIGSERIAL PRIMARY KEY,
            dungeon_id INTEGER NOT NULL,
            best_clear_milliseconds BIGINT NOT NULL CHECK (best_clear_milliseconds > 0),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            CONSTRAINT uq_dungeon_run_record_user_dungeon UNIQUE (user_id, dungeon_id)
        );
        """
    )


async def main() -> None:
    try:
        await init_db()
        await migrate()
        print("roguelike/reward migration complete")
    finally:
        await Tortoise.close_connections()


if __name__ == "__main__":
    asyncio.run(main())
