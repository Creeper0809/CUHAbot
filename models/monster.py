from tortoise import models, fields


class Monster(models.Model):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=255)
    description = fields.TextField()
    hp = fields.IntField()
    attack = fields.IntField()

    class Meta:
        table = "monster"