"""
UserTowerProgress 모델 정의

주간 타워 진행도를 저장합니다.
"""
from tortoise import models, fields


class UserTowerProgress(models.Model):
    """주간 타워 진행도"""

    id = fields.IntField(pk=True)
    user = fields.ForeignKeyField(
        "models.User",
        related_name="tower_progress",
        on_delete=fields.CASCADE,
    )
    season_id = fields.IntField(default=1)
    highest_floor_reached = fields.IntField(default=0)
    current_floor = fields.IntField(default=0)
    rewards_claimed = fields.JSONField(default=list)
    tower_coins = fields.IntField(default=0)
    last_attempt_time = fields.DatetimeField(null=True)
    season_start_time = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "user_tower_progress"
        unique_together = (("user", "season_id"),)
