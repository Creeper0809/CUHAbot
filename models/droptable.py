from tortoise import models, fields


class Droptable(models.Model):
    id = fields.IntField(pk=True)
    drop_monster = fields.IntField(null=True)
    probability = fields.FloatField(null=True)
    item = fields.ForeignKeyField(
        'models.Item',
        related_name='droptable_entries',
        null=True,
        db_constraint=False  # 기존 데이터 호환성을 위해
    )
    # 하위 호환성을 위해 item_id는 유지 (item.id로 자동 매핑됨)

    class Meta:
        table = "droptable"
