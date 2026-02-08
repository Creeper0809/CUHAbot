"""
UserInventory 모델 정의

사용자의 소지품(아이템)을 관리합니다.
"""
from tortoise import models, fields


class UserInventory(models.Model):
    """
    사용자 인벤토리 모델

    - 소비 아이템은 quantity로 스택 (grade=0)
    - 장비 아이템은 인스턴스 등급별 개별 관리
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

    # 인스턴스 등급 (0=소비품/미지정, 1=D ~ 8=신화)
    instance_grade = fields.IntField(default=0)
    # 특수 효과 JSON (A등급 이상에서 부여)
    # 예: [{"type": "lifesteal", "value": 3}, {"type": "crit_rate", "value": 5}]
    special_effects = fields.JSONField(null=True)

    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "user_inventory"
        unique_together = [("user", "item", "enhancement_level", "instance_grade")]
