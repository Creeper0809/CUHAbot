from tortoise import models, fields
from enum import IntEnum

class EquipPos(models.Model):
    id = fields.IntField(pk=True)
    pos_name = fields.CharField(max_length=50, null=True)
    description = fields.CharField(max_length=50, null=True)

    class Meta:
        table = "equip_pos"

    def __str__(self):
        return self.description

class EquipPosition(IntEnum):
    HEAD = 1      # 머리
    CHEST = 2     # 흉갑
    BOOTS = 3     # 신발
    WEAPON = 4    # 무기
    SUB_WEAPON = 5  # 보조무기

    @classmethod
    def get_korean_name(cls, value):
        names = {
            cls.HEAD: "머리",
            cls.CHEST: "흉갑",
            cls.BOOTS: "신발",
            cls.WEAPON: "무기",
            cls.SUB_WEAPON: "보조무기"
        }
        return names.get(value, "알 수 없음")