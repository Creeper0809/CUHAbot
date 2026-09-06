"""Additive PostgreSQL schema migration for Balance V2."""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
from tortoise import Tortoise

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
    "ALTER TABLE monster ADD COLUMN IF NOT EXISTS ap_defense INT NOT NULL DEFAULT 0",
    "ALTER TABLE monster ADD COLUMN IF NOT EXISTS accuracy INT NOT NULL DEFAULT 95",
    "ALTER TABLE monster ADD COLUMN IF NOT EXISTS evasion INT NOT NULL DEFAULT 5",
    "ALTER TABLE monster ADD COLUMN IF NOT EXISTS phase_config JSONB NOT NULL DEFAULT '{}'::jsonb",
    "ALTER TABLE monster ALTER COLUMN speed SET DEFAULT 100",
    "ALTER TABLE users ALTER COLUMN attack SET DEFAULT 15",
    "ALTER TABLE users ALTER COLUMN ap_attack SET DEFAULT 15",
    "ALTER TABLE users ALTER COLUMN defense SET DEFAULT 8",
    "ALTER TABLE users ALTER COLUMN ap_defense SET DEFAULT 8",
    "ALTER TABLE users ALTER COLUMN speed SET DEFAULT 100",
    "ALTER TABLE users ALTER COLUMN accuracy SET DEFAULT 95",
    """
    CREATE TABLE IF NOT EXISTS game_season (
        id VARCHAR(64) PRIMARY KEY,
        profile_version VARCHAR(32) NOT NULL,
        started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        ended_at TIMESTAMPTZ NULL,
        is_active BOOLEAN NOT NULL DEFAULT TRUE,
        backup_path TEXT NOT NULL
    )
    """,
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_game_season_active ON game_season (is_active) WHERE is_active",
    """
    CREATE TABLE IF NOT EXISTS season_progress_archive (
        id BIGSERIAL PRIMARY KEY,
        season_id VARCHAR(64) NOT NULL REFERENCES game_season(id) ON DELETE RESTRICT,
        user_id INT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
        discord_id BIGINT NOT NULL,
        snapshot JSONB NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        CONSTRAINT uq_season_progress_archive UNIQUE (season_id, user_id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_season_archive_discord ON season_progress_archive(discord_id)",
    """
    CREATE TABLE IF NOT EXISTS game_telemetry_event (
        id BIGSERIAL PRIMARY KEY,
        event_type VARCHAR(48) NOT NULL,
        user_id INT NULL REFERENCES users(id) ON DELETE SET NULL,
        guild_id BIGINT NULL,
        content_type VARCHAR(32) NULL,
        run_nonce VARCHAR(96) NULL,
        level INT NULL,
        metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_game_telemetry_type_time ON game_telemetry_event(event_type, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_game_telemetry_content_time ON game_telemetry_event(content_type, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_game_telemetry_user_time ON game_telemetry_event(user_id, created_at)",
)


async def migrate() -> None:
    await Tortoise.init(db_url=database_url(), modules={"models": ["models"]})
    connection = Tortoise.get_connection("default")
    for statement in STATEMENTS:
        await connection.execute_query(statement)
    await Tortoise.close_connections()


if __name__ == "__main__":
    asyncio.run(migrate())
    print("Balance V2 migration complete")
