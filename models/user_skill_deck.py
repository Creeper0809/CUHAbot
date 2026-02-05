"""
UserSkillDeck 모델 정의

사용자의 스킬 덱(10슬롯)을 관리합니다.
"""
from tortoise import models, fields

from config import SKILL_DECK_SIZE


class UserSkillDeck(models.Model):
    """
    사용자 스킬 덱 모델

    - 총 10개 슬롯 (0-9)
    - 같은 스킬을 여러 슬롯에 장착 가능
    - 모든 슬롯이 채워져야 전투 가능
    """

    id = fields.BigIntField(pk=True)
    user = fields.ForeignKeyField(
        "models.User",
        related_name="skill_deck",
        on_delete=fields.CASCADE
    )
    slot_index = fields.IntField()  # 0-9
    skill = fields.ForeignKeyField(
        "models.Skill_Model",
        related_name="deck_slots",
        on_delete=fields.CASCADE
    )

    class Meta:
        table = "user_skill_deck"
        unique_together = [("user", "slot_index")]

    @classmethod
    def get_max_slots(cls) -> int:
        """최대 슬롯 수 반환"""
        return SKILL_DECK_SIZE
