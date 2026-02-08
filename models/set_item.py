"""
세트 아이템 시스템 모델

장비 아이템의 세트 구성과 세트 효과를 관리합니다.
"""
from tortoise import models, fields
from typing import Dict, Any


class SetItem(models.Model):
    """
    세트 아이템 정의

    예: 드래곤 세트, 화염 세트, 창조신 세트 등
    """
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=100, unique=True)
    description = fields.TextField(null=True)

    class Meta:
        table = "set_items"

    def __str__(self):
        return f"Set: {self.name}"


class SetItemMember(models.Model):
    """
    세트 구성원 (어떤 장비가 어떤 세트에 속하는지)

    예: '드래곤의 검'은 '드래곤 세트'에 속함
    """
    id = fields.IntField(pk=True)
    set_item = fields.ForeignKeyField(
        "models.SetItem",
        related_name="members",
        on_delete=fields.CASCADE
    )
    equipment_item = fields.ForeignKeyField(
        "models.EquipmentItem",
        related_name="set_membership",
        on_delete=fields.CASCADE
    )

    class Meta:
        table = "set_item_members"
        unique_together = ("set_item", "equipment_item")

    def __str__(self):
        return f"SetMember: {self.equipment_item_id} in {self.set_item_id}"


class SetEffect(models.Model):
    """
    세트 효과 정의

    예: 드래곤 세트 2개 착용 시 HP +200, 모든 저항 +10%
    """
    id = fields.IntField(pk=True)
    set_item = fields.ForeignKeyField(
        "models.SetItem",
        related_name="effects",
        on_delete=fields.CASCADE
    )
    pieces_required = fields.IntField()  # 2, 3, 4, 5, 6, 8
    effect_description = fields.TextField()
    effect_config = fields.JSONField()  # {"hp": 200, "all_resistance": 0.1, ...}

    class Meta:
        table = "set_effects"
        unique_together = ("set_item", "pieces_required")

    def get_stat_bonuses(self) -> Dict[str, Any]:
        """
        효과 설정에서 스탯 보너스 추출

        Returns:
            스탯 보너스 딕셔너리
        """
        if not self.effect_config:
            return {}

        # effect_config에서 스탯 관련 항목만 추출
        stats = {}
        for key, value in self.effect_config.items():
            # 특수 효과는 제외하고 순수 스탯만 포함
            if key not in ["special", "trigger", "condition"]:
                stats[key] = value

        return stats

    def __str__(self):
        return f"SetEffect: {self.set_item_id} ({self.pieces_required}개)"
