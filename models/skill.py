from typing import Iterable

from tortoise import models, fields, BaseDBAsyncClient


class Skill_Model(models.Model):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=255)
    description = fields.TextField()
    config = fields.JSONField()

    class Meta:
        table = "skill"
