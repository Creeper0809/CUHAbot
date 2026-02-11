"""
경매 거래 내역 모델

가격 히스토리 조회를 위한 거래 기록입니다.
"""
from enum import Enum

from tortoise import fields, models


class AuctionSaleType(str, Enum):
    """판매 방식"""
    AUCTION = "auction"      # 입찰 경매
    BUYNOW = "buynow"       # 즉시 구매
    BUY_ORDER = "buy_order"  # 구매 주문 체결


class AuctionHistory(models.Model):
    """
    경매 거래 내역 (가격 히스토리용)

    - 각 (item_id, enhancement_level, instance_grade) 조합당 최근 10건만 유지
    - 클린업은 서비스 레이어에서 처리
    """

    id = fields.BigIntField(pk=True)

    # 아이템 정보
    item_id = fields.IntField()
    enhancement_level = fields.IntField(default=0)
    instance_grade = fields.IntField(default=0)

    # 거래 정보
    sale_price = fields.BigIntField()
    sale_type = fields.CharEnumField(AuctionSaleType)
    sold_at = fields.DatetimeField(auto_now_add=True)

    # 거래 당사자
    seller_id = fields.BigIntField()
    buyer_id = fields.BigIntField()

    class Meta:
        table = "auction_history"
        indexes = (
            ("item_id", "enhancement_level", "instance_grade", "sold_at"),
        )

    def __str__(self) -> str:
        return (
            f"History {self.id}: Item {self.item_id} "
            f"sold for {self.sale_price}G ({self.sale_type})"
        )
