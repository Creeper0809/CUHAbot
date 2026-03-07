"""
UserUltimateDeck 모델 정의

사용자의 궁극기 슬롯(1칸)과 발동 모드(수동/자동)를 저장합니다.
"""
from tortoise import models, fields


class UserUltimateDeck(models.Model):
    id = fields.BigIntField(pk=True)
    user = fields.ForeignKeyField(
        "models.User",
        related_name="ultimate_deck",
        on_delete=fields.CASCADE,
    )
    skill_id = fields.IntField(default=0)
    mode = fields.CharField(max_length=10, default="manual")

    class Meta:
        table = "user_ultimate_deck"
        unique_together = [("user",)]
