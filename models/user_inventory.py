"""
UserInventory 모델 정의

사용자의 소지품(아이템)을 관리합니다.
"""
from tortoise import models, fields


class UserInventory(models.Model):
    """
    사용자 인벤토리 모델

    - 소비 아이템은 quantity로 스택
    - 장비 아이템은 개별 관리 (강화 레벨별로 구분)
    """

    id = fields.BigIntField(pk=True)
    user = fields.ForeignKeyField(
        "models.User",
        related_name="inventory",
        on_delete=fields.CASCADE
    )
    item = fields.ForeignKeyField(
        "models.Item",
        related_name="owned_by",
        on_delete=fields.CASCADE
    )
    quantity = fields.IntField(default=1)

    # 장비 아이템 강화 정보 (소비 아이템은 0)
    enhancement_level = fields.IntField(default=0)
    is_blessed = fields.BooleanField(default=False)
    is_cursed = fields.BooleanField(default=False)

    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "user_inventory"
        unique_together = [("user", "item", "enhancement_level")]
