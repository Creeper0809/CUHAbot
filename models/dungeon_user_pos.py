from tortoise import fields, models

class DungeonUserPos(models.Model):
    id = fields.IntField(pk=True)
    user = fields.ForeignKeyField('models.User', related_name='positions')
    equip = fields.ForeignKeyField('models.Item', related_name='equipped_positions', null=True)
    skill = fields.ForeignKeyField('models.Skill', related_name='equipped_positions', null=True)

    class Meta:
        table = "dungeon_user_pos"

    def __str__(self):
        return f"{self.user.name}의 장비: {self.equip.name if self.equip else 'None'}, 스킬: {self.skill.name if self.skill else 'None'}"