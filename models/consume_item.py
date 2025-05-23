from tortoise import models, fields

class ConsumeItem(models.Model):
    id = fields.IntField(pk=True)
    consume_id = fields.IntField()
    item = fields.ForeignKeyField(
        'models.Item',
        related_name='consume_item',
        source_field='consume_id',
        to_field='id',
        unique=True
    )
    amount = fields.IntField()

    class Meta:
        table = "consume_item"

    def get_stats(self):
        stats = {}
        if self.amount is not None and self.amount != 0:
            stats['HP 회복량'] = self.amount
        return stats

    def __str__(self):
        return f"Consume {self.id}"