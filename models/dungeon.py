from tortoise import models,fields


class Dungeon(models.Model):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=255)
    require_level = fields.IntField()
    description = fields.TextField()

    class Meta:
        table = "dungeon"