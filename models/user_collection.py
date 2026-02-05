"""
UserCollection 모델 정의

유저가 발견/획득한 아이템, 스킬, 몬스터를 기록합니다.
"""
from enum import Enum
from tortoise import models, fields


class CollectionType(str, Enum):
    """도감 항목 타입"""
    ITEM = "ITEM"
    SKILL = "SKILL"
    MONSTER = "MONSTER"


class UserCollection(models.Model):
    """
    유저 도감 모델

    유저가 한 번이라도 획득/조우한 항목을 기록합니다.
    """

    id = fields.BigIntField(pk=True)
    user = fields.ForeignKeyField(
        "models.User",
        related_name="collections",
        on_delete=fields.CASCADE
    )
    collection_type = fields.CharEnumField(CollectionType)
    target_id = fields.IntField()  # Item.id, Skill_Model.id, Monster.id
    first_obtained_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "user_collection"
        unique_together = [("user", "collection_type", "target_id")]
