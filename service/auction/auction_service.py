"""
경매 서비스

경매 시스템의 핵심 비즈니스 로직을 제공합니다.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from tortoise.transactions import in_transaction

from config.multiplayer import AUCTION
from exceptions import (
    AuctionAlreadyEndedError,
    AuctionBidTooLowError,
    AuctionCannotCancelError,
    AuctionListingNotFoundError,
    AuctionSelfBidError,
    BuyOrderNotFoundError,
    CombatRestrictionError,
    InsufficientGoldError,
    ItemNotFoundError,
)
from models.auction_bid import AuctionBid
from models.auction_history import AuctionHistory, AuctionSaleType
from models.auction_listing import AuctionListing, AuctionStatus, AuctionType
from models.buy_order import BuyOrder, BuyOrderStatus
from models.item import ItemType
from models.user_inventory import UserInventory
from models.users import User
from service.item.inventory_service import InventoryService
from service.mail.mail_service import MailService
from service.session import get_session

logger = logging.getLogger(__name__)


class AuctionService:
    """경매 비즈니스 로직"""

    # =========================================================================
    # 등록 (Listing)
    # =========================================================================

    @staticmethod
    async def create_listing(
        user: User,
        inventory_id: int,
        auction_type: AuctionType,
        starting_price: int,
        buyout_price: Optional[int],
        duration_hours: int
    ) -> AuctionListing:
        """
        경매 등록

        Args:
            user: 판매자
            inventory_id: 인벤토리 아이템 ID
            auction_type: 경매 타입 (bid/buynow)
            starting_price: 시작가 (즉구면 즉구가)
            buyout_price: 즉시 구매가 (입찰 모드만, optional)
            duration_hours: 등록 기간 (시간)

        Returns:
            생성된 AuctionListing

        Raises:
            CombatRestrictionError: 전투 중
            ItemNotFoundError: 인벤토리 아이템 없음
            InsufficientGoldError: 등록 수수료 부족
            ValueError: 가격 또는 기간 유효하지 않음
        """
        # Guard: 전투 중 체크
        session = get_session(user.discord_id)
        if session and session.in_combat:
            raise CombatRestrictionError("경매 등록")

        # Guard: 인벤토리 아이템 존재 확인
        inventory_item = await UserInventory.filter(
            id=inventory_id,
            user=user
        ).prefetch_related("item").first()

        if not inventory_item:
            raise ItemNotFoundError(inventory_id)

        if inventory_item.is_locked:
            raise ValueError("이미 경매 등록된 아이템입니다")

        # Guard: 장착 중인 장비 체크
        if inventory_item.item.type == ItemType.EQUIP:
            from models.user_equipment import UserEquipment
            is_equipped = await UserEquipment.exists(
                user=user,
                inventory_item=inventory_item
            )
            if is_equipped:
                raise ValueError("장착 중인 장비는 경매에 등록할 수 없습니다")

        # Guard: 가격 검증
        if starting_price < AUCTION.MIN_LISTING_PRICE:
            raise ValueError(
                f"최소 등록 가격은 {AUCTION.MIN_LISTING_PRICE}G입니다"
            )

        if buyout_price and buyout_price <= starting_price:
            raise ValueError("즉시 구매가는 시작가보다 높아야 합니다")

        # Guard: 기간 검증
        if not (1 <= duration_hours <= AUCTION.MAX_LISTING_DURATION_HOURS):
            raise ValueError(
                f"등록 기간은 1~{AUCTION.MAX_LISTING_DURATION_HOURS}시간이어야 합니다"
            )

        # Transaction: 등록 수수료 차감 + 아이템 잠금 + 리스팅 생성
        listing_fee = int(starting_price * AUCTION.LISTING_FEE_PERCENT)

        if user.gold < listing_fee:
            raise InsufficientGoldError(listing_fee, user.gold)

        async with in_transaction() as conn:
            user.gold -= listing_fee
            await user.save(using_db=conn)

            inventory_item.is_locked = True
            await inventory_item.save(using_db=conn)

            expires_at = datetime.now(timezone.utc) + timedelta(hours=duration_hours)

            listing = await AuctionListing.create(
                seller=user,
                inventory_item=inventory_item,
                item_id=inventory_item.item.id,
                item_name=inventory_item.item.name,
                enhancement_level=inventory_item.enhancement_level,
                instance_grade=inventory_item.instance_grade,
                is_blessed=inventory_item.is_blessed,
                is_cursed=inventory_item.is_cursed,
                special_effects=inventory_item.special_effects,
                auction_type=auction_type,
                starting_price=starting_price,
                buyout_price=buyout_price,
                current_price=starting_price,
                expires_at=expires_at,
                using_db=conn
            )

        logger.info(
            f"User {user.id} created listing {listing.id} "
            f"({auction_type}, {starting_price}G, {duration_hours}h)"
        )

        # Post: 즉시구매 리스팅이면 구매 주문 매칭 시도
        if auction_type == AuctionType.BUYNOW:
            await AuctionService._try_match_listing_with_buy_orders(listing)

        return listing

    @staticmethod
    async def cancel_listing(user: User, listing_id: int) -> None:
        """
        경매 취소

        Args:
            user: 판매자
            listing_id: 리스팅 ID

        Raises:
            AuctionListingNotFoundError: 리스팅 없음
            AuctionCannotCancelError: 취소 불가 (본인 아님, 입찰자 있음 등)
        """
        listing = await AuctionListing.get_or_none(id=listing_id).prefetch_related("seller")

        if not listing:
            raise AuctionListingNotFoundError(listing_id)

        # Guard: 본인 확인
        if listing.seller_id != user.id:
            raise AuctionCannotCancelError("본인의 경매만 취소할 수 있습니다")

        # Guard: ACTIVE 상태 확인
        if listing.status != AuctionStatus.ACTIVE:
            raise AuctionCannotCancelError(f"이미 {listing.status} 상태입니다")

        # Guard: 입찰자 있으면 취소 불가 (BID 모드)
        if listing.auction_type == AuctionType.BID:
            bid_count = await AuctionBid.filter(auction=listing).count()
            if bid_count > 0:
                raise AuctionCannotCancelError("입찰자가 있어 취소할 수 없습니다")

        # Transaction: is_locked 해제 + 상태 변경
        async with in_transaction() as conn:
            if listing.inventory_item:
                listing.inventory_item.is_locked = False
                await listing.inventory_item.save(using_db=conn)

            listing.status = AuctionStatus.CANCELLED
            await listing.save(using_db=conn)

        logger.info(f"User {user.id} cancelled listing {listing_id}")

    # =========================================================================
    # 입찰 (Bidding)
    # =========================================================================

    @staticmethod
    async def place_bid(
        user: User,
        listing_id: int,
        bid_amount: int
    ) -> AuctionBid:
        """
        입찰

        Args:
            user: 입찰자
            listing_id: 리스팅 ID
            bid_amount: 입찰 금액

        Returns:
            생성된 AuctionBid

        Raises:
            CombatRestrictionError: 전투 중
            AuctionListingNotFoundError: 리스팅 없음
            AuctionSelfBidError: 본인 물품 입찰
            AuctionAlreadyEndedError: 이미 종료된 경매
            AuctionBidTooLowError: 입찰가 너무 낮음
            InsufficientGoldError: 골드 부족
        """
        # Guard: 전투 중 체크
        session = get_session(user.discord_id)
        if session and session.in_combat:
            raise CombatRestrictionError("입찰")

        listing = await AuctionListing.get_or_none(id=listing_id).prefetch_related("seller")

        if not listing:
            raise AuctionListingNotFoundError(listing_id)

        # Guard: 본인 물품 입찰 방지
        if listing.seller_id == user.id:
            raise AuctionSelfBidError()

        # Guard: ACTIVE + BID 타입 확인
        if listing.status != AuctionStatus.ACTIVE:
            raise AuctionAlreadyEndedError()

        if listing.auction_type != AuctionType.BID:
            raise ValueError("입찰 방식 경매가 아닙니다")

        # Guard: 현재가보다 높은지 검증
        if bid_amount <= listing.current_price:
            raise AuctionBidTooLowError(listing.current_price, bid_amount)

        # Guard: 골드 충분 여부
        if user.gold < bid_amount:
            raise InsufficientGoldError(bid_amount, user.gold)

        # Transaction: 이전 입찰자 환불 + 현재 입찰자 차감 + 입찰 생성
        async with in_transaction() as conn:
            # 이전 최고 입찰자 환불
            prev_highest_bid = await AuctionBid.filter(
                auction=listing
            ).order_by("-bid_amount").first()

            if prev_highest_bid:
                prev_bidder = await User.get(id=prev_highest_bid.bidder_id)
                prev_bidder.gold += prev_highest_bid.bid_amount
                prev_highest_bid.is_refunded = True
                await prev_bidder.save(using_db=conn)
                await prev_highest_bid.save(using_db=conn)
                logger.info(
                    f"Refunded {prev_highest_bid.bid_amount}G to user {prev_bidder.id}"
                )

            # 현재 입찰자 골드 차감
            user.gold -= bid_amount
            await user.save(using_db=conn)

            # 입찰 생성
            bid = await AuctionBid.create(
                auction=listing,
                bidder=user,
                bid_amount=bid_amount,
                using_db=conn
            )

            # 현재가 업데이트
            listing.current_price = bid_amount
            await listing.save(using_db=conn)

        logger.info(
            f"User {user.id} bid {bid_amount}G on listing {listing_id}"
        )

        return bid

    # =========================================================================
    # 즉시 구매
    # =========================================================================

    @staticmethod
    async def buy_now(user: User, listing_id: int) -> None:
        """
        즉시 구매

        Args:
            user: 구매자
            listing_id: 리스팅 ID

        Raises:
            CombatRestrictionError: 전투 중
            AuctionListingNotFoundError: 리스팅 없음
            AuctionAlreadyEndedError: 이미 종료
            InsufficientGoldError: 골드 부족
        """
        # Guard: 전투 중 체크
        session = get_session(user.discord_id)
        if session and session.in_combat:
            raise CombatRestrictionError("즉시 구매")

        listing = await AuctionListing.get_or_none(id=listing_id).prefetch_related("seller")

        if not listing:
            raise AuctionListingNotFoundError(listing_id)

        # Guard: 본인 물품 구매 방지
        if listing.seller_id == user.id:
            raise ValueError("본인의 물품은 구매할 수 없습니다")

        # Guard: ACTIVE 상태 확인
        if listing.status != AuctionStatus.ACTIVE:
            raise AuctionAlreadyEndedError()

        # Guard: 즉시구매 가능 여부
        if listing.auction_type == AuctionType.BUYNOW:
            purchase_price = listing.starting_price
        elif listing.buyout_price:
            purchase_price = listing.buyout_price
        else:
            raise ValueError("즉시 구매가 설정되지 않았습니다")

        # Guard: 골드 충분 여부
        if user.gold < purchase_price:
            raise InsufficientGoldError(purchase_price, user.gold)

        # Transaction: 골드 이동 + 아이템 이동 + 상태 변경
        await AuctionService._execute_sale(
            listing, user, purchase_price, AuctionSaleType.BUYNOW
        )

        logger.info(
            f"User {user.id} bought listing {listing_id} "
            f"for {purchase_price}G (buy now)"
        )

    # =========================================================================
    # 구매 주문 (Buy Order)
    # =========================================================================

    @staticmethod
    async def create_buy_order(
        user: User,
        item_id: int,
        max_price: int,
        min_enhancement: int,
        max_enhancement: int,
        min_grade: int,
        max_grade: int,
        duration_hours: int
    ) -> BuyOrder:
        """
        구매 주문 생성

        Args:
            user: 구매자
            item_id: 원하는 아이템 ID
            max_price: 최대 지불 가격
            min_enhancement: 최소 강화 레벨
            max_enhancement: 최대 강화 레벨
            min_grade: 최소 등급
            max_grade: 최대 등급
            duration_hours: 주문 기간 (시간)

        Returns:
            생성된 BuyOrder

        Raises:
            CombatRestrictionError: 전투 중
            InsufficientGoldError: 골드 부족 (에스크로)
            ValueError: 가격 또는 기간 유효하지 않음
        """
        # Guard: 전투 중 체크
        session = get_session(user.discord_id)
        if session and session.in_combat:
            raise CombatRestrictionError("구매 주문")

        # Guard: 가격 검증
        if max_price < AUCTION.MIN_LISTING_PRICE:
            raise ValueError(
                f"최소 가격은 {AUCTION.MIN_LISTING_PRICE}G입니다"
            )

        # Guard: 골드 충분 여부 (에스크로)
        if user.gold < max_price:
            raise InsufficientGoldError(max_price, user.gold)

        # Guard: 기간 검증
        if not (1 <= duration_hours <= AUCTION.MAX_LISTING_DURATION_HOURS):
            raise ValueError(
                f"주문 기간은 1~{AUCTION.MAX_LISTING_DURATION_HOURS}시간이어야 합니다"
            )

        # Transaction: 골드 차감 (에스크로) + 주문 생성
        async with in_transaction() as conn:
            user.gold -= max_price
            await user.save(using_db=conn)

            expires_at = datetime.now(timezone.utc) + timedelta(hours=duration_hours)

            buy_order = await BuyOrder.create(
                buyer=user,
                item_id=item_id,
                min_enhancement_level=min_enhancement,
                max_enhancement_level=max_enhancement,
                min_instance_grade=min_grade,
                max_instance_grade=max_grade,
                max_price=max_price,
                escrowed_gold=max_price,
                expires_at=expires_at,
                using_db=conn
            )

        logger.info(
            f"User {user.id} created buy order {buy_order.id} "
            f"(item {item_id}, max {max_price}G)"
        )

        # Post: 즉시 매칭 시도
        matched = await AuctionService._try_match_buy_order(buy_order)
        if matched:
            logger.info(f"Buy order {buy_order.id} immediately matched")

        return buy_order

    @staticmethod
    async def cancel_buy_order(user: User, order_id: int) -> None:
        """
        구매 주문 취소

        Args:
            user: 구매자
            order_id: 주문 ID

        Raises:
            BuyOrderNotFoundError: 주문 없음
            ValueError: 취소 불가 (본인 아님, 이미 체결 등)
        """
        buy_order = await BuyOrder.get_or_none(id=order_id)

        if not buy_order:
            raise BuyOrderNotFoundError(order_id)

        # Guard: 본인 확인
        if buy_order.buyer_id != user.id:
            raise ValueError("본인의 주문만 취소할 수 있습니다")

        # Guard: ACTIVE 상태 확인
        if buy_order.status != BuyOrderStatus.ACTIVE:
            raise ValueError(f"이미 {buy_order.status} 상태입니다")

        # Transaction: 에스크로 골드 반환 + 상태 변경
        async with in_transaction() as conn:
            user.gold += buy_order.escrowed_gold
            await user.save(using_db=conn)

            buy_order.status = BuyOrderStatus.CANCELLED
            await buy_order.save(using_db=conn)

        logger.info(f"User {user.id} cancelled buy order {order_id}")

    # =========================================================================
    # 만료 처리 (Cron)
    # =========================================================================

    @staticmethod
    async def process_expired_listings() -> int:
        """
        만료된 리스팅 처리 (크론잡용)

        Returns:
            처리된 리스팅 수
        """
        now = datetime.now(timezone.utc)
        expired_listings = await AuctionListing.filter(
            status=AuctionStatus.ACTIVE,
            expires_at__lt=now
        ).prefetch_related("inventory_item", "seller")

        count = 0
        for listing in expired_listings:
            # 입찰자 있으면 낙찰 처리
            if listing.auction_type == AuctionType.BID:
                highest_bid = await AuctionBid.filter(
                    auction=listing
                ).order_by("-bid_amount").first()

                if highest_bid:
                    await AuctionService._finalize_auction(listing, highest_bid)
                    count += 1
                    continue

            # 입찰자 없으면 만료 처리
            async with in_transaction() as conn:
                if listing.inventory_item:
                    listing.inventory_item.is_locked = False
                    await listing.inventory_item.save(using_db=conn)

                listing.status = AuctionStatus.EXPIRED
                await listing.save(using_db=conn)

            # 판매자에게 우편 발송
            await MailService.send_mail(
                user_id=listing.seller_id,
                mail_type="system",
                sender="경매장",
                title="경매 만료",
                content=f"**{listing.item_name}**의 경매가 입찰자 없이 만료되었습니다.",
                reward_config=None
            )

            count += 1

        if count > 0:
            logger.info(f"Processed {count} expired listings")

        return count

    @staticmethod
    async def process_expired_buy_orders() -> int:
        """
        만료된 구매 주문 처리 (크론잡용)

        Returns:
            처리된 주문 수
        """
        now = datetime.now(timezone.utc)
        expired_orders = await BuyOrder.filter(
            status=BuyOrderStatus.ACTIVE,
            expires_at__lt=now
        ).prefetch_related("buyer")

        count = 0
        for order in expired_orders:
            async with in_transaction() as conn:
                # 에스크로 골드 반환
                buyer = order.buyer
                buyer.gold += order.escrowed_gold
                await buyer.save(using_db=conn)

                order.status = BuyOrderStatus.EXPIRED
                await order.save(using_db=conn)

            count += 1

        if count > 0:
            logger.info(f"Processed {count} expired buy orders")

        return count

    # =========================================================================
    # 조회 (Query)
    # =========================================================================

    @staticmethod
    async def search_listings(
        item_type: Optional[ItemType] = None,
        item_grade: Optional[int] = None,
        min_enhancement: int = 0,
        max_enhancement: int = 99,
        min_price: int = 0,
        max_price: int = 999999999,
        sort_by: str = "created_at",
        offset: int = 0,
        limit: int = 25
    ) -> List[AuctionListing]:
        """리스팅 검색"""
        query = AuctionListing.filter(status=AuctionStatus.ACTIVE)

        # 필터 적용
        if item_grade is not None:
            query = query.filter(instance_grade=item_grade)

        query = query.filter(
            enhancement_level__gte=min_enhancement,
            enhancement_level__lte=max_enhancement,
            current_price__gte=min_price,
            current_price__lte=max_price
        )

        # 정렬
        if sort_by == "price_asc":
            query = query.order_by("current_price")
        elif sort_by == "price_desc":
            query = query.order_by("-current_price")
        elif sort_by == "expires_at":
            query = query.order_by("expires_at")
        else:  # created_at (default)
            query = query.order_by("-created_at")

        # 페이지네이션
        listings = await query.offset(offset).limit(limit).prefetch_related("seller")

        return listings

    @staticmethod
    async def get_my_listings(
        user: User,
        status: Optional[AuctionStatus] = None
    ) -> List[AuctionListing]:
        """내 리스팅 조회"""
        query = AuctionListing.filter(seller=user)

        if status:
            query = query.filter(status=status)
        else:
            query = query.filter(status=AuctionStatus.ACTIVE)

        return await query.order_by("-created_at")

    @staticmethod
    async def get_my_bids(user: User) -> List[AuctionBid]:
        """내 입찰 조회 (환불되지 않은 것만)"""
        return await AuctionBid.filter(
            bidder=user,
            is_refunded=False
        ).prefetch_related("auction").order_by("-created_at")

    @staticmethod
    async def get_my_buy_orders(
        user: User,
        status: Optional[BuyOrderStatus] = None
    ) -> List[BuyOrder]:
        """내 구매 주문 조회"""
        query = BuyOrder.filter(buyer=user)

        if status:
            query = query.filter(status=status)
        else:
            query = query.filter(status=BuyOrderStatus.ACTIVE)

        return await query.order_by("-created_at")

    @staticmethod
    async def get_price_history(
        item_id: int,
        enhancement_level: int,
        instance_grade: int
    ) -> List[AuctionHistory]:
        """가격 히스토리 조회 (최근 10건)"""
        return await AuctionHistory.filter(
            item_id=item_id,
            enhancement_level=enhancement_level,
            instance_grade=instance_grade
        ).order_by("-sold_at").limit(10)

    # =========================================================================
    # 내부 헬퍼
    # =========================================================================

    @staticmethod
    async def _finalize_auction(
        listing: AuctionListing,
        highest_bid: AuctionBid
    ) -> None:
        """
        경매 낙찰 처리 (내부용)

        Args:
            listing: 경매 리스팅
            highest_bid: 최고 입찰
        """
        winner = await User.get(id=highest_bid.bidder_id)
        seller = listing.seller

        await AuctionService._execute_sale(
            listing, winner, highest_bid.bid_amount, AuctionSaleType.AUCTION
        )

        # 낙찰자 외 입찰자들 환불
        other_bids = await AuctionBid.filter(
            auction=listing,
            is_refunded=False
        ).exclude(id=highest_bid.id)

        if other_bids:
            async with in_transaction() as conn:
                for bid in other_bids:
                    bidder = await User.get(id=bid.bidder_id)
                    bidder.gold += bid.bid_amount
                    bid.is_refunded = True
                    await bidder.save(using_db=conn)
                    await bid.save(using_db=conn)

        logger.info(
            f"Finalized auction {listing.id}: winner={winner.id}, "
            f"price={highest_bid.bid_amount}G"
        )

    @staticmethod
    async def _execute_sale(
        listing: AuctionListing,
        buyer: User,
        sale_price: int,
        sale_type: AuctionSaleType
    ) -> None:
        """
        판매 실행 (내부용)

        Args:
            listing: 경매 리스팅
            buyer: 구매자
            sale_price: 판매 가격
            sale_type: 판매 방식
        """
        seller = listing.seller

        # 판매 수수료 계산
        sale_fee = int(sale_price * AUCTION.SALE_FEE_PERCENT)
        seller_receives = sale_price - sale_fee

        async with in_transaction() as conn:
            # 골드 이동 (즉시구매는 여기서 차감, 입찰은 이미 차감됨)
            if sale_type == AuctionSaleType.BUYNOW:
                buyer.gold -= sale_price
                await buyer.save(using_db=conn)

            seller.gold += seller_receives
            await seller.save(using_db=conn)

            # 아이템 이동 (소유권 이전)
            if listing.inventory_item:
                listing.inventory_item.user = buyer
                listing.inventory_item.is_locked = False
                await listing.inventory_item.save(using_db=conn)

            # 리스팅 상태 변경
            listing.status = AuctionStatus.SOLD
            listing.buyer_id = buyer.id
            listing.sold_at = datetime.now(timezone.utc)
            listing.final_price = sale_price
            listing.inventory_item = None  # FK null
            await listing.save(using_db=conn)

            # 히스토리 생성
            await AuctionHistory.create(
                item_id=listing.item_id,
                enhancement_level=listing.enhancement_level,
                instance_grade=listing.instance_grade,
                sale_price=sale_price,
                sale_type=sale_type,
                seller_id=seller.id,
                buyer_id=buyer.id,
                using_db=conn
            )

        # 히스토리 정리 (10건 초과 시 오래된 것 삭제)
        await AuctionService._cleanup_price_history(
            listing.item_id,
            listing.enhancement_level,
            listing.instance_grade
        )

        # 우편 발송
        await MailService.send_mail(
            user_id=seller.id,
            mail_type="system",
            sender="경매장",
            title="경매 판매 완료",
            content=(
                f"**{listing.item_name}**이(가) {sale_price}G에 판매되었습니다.\n"
                f"수수료 {sale_fee}G를 제외한 {seller_receives}G를 받았습니다."
            ),
            reward_config=None
        )

        await MailService.send_mail(
            user_id=buyer.id,
            mail_type="system",
            sender="경매장",
            title="경매 구매 완료",
            content=(
                f"**{listing.item_name}**을(를) {sale_price}G에 구매했습니다.\n"
                f"인벤토리를 확인해주세요."
            ),
            reward_config=None
        )

    @staticmethod
    async def _try_match_listing_with_buy_orders(
        listing: AuctionListing
    ) -> bool:
        """
        새 리스팅과 구매 주문 매칭 시도 (내부용)

        Args:
            listing: 새로 등록된 리스팅

        Returns:
            매칭 성공 여부
        """
        # 조건에 맞는 구매 주문 검색 (가장 높은 가격 순)
        matching_orders = await BuyOrder.filter(
            status=BuyOrderStatus.ACTIVE,
            item_id=listing.item_id,
            min_enhancement_level__lte=listing.enhancement_level,
            max_enhancement_level__gte=listing.enhancement_level,
            min_instance_grade__lte=listing.instance_grade,
            max_instance_grade__gte=listing.instance_grade,
            max_price__gte=listing.starting_price
        ).order_by("-max_price").first()

        if matching_orders:
            await AuctionService._fulfill_buy_order(matching_orders, listing)
            return True

        return False

    @staticmethod
    async def _try_match_buy_order(buy_order: BuyOrder) -> bool:
        """
        구매 주문 매칭 시도 (내부용)

        Args:
            buy_order: 구매 주문

        Returns:
            매칭 성공 여부
        """
        # 조건 맞는 즉시구매 리스팅 검색 (가장 낮은 가격 순)
        matching_listing = await AuctionListing.filter(
            status=AuctionStatus.ACTIVE,
            auction_type=AuctionType.BUYNOW,
            item_id=buy_order.item_id,
            enhancement_level__gte=buy_order.min_enhancement_level,
            enhancement_level__lte=buy_order.max_enhancement_level,
            instance_grade__gte=buy_order.min_instance_grade,
            instance_grade__lte=buy_order.max_instance_grade,
            starting_price__lte=buy_order.max_price
        ).order_by("starting_price").first()

        if matching_listing:
            await AuctionService._fulfill_buy_order(buy_order, matching_listing)
            return True

        return False

    @staticmethod
    async def _fulfill_buy_order(
        buy_order: BuyOrder,
        listing: AuctionListing
    ) -> None:
        """
        구매 주문 체결 (내부용)

        Args:
            buy_order: 구매 주문
            listing: 매칭된 리스팅
        """
        buyer = buy_order.buyer
        seller = listing.seller
        final_price = listing.starting_price  # 리스팅 가격으로 체결

        # 판매 수수료 계산
        sale_fee = int(final_price * AUCTION.SALE_FEE_PERCENT)
        seller_receives = final_price - sale_fee

        # 에스크로에서 차액 환불 (max_price - final_price)
        refund = buy_order.escrowed_gold - final_price

        async with in_transaction() as conn:
            # 차액 환불
            if refund > 0:
                buyer.gold += refund

            # 판매자 골드 증가
            seller.gold += seller_receives
            await buyer.save(using_db=conn)
            await seller.save(using_db=conn)

            # 아이템 이동 (소유권 이전)
            if listing.inventory_item:
                listing.inventory_item.user = buyer
                listing.inventory_item.is_locked = False
                await listing.inventory_item.save(using_db=conn)

            # 상태 변경
            buy_order.status = BuyOrderStatus.FULFILLED
            buy_order.seller_id = seller.id
            buy_order.fulfilled_at = datetime.now(timezone.utc)
            buy_order.final_price = final_price
            await buy_order.save(using_db=conn)

            listing.status = AuctionStatus.SOLD
            listing.buyer_id = buyer.id
            listing.sold_at = datetime.now(timezone.utc)
            listing.final_price = final_price
            listing.inventory_item = None
            await listing.save(using_db=conn)

            # 히스토리 생성
            await AuctionHistory.create(
                item_id=listing.item_id,
                enhancement_level=listing.enhancement_level,
                instance_grade=listing.instance_grade,
                sale_price=final_price,
                sale_type=AuctionSaleType.BUY_ORDER,
                seller_id=seller.id,
                buyer_id=buyer.id,
                using_db=conn
            )

        # 히스토리 정리
        await AuctionService._cleanup_price_history(
            listing.item_id,
            listing.enhancement_level,
            listing.instance_grade
        )

        # 우편 발송
        await MailService.send_mail(
            user_id=seller.id,
            mail_type="system",
            sender="경매장",
            title="구매 주문 체결",
            content=(
                f"**{listing.item_name}**이(가) 구매 주문으로 {final_price}G에 판매되었습니다.\n"
                f"수수료 {sale_fee}G를 제외한 {seller_receives}G를 받았습니다."
            ),
            reward_config=None
        )

        await MailService.send_mail(
            user_id=buyer.id,
            mail_type="system",
            sender="경매장",
            title="구매 주문 체결",
            content=(
                f"**{listing.item_name}**에 대한 구매 주문이 체결되었습니다!\n"
                f"{final_price}G에 구매했습니다. (차액 {refund}G 환불)"
            ),
            reward_config=None
        )

        logger.info(
            f"Fulfilled buy order {buy_order.id} with listing {listing.id} "
            f"at {final_price}G"
        )

    @staticmethod
    async def _cleanup_price_history(
        item_id: int,
        enhancement_level: int,
        instance_grade: int
    ) -> None:
        """
        가격 히스토리 정리 - 최근 10건만 유지 (내부용)

        Args:
            item_id: 아이템 ID
            enhancement_level: 강화 레벨
            instance_grade: 등급
        """
        # 최근 10건 ID 조회
        recent_ids = await AuctionHistory.filter(
            item_id=item_id,
            enhancement_level=enhancement_level,
            instance_grade=instance_grade
        ).order_by("-sold_at").limit(10).values_list("id", flat=True)

        if len(recent_ids) < 10:
            return

        # 10건 초과 시 오래된 것 삭제
        await AuctionHistory.filter(
            item_id=item_id,
            enhancement_level=enhancement_level,
            instance_grade=instance_grade
        ).exclude(id__in=recent_ids).delete()

        logger.debug(
            f"Cleaned up price history for item {item_id} "
            f"(+{enhancement_level}, grade {instance_grade})"
        )
