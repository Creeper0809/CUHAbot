from tortoise import models, fields

class User(models.Model):
    id = fields.IntField(pk=True)
    username = fields.CharField(max_length=255)

    class Meta:
        table = "users"