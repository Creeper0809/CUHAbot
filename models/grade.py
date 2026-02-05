from tortoise import models, fields

class Grade(models.Model):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=50, null=True)
    description = fields.CharField(max_length=50, null=True)

    class Meta:
        table = "grade"

    def __str__(self):
        return self.name