"""
입찰 기록 모델

경매에 대한 입찰 정보를 관리합니다.
"""
from tortoise import fields, models


class AuctionBid(models.Model):
    """
    입찰 기록

    - 입찰 시 골드 차감 (에스크로)
    - 다른 사람이 더 높게 입찰하면 환불 (is_refunded=True)
    - 낙찰 시 is_refunded는 False 유지
    """

    id = fields.BigIntField(pk=True)

    auction = fields.ForeignKeyField(
        "models.AuctionListing",
        related_name="bids",
        on_delete=fields.CASCADE
    )

    bidder = fields.ForeignKeyField(
        "models.User",
        related_name="my_bids",
        on_delete=fields.CASCADE
    )

    bid_amount = fields.BigIntField()
    created_at = fields.DatetimeField(auto_now_add=True)

    # 에스크로: 입찰 시 골드 차감, 낙찰 실패 시 환불
    is_refunded = fields.BooleanField(default=False)

    class Meta:
        table = "auction_bid"
        indexes = (
            ("auction", "bid_amount"),  # 최고 입찰가 조회
            ("bidder", "is_refunded"),  # 내 입찰 조회
        )

    def __str__(self) -> str:
        return f"Bid {self.id}: {self.bid_amount}G on Auction {self.auction_id}"
