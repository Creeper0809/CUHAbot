#!/usr/bin/env python3
"""Additive PostgreSQL migration and authored-affix synchronization for V4."""
from __future__ import annotations

import asyncio
import csv
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
from tortoise import Tortoise

load_dotenv()


def database_url() -> str:
    host = os.getenv("DATABASE_URL", "")
    if host.startswith(("postgres://", "postgresql://")):
        return host
    return (
        f"postgres://{os.getenv('DATABASE_USER')}:{os.getenv('DATABASE_PASSWORD')}"
        f"@{host}:{os.getenv('DATABASE_PORT', '5432')}/{os.getenv('DATABASE_TABLE')}"
    )


SCHEMA = """
ALTER TABLE equipment_item ADD COLUMN IF NOT EXISTS set_key VARCHAR(64) NOT NULL DEFAULT '';
ALTER TABLE guild_game_settings ADD COLUMN IF NOT EXISTS itemization_v4_enabled BOOLEAN NULL;
ALTER TABLE guild_game_settings ADD COLUMN IF NOT EXISTS farming_focus_enabled BOOLEAN NULL;
ALTER TABLE guild_game_settings ADD COLUMN IF NOT EXISTS crafting_v4_enabled BOOLEAN NULL;
ALTER TABLE guild_game_settings ADD COLUMN IF NOT EXISTS build_presets_v4_enabled BOOLEAN NULL;
ALTER TABLE guild_game_settings ADD COLUMN IF NOT EXISTS set_effects_v4_enabled BOOLEAN NULL;

CREATE TABLE IF NOT EXISTS equipment_affix_definition (
    id VARCHAR(48) PRIMARY KEY, name VARCHAR(64) NOT NULL, family VARCHAR(32) NOT NULL,
    effect_group VARCHAR(48) NOT NULL, allowed_slots JSONB NOT NULL DEFAULT '[]'::jsonb,
    setup_tags JSONB NOT NULL DEFAULT '[]'::jsonb, payoff_tags JSONB NOT NULL DEFAULT '[]'::jsonb,
    runtime_key VARCHAR(48) NOT NULL, tier_values JSONB NOT NULL DEFAULT '{}'::jsonb,
    weight DOUBLE PRECISION NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS user_equipment_affix (
    id BIGSERIAL PRIMARY KEY, inventory_item_id BIGINT NOT NULL REFERENCES user_inventory(id) ON DELETE CASCADE,
    affix_definition_id VARCHAR(48) NOT NULL REFERENCES equipment_affix_definition(id) ON DELETE RESTRICT,
    position INT NOT NULL, tier INT NOT NULL CHECK(tier BETWEEN 1 AND 5), value DOUBLE PRECISION NOT NULL,
    quality_percentile INT NOT NULL DEFAULT 0 CHECK(quality_percentile BETWEEN 0 AND 100),
    CONSTRAINT uq_user_equipment_affix_position UNIQUE(inventory_item_id, position)
);
CREATE INDEX IF NOT EXISTS idx_equipment_affix_search ON user_equipment_affix(affix_definition_id, tier, value);

CREATE TABLE IF NOT EXISTS equipment_provenance (
    id BIGSERIAL PRIMARY KEY, inventory_item_id BIGINT NOT NULL UNIQUE REFERENCES user_inventory(id) ON DELETE CASCADE,
    source_type VARCHAR(24) NOT NULL DEFAULT 'legacy', source_key VARCHAR(128) NOT NULL DEFAULT '',
    original_owner_id INT NULL, crafted BOOLEAN NOT NULL DEFAULT FALSE, reforge_count INT NOT NULL DEFAULT 0,
    acquired_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS user_crafting_wallet (
    id BIGSERIAL PRIMARY KEY, user_id INT NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    equipment_essence INT NOT NULL DEFAULT 0, source_seals JSONB NOT NULL DEFAULT '{}'::jsonb,
    preservation_catalysts INT NOT NULL DEFAULT 0, recovery_cores JSONB NOT NULL DEFAULT '{}'::jsonb,
    equipment_storage INT NOT NULL DEFAULT 300 CHECK(equipment_storage BETWEEN 300 AND 600)
);
CREATE TABLE IF NOT EXISTS user_farm_progress (
    id BIGSERIAL PRIMARY KEY, user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    source_type VARCHAR(16) NOT NULL, source_key VARCHAR(128) NOT NULL, progress INT NOT NULL DEFAULT 0,
    seals_earned INT NOT NULL DEFAULT 0, target_item_id INT NULL, updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_user_farm_progress_source UNIQUE(user_id, source_type, source_key)
);
CREATE TABLE IF NOT EXISTS user_build_preset (
    id BIGSERIAL PRIMARY KEY, user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(24) NOT NULL, note VARCHAR(160) NOT NULL DEFAULT '', content_key VARCHAR(64) NOT NULL DEFAULT '',
    bonus_str INT NOT NULL DEFAULT 0, bonus_int INT NOT NULL DEFAULT 0, bonus_dex INT NOT NULL DEFAULT 0,
    bonus_vit INT NOT NULL DEFAULT 0, bonus_luk INT NOT NULL DEFAULT 0,
    skill_ids JSONB NOT NULL DEFAULT '[]'::jsonb, last_measurement JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_user_build_preset_name UNIQUE(user_id, name)
);
CREATE TABLE IF NOT EXISTS user_build_preset_item (
    id BIGSERIAL PRIMARY KEY, preset_id BIGINT NOT NULL REFERENCES user_build_preset(id) ON DELETE CASCADE,
    slot INT NOT NULL, inventory_item_id BIGINT NULL REFERENCES user_inventory(id) ON DELETE SET NULL,
    CONSTRAINT uq_user_build_preset_slot UNIQUE(preset_id, slot)
);
CREATE INDEX IF NOT EXISTS idx_build_preset_item_inventory ON user_build_preset_item(inventory_item_id);
CREATE TABLE IF NOT EXISTS user_loot_rule (
    id BIGSERIAL PRIMARY KEY, user_id INT NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    enabled BOOLEAN NOT NULL DEFAULT FALSE, max_grade INT NOT NULL DEFAULT 0,
    slots JSONB NOT NULL DEFAULT '[]'::jsonb, excluded_item_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    minimum_affix_tier INT NULL
);
CREATE TABLE IF NOT EXISTS equipment_action_receipt (
    id BIGSERIAL PRIMARY KEY, interaction_id VARCHAR(80) NOT NULL UNIQUE,
    user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE, action VARCHAR(24) NOT NULL,
    inventory_item_id BIGINT NULL, result JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_equipment_receipt_created ON equipment_action_receipt(created_at);
"""


async def migrate() -> None:
    await Tortoise.init(db_url=database_url(), modules={"models": ["models"]})
    conn = Tortoise.get_connection("default")
    await conn.execute_script(SCHEMA)
    from models import EquipmentItem
    with (ROOT / "data" / "items_equipment.csv").open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            await EquipmentItem.filter(item_id=int(row["ID"])).update(set_key=row.get("set_key", ""))
    from service.item.affix_service import backfill_existing_instances, sync_affix_definitions
    await sync_affix_definitions()
    result = await backfill_existing_instances()
    print(f"instance backfill: {result}")
    await Tortoise.close_connections()


if __name__ == "__main__":
    asyncio.run(migrate())
    print("Farming and Buildcraft V4 migration complete")
