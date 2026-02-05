from enum import Enum
from tortoise import fields, models

class GradeEnum(str, Enum):
    S = 'S'
    A = 'A'
    B = 'B'
    C = 'C'
    D = 'D'

class ItemGradeProbability(models.Model):
    id = fields.IntField(pk=True)
    cheat_id = fields.IntField(null=True)
    grade = fields.CharField(max_length=1, null=True, enum=GradeEnum)
    probability = fields.IntField(null=True)
    grade_idx = fields.IntField(null=True)

    def __str__(self):
        return f"Grade {self.grade} (Index: {self.grade_idx})"

    class Meta:
        table = "item_grade_probability"