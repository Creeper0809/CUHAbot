"""
경매 등록 모델

사용자가 등록한 경매 정보를 관리합니다.
"""
from datetime import datetime, timedelta, timezone
from enum import Enum

from tortoise import fields, models


class AuctionType(str, Enum):
    """경매 타입"""
    BID = "bid"          # 입찰 방식
    BUYNOW = "buynow"    # 즉시 구매


class AuctionStatus(str, Enum):
    """경매 상태"""
    ACTIVE = "active"       # 진행 중
    SOLD = "sold"          # 판매 완료
    EXPIRED = "expired"    # 기간 만료
    CANCELLED = "cancelled"  # 판매자 취소


class AuctionListing(models.Model):
    """
    경매 등록 정보

    - auction_type이 BID면 입찰 방식 (highest bidder wins)
    - auction_type이 BUYNOW면 즉시 구매 (fixed price)
    - inventory_item은 에스크로 역할 (is_locked 설정)
    - 판매 완료 시 inventory_item은 null로 설정
    """

    id = fields.BigIntField(pk=True)

    # 판매자 정보
    seller = fields.ForeignKeyField(
        "models.User",
        related_name="auction_listings",
        on_delete=fields.CASCADE
    )

    # 아이템 정보 (FK to UserInventory - 에스크로)
    inventory_item = fields.ForeignKeyField(
        "models.UserInventory",
        related_name="auction_listing",
        null=True,  # 판매 완료 시 null
        on_delete=fields.SET_NULL
    )

    # 아이템 스냅샷 (inventory_item 삭제 후에도 표시용)
    item_id = fields.IntField()
    item_name = fields.CharField(max_length=255)
    enhancement_level = fields.IntField(default=0)
    instance_grade = fields.IntField(default=0)
    is_blessed = fields.BooleanField(default=False)
    is_cursed = fields.BooleanField(default=False)
    special_effects = fields.JSONField(null=True)

    # 경매 설정
    auction_type = fields.CharEnumField(AuctionType)
    starting_price = fields.BigIntField()  # 시작가 (입찰) or 즉구가
    buyout_price = fields.BigIntField(null=True)  # 즉시 구매가 (입찰 모드만)
    current_price = fields.BigIntField()  # 현재가 (입찰은 최고 입찰가)

    # 시간
    created_at = fields.DatetimeField(auto_now_add=True)
    expires_at = fields.DatetimeField()

    # 상태
    status = fields.CharEnumField(AuctionStatus, default=AuctionStatus.ACTIVE)

    # 판매 완료 정보
    buyer_id = fields.BigIntField(null=True)  # 구매자 User.id
    sold_at = fields.DatetimeField(null=True)
    final_price = fields.BigIntField(null=True)

    class Meta:
        table = "auction_listing"
        indexes = (
            ("status", "expires_at"),  # 만료 처리 쿼리
            ("seller", "status"),      # 내 경매 조회
            ("status", "item_id"),     # 아이템별 검색
        )

    @property
    def is_expired(self) -> bool:
        """만료 여부"""
        return datetime.now(timezone.utc) > self.expires_at and self.status == AuctionStatus.ACTIVE

    @property
    def time_remaining(self) -> timedelta:
        """남은 시간"""
        return self.expires_at - datetime.now(timezone.utc)

    def __str__(self) -> str:
        return f"Auction {self.id}: {self.item_name} ({self.status})"
