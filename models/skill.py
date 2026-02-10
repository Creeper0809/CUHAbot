from typing import Iterable

from tortoise import models, fields, BaseDBAsyncClient


class Skill_Model(models.Model):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=255)
    description = fields.TextField()
    config = fields.JSONField()
    grade = fields.IntField(null=True)
    attribute = fields.CharField(max_length=20, default="무속성")
    """스킬 속성 (화염/냉기/번개/수속성/신성/암흑/무속성)"""
    keyword = fields.CharField(max_length=100, default="", null=True)
    """스킬 키워드 (슬래시 구분: "화염/화상/셋업")"""
    player_obtainable = fields.BooleanField(default=True)
    """플레이어 획득 가능 여부 (False면 드롭/도감 제외)"""
    acquisition_source = fields.CharField(max_length=50, default="", null=True)
    """획득처 (상점, 기본 지급, 던전 이름 등)"""

    class Meta:
        table = "skill"
