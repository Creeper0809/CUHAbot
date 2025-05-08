from tortoise import models, fields

class User(models.Model):
    id = fields.IntField(pk=True)
    discord_id = fields.BigIntField()
    username = fields.CharField(max_length=255)
    password = fields.CharField(max_length=255)
    baekjoon_id = fields.CharField(max_length=255)
    gender = fields.CharField(max_length=255)
    cuha_point = fields.BigIntField()
    created_at = fields.DatetimeField(auto_now_add=True)
    user_role = fields.CharField(max_length=255)

    hp = fields.IntField(default=300)
    level = fields.IntField(default=1)
    now_hp = fields.IntField(default=300)
    attack = fields.IntField(default=10)

    class Meta:
        table = "users"
