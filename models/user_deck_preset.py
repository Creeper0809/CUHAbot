"""
UserDeckPreset 모델 정의

사용자의 커스텀 스킬 덱 프리셋을 관리합니다.
"""
from tortoise import models, fields


class UserDeckPreset(models.Model):
    """
    사용자 덱 프리셋 모델

    - 사용자당 최대 5개의 프리셋 저장 가능
    - 프리셋 이름과 10개 스킬 ID를 저장
    """

    id = fields.IntField(pk=True)
    user = fields.ForeignKeyField(
        "models.User",
        related_name="deck_presets",
        on_delete=fields.CASCADE
    )

    # 프리셋 정보
    name = fields.CharField(max_length=20)
    slot_0 = fields.IntField(default=0)
    slot_1 = fields.IntField(default=0)
    slot_2 = fields.IntField(default=0)
    slot_3 = fields.IntField(default=0)
    slot_4 = fields.IntField(default=0)
    slot_5 = fields.IntField(default=0)
    slot_6 = fields.IntField(default=0)
    slot_7 = fields.IntField(default=0)
    slot_8 = fields.IntField(default=0)
    slot_9 = fields.IntField(default=0)

    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "user_deck_presets"
        unique_together = [("user", "name")]

    def get_deck_list(self) -> list[int]:
        """프리셋을 리스트로 반환"""
        return [
            self.slot_0, self.slot_1, self.slot_2, self.slot_3, self.slot_4,
            self.slot_5, self.slot_6, self.slot_7, self.slot_8, self.slot_9
        ]

    @classmethod
    async def create_from_deck(
        cls,
        user,
        name: str,
        deck: list[int]
    ) -> "UserDeckPreset":
        """덱 리스트로부터 프리셋 생성"""
        return await cls.create(
            user=user,
            name=name,
            slot_0=deck[0] if len(deck) > 0 else 0,
            slot_1=deck[1] if len(deck) > 1 else 0,
            slot_2=deck[2] if len(deck) > 2 else 0,
            slot_3=deck[3] if len(deck) > 3 else 0,
            slot_4=deck[4] if len(deck) > 4 else 0,
            slot_5=deck[5] if len(deck) > 5 else 0,
            slot_6=deck[6] if len(deck) > 6 else 0,
            slot_7=deck[7] if len(deck) > 7 else 0,
            slot_8=deck[8] if len(deck) > 8 else 0,
            slot_9=deck[9] if len(deck) > 9 else 0,
        )

    @classmethod
    def get_max_presets(cls) -> int:
        """최대 프리셋 개수"""
        return 5
