"""
UserEquipment 모델 정의

사용자가 장착한 장비를 관리합니다.
"""
from enum import IntEnum

from tortoise import models, fields


class EquipmentSlot(IntEnum):
    """장비 슬롯 열거형 (9개 슬롯)"""

    WEAPON = 1       # 무기
    HELMET = 2       # 투구
    ARMOR = 3        # 갑옷
    GLOVES = 4       # 장갑
    BOOTS = 5        # 신발
    NECKLACE = 6     # 목걸이
    RING1 = 7        # 반지 1
    RING2 = 8        # 반지 2
    SUB_WEAPON = 9   # 보조무기

    @classmethod
    def get_korean_name(cls, slot: "EquipmentSlot") -> str:
        """슬롯의 한국어 이름 반환"""
        names = {
            cls.WEAPON: "무기",
            cls.HELMET: "투구",
            cls.ARMOR: "갑옷",
            cls.GLOVES: "장갑",
            cls.BOOTS: "신발",
            cls.NECKLACE: "목걸이",
            cls.RING1: "반지 1",
            cls.RING2: "반지 2",
            cls.SUB_WEAPON: "보조무기",
        }
        return names.get(slot, "알 수 없음")


class UserEquipment(models.Model):
    """
    사용자 장착 장비 모델

    - 각 슬롯당 하나의 장비만 장착 가능
    - inventory_item을 참조하여 강화 정보 유지
    """

    id = fields.IntField(pk=True)
    user = fields.ForeignKeyField(
        "models.User",
        related_name="equipped",
        on_delete=fields.CASCADE
    )
    slot = fields.IntEnumField(EquipmentSlot)
    inventory_item = fields.ForeignKeyField(
        "models.UserInventory",
        related_name="equipped_in",
        on_delete=fields.CASCADE
    )

    equipped_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "user_equipment"
        unique_together = [("user", "slot")]
