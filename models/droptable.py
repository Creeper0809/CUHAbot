from tortoise import models, fields


class Droptable(models.Model):
    id = fields.IntField(pk=True)
    drop_monster = fields.IntField(null=True)
    probability = fields.FloatField(null=True)
    item_id = fields.IntField(null=True)

    class Meta:
        table = "droptable"
