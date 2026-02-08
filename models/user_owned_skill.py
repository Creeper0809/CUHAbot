"""
UserOwnedSkill 모델 정의

사용자가 소유한 스킬과 수량을 관리합니다.
스킬 덱에 장착 시 수량이 소모됩니다.
"""
from tortoise import models, fields


class UserOwnedSkill(models.Model):
    """
    사용자 스킬 소유 모델

    - 스킬은 상점에서 구매하거나 던전에서 획득
    - 덱에 장착 시 수량 소모 (10슬롯 = 10개 필요)
    - 장착 해제 시 수량 복구
    """

    id = fields.BigIntField(pk=True)
    user = fields.ForeignKeyField(
        "models.User",
        related_name="owned_skills",
        on_delete=fields.CASCADE
    )
    skill = fields.ForeignKeyField(
        "models.Skill_Model",
        related_name="owned_by",
        on_delete=fields.CASCADE
    )
    quantity = fields.IntField(default=0)
    """총 보유 수량 (장착된 수량 + 미장착 수량)"""

    equipped_count = fields.IntField(default=0)
    """현재 덱에 장착된 수량"""

    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "user_owned_skill"
        unique_together = [("user", "skill")]

    @property
    def available_count(self) -> int:
        """장착 가능한 수량 (보유 - 장착)"""
        return self.quantity - self.equipped_count
