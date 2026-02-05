from tortoise import models

class BaseItem(models.Model):
    class Meta:
        abstract = True

    def add_stats_to_embed(self, embed, stats):
        # 스탯 정보를 embed에 추가
        stats = {k: v for k, v in stats.items() if v is not None and v != 0}
        for stat_key, stat_value in stats.items():
            from resources.item_emoji import ItemEmoji
            emoji = ItemEmoji.get_emoji(stat_key.key)
            embed.add_field(
                name=f"{stat_key.display} {emoji}",
                value=f"```      {stat_value}      ```",
                inline=True
            )
