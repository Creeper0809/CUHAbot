from tortoise import models,fields


class Item(models.Model):
    id = fields.IntField(pk=True)
    attack = fields.IntField()

    class Meta:
        table = "item"
