"""Persistent settings and receipts for roguelike/reward systems."""

from tortoise import fields, models


class UserStarterRecovery(models.Model):
    """One-time starter grant and deferred out-of-session HP recovery receipt."""

    user = fields.OneToOneField("models.User", related_name="starter_recovery", pk=True)
    revision = fields.IntField(default=1)
    hp_recovered = fields.BooleanField(default=False)
    details = fields.JSONField(default=dict)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "user_starter_recovery"


class GuildGameSettings(models.Model):
    guild_id = fields.BigIntField(pk=True)
    roguelike_enabled = fields.BooleanField(null=True)
    brag_channel_id = fields.BigIntField(null=True)
    itemization_v4_enabled = fields.BooleanField(null=True)
    farming_focus_enabled = fields.BooleanField(null=True)
    crafting_v4_enabled = fields.BooleanField(null=True)
    build_presets_v4_enabled = fields.BooleanField(null=True)
    set_effects_v4_enabled = fields.BooleanField(null=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "guild_game_settings"


class UserBoxPity(models.Model):
    id = fields.BigIntField(pk=True)
    user = fields.ForeignKeyField(
        "models.User", related_name="box_pity", on_delete=fields.CASCADE
    )
    pity_group = fields.CharField(max_length=16)
    failure_count = fields.IntField(default=0)
    last_opened_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "user_box_pity"
        unique_together = (("user", "pity_group"),)


class BoxOpenReceipt(models.Model):
    id = fields.BigIntField(pk=True)
    interaction_id = fields.CharField(max_length=64, unique=True)
    user = fields.ForeignKeyField(
        "models.User", related_name="box_open_receipts", on_delete=fields.CASCADE
    )
    box_id = fields.IntField()
    quantity = fields.IntField(default=1)
    outcomes = fields.JSONField()
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "box_open_receipt"


class DungeonRunRecord(models.Model):
    id = fields.BigIntField(pk=True)
    user = fields.ForeignKeyField(
        "models.User", related_name="dungeon_run_records", on_delete=fields.CASCADE
    )
    dungeon_id = fields.IntField()
    best_clear_milliseconds = fields.BigIntField()
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "dungeon_run_record"
        unique_together = (("user", "dungeon_id"),)


class GameTelemetryEvent(models.Model):
    """Append-only balance/operations event used for live cohort analysis."""

    id = fields.BigIntField(pk=True)
    event_type = fields.CharField(max_length=48)
    user = fields.ForeignKeyField(
        "models.User", related_name="game_telemetry_events",
        null=True, on_delete=fields.SET_NULL,
    )
    guild_id = fields.BigIntField(null=True)
    content_type = fields.CharField(max_length=32, null=True)
    run_nonce = fields.CharField(max_length=96, null=True)
    level = fields.IntField(null=True)
    metrics = fields.JSONField(default=dict)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "game_telemetry_event"
        indexes = (("event_type", "created_at"), ("content_type", "created_at"), ("user", "created_at"))
