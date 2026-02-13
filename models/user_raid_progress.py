"""
UserRaidProgress 모델 정의

주간 레이드 입장/클리어 진행도를 저장합니다.
"""
from tortoise import models, fields


class UserRaidProgress(models.Model):
    """주간 레이드 진행도"""

    id = fields.IntField(pk=True)
    user = fields.ForeignKeyField(
        "models.User",
        related_name="raid_progress",
        on_delete=fields.CASCADE,
    )
    raid_id = fields.IntField(index=True)
    week_key = fields.IntField(index=True)
    entries_used = fields.IntField(default=0)
    clears = fields.IntField(default=0)
    first_clear_reward_claimed = fields.BooleanField(default=False)
    best_clear_turns = fields.IntField(null=True)
    last_entered_at = fields.DatetimeField(null=True)
    last_cleared_at = fields.DatetimeField(null=True)

    class Meta:
        table = "user_raid_progress"
        unique_together = (("user", "raid_id", "week_key"),)
