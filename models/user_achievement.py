"""
유저 업적 모델
"""

from tortoise import fields
from tortoise.models import Model


class UserAchievement(Model):
    """
    유저 업적 진행 상태

    각 유저의 업적 달성 여부와 진행도를 추적합니다.
    """

    id = fields.IntField(pk=True)
    user = fields.ForeignKeyField("models.User", related_name="user_achievements")
    achievement = fields.ForeignKeyField("models.Achievement", related_name="user_progress")

    progress_current = fields.IntField(default=0)        # 현재 진행도
    progress_required = fields.IntField()                # 목표 진행도

    is_completed = fields.BooleanField(default=False)    # 완료 여부
    completed_at = fields.DatetimeField(null=True)       # 완료 시각

    class Meta:
        table = "user_achievement"
        unique_together = ("user", "achievement")

    def __str__(self) -> str:
        return (
            f"UserAchievement(user_id={self.user_id}, achievement_id={self.achievement_id}, "
            f"progress={self.progress_current}/{self.progress_required})"
        )

    @property
    def progress_percent(self) -> float:
        """진행률 (0.0 ~ 1.0)"""
        if self.progress_required == 0:
            return 1.0
        return min(1.0, self.progress_current / self.progress_required)

    @property
    def progress_percent_int(self) -> int:
        """진행률 (0 ~ 100)"""
        return int(self.progress_percent * 100)
