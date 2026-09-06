"""Guild-scoped feature flags with safe fallbacks before migration."""

from __future__ import annotations

import os

from tortoise.exceptions import OperationalError

from models.game_system import GuildGameSettings


def _env_enabled(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().upper() in {"1", "TRUE", "YES", "ON"}


async def get_guild_settings(guild_id: int | None) -> GuildGameSettings | None:
    if not guild_id:
        return None
    try:
        return await GuildGameSettings.get_or_none(guild_id=guild_id)
    except OperationalError:
        return None


async def is_roguelike_enabled(guild_id: int | None) -> bool:
    settings = await get_guild_settings(guild_id)
    if settings and settings.roguelike_enabled is not None:
        return bool(settings.roguelike_enabled)
    return _env_enabled("ROGUELIKE_DUNGEON_DEFAULT_ENABLED", False)


def is_box_reveal_enabled() -> bool:
    return _env_enabled("BOX_REVEAL_ENABLED", False)


V4_FEATURE_FIELDS = {
    "itemization_v4": "itemization_v4_enabled",
    "farming_focus": "farming_focus_enabled",
    "crafting_v4": "crafting_v4_enabled",
    "build_presets_v4": "build_presets_v4_enabled",
    "set_effects_v4": "set_effects_v4_enabled",
}


async def is_v4_feature_enabled(guild_id: int | None, feature: str) -> bool:
    field = V4_FEATURE_FIELDS.get(feature)
    if not field:
        raise ValueError(f"unknown V4 feature: {feature}")
    settings = await get_guild_settings(guild_id)
    if settings and getattr(settings, field, None) is not None:
        return bool(getattr(settings, field))
    return _env_enabled(f"{feature.upper()}_ENABLED", False)


async def set_v4_feature_override(guild_id: int, feature: str, enabled: bool | None) -> GuildGameSettings:
    field = V4_FEATURE_FIELDS.get(feature)
    if not field:
        raise ValueError(f"unknown V4 feature: {feature}")
    settings, _ = await GuildGameSettings.get_or_create(guild_id=guild_id)
    setattr(settings, field, enabled)
    await settings.save(update_fields=[field, "updated_at"])
    return settings


async def set_roguelike_override(guild_id: int, enabled: bool | None) -> GuildGameSettings:
    settings, _ = await GuildGameSettings.get_or_create(guild_id=guild_id)
    settings.roguelike_enabled = enabled
    await settings.save(update_fields=["roguelike_enabled", "updated_at"])
    return settings


async def set_brag_channel(guild_id: int, channel_id: int | None) -> GuildGameSettings:
    settings, _ = await GuildGameSettings.get_or_create(guild_id=guild_id)
    settings.brag_channel_id = channel_id
    await settings.save(update_fields=["brag_channel_id", "updated_at"])
    return settings
