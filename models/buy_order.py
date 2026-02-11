"""
구매 주문 모델

역경매 - 구매자가 원하는 아이템과 가격을 제시합니다.
"""
from datetime import datetime, timedelta, timezone
from enum import Enum

from tortoise import fields, models


class BuyOrderStatus(str, Enum):
    """구매 주문 상태"""
    ACTIVE = "active"
    FULFILLED = "fulfilled"  # 체결 완료
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class BuyOrder(models.Model):
    """
    구매 주문 (역경매)

    - 구매자가 원하는 아이템 조건과 최대 가격 제시
    - 주문 시 max_price만큼 골드 차감 (에스크로)
    - 판매자가 조건에 맞는 아이템 등록 시 자동 매칭
    """

    id = fields.BigIntField(pk=True)

    buyer = fields.ForeignKeyField(
        "models.User",
        related_name="buy_orders",
        on_delete=fields.CASCADE
    )

    # 원하는 아이템 조건
    item_id = fields.IntField()
    min_enhancement_level = fields.IntField(default=0)
    max_enhancement_level = fields.IntField(default=99)
    min_instance_grade = fields.IntField(default=0)
    max_instance_grade = fields.IntField(default=8)

    # 가격
    max_price = fields.BigIntField()  # 최대 지불 가격

    # 에스크로: 주문 시 골드 차감
    escrowed_gold = fields.BigIntField()

    # 시간
    created_at = fields.DatetimeField(auto_now_add=True)
    expires_at = fields.DatetimeField()

    status = fields.CharEnumField(BuyOrderStatus, default=BuyOrderStatus.ACTIVE)

    # 체결 정보
    seller_id = fields.BigIntField(null=True)
    fulfilled_at = fields.DatetimeField(null=True)
    final_price = fields.BigIntField(null=True)

    class Meta:
        table = "buy_order"
        indexes = (
            ("status", "item_id"),     # 매칭 쿼리
            ("buyer", "status"),       # 내 주문 조회
        )

    @property
    def is_expired(self) -> bool:
        """만료 여부"""
        return datetime.now(timezone.utc) > self.expires_at and self.status == BuyOrderStatus.ACTIVE

    @property
    def time_remaining(self) -> timedelta:
        """남은 시간"""
        return self.expires_at - datetime.now(timezone.utc)

    def matches_item(
        self,
        item_id: int,
        enhancement: int,
        grade: int
    ) -> bool:
        """아이템이 주문 조건과 일치하는지 확인"""
        return (
            self.item_id == item_id
            and self.min_enhancement_level <= enhancement <= self.max_enhancement_level
            and self.min_instance_grade <= grade <= self.max_instance_grade
        )

    def __str__(self) -> str:
        return f"BuyOrder {self.id}: Item {self.item_id} (max {self.max_price}G)"
