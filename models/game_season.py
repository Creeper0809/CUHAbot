"""Balance season and per-user immutable progress archives."""
from tortoise import fields, models


class GameSeason(models.Model):
    id = fields.CharField(pk=True, max_length=64)
    profile_version = fields.CharField(max_length=32)
    started_at = fields.DatetimeField(auto_now_add=True)
    ended_at = fields.DatetimeField(null=True)
    is_active = fields.BooleanField(default=True)
    backup_path = fields.TextField()

    class Meta:
        table = "game_season"


class SeasonProgressArchive(models.Model):
    id = fields.BigIntField(pk=True)
    season = fields.ForeignKeyField("models.GameSeason", related_name="archives", on_delete=fields.RESTRICT)
    user = fields.ForeignKeyField("models.User", related_name="season_archives", on_delete=fields.RESTRICT)
    discord_id = fields.BigIntField()
    snapshot = fields.JSONField()
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "season_progress_archive"
        unique_together = (("season", "user"),)
