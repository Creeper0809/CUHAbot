from tortoise import models, fields


class DungeonSpawn(models.Model):
    id: int = fields.IntField(pk=True)
    monster_id: int = fields.IntField()
    dungeon_id: int = fields.IntField()
    prob : float = fields.FloatField()

    class Meta:
        table = "dungeon_spawn"

