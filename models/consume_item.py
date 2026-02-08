from tortoise import models, fields
from typing import Dict, Optional
from enum import Enum

class ConsumeStatKey(Enum):
    HP_RECOVERY = ("hp_recovery", "HP 회복량")

    def __init__(self, key: str, display: str):
        self._key = key
        self._display = display

    @property
    def key(self) -> str:
        return self._key

    @property
    def display(self) -> str:
        return self._display

class ConsumeItem(models.Model):
    id = fields.IntField(pk=True)
    item = fields.ForeignKeyField(
        'models.Item',
        related_name='consume_item',
        source_field='consume_id',
        to_field='id',
        unique=True
    )
    amount = fields.IntField()  # HP 회복량

    # 버프 효과
    buff_type = fields.CharField(max_length=50, null=True)  # attack, defense, speed, etc.
    buff_amount = fields.IntField(null=True)  # 버프 수치
    buff_duration = fields.IntField(null=True)  # 지속 시간 (턴)

    # 디버프 해제
    cleanse_debuff = fields.BooleanField(default=False)

    # 투척 아이템 (전투 중 사용 가능)
    throwable_damage = fields.IntField(null=True)  # 투척 데미지

    class Meta:
        table = "consume_item"

    @property
    def raw_stats(self) -> Dict[ConsumeStatKey, Optional[int]]:
        return {
            ConsumeStatKey.HP_RECOVERY: self.amount
        }

    async def apply_to_embed(self, embed) -> None:
        from resources.item_emoji import ItemEmoji
        
        stats = {k: v for k, v in self.raw_stats.items() if v is not None and v != 0}
        for stat_key, stat_value in stats.items():
            emoji = ItemEmoji.get_stat_emoji(stat_key.key)
            embed.add_field(
                name=f"{stat_key.display} {emoji}",
                value=f"```      {stat_value}      ```",
                inline=True
            )

    def __str__(self):
        return f"Consume {self.id}"