"""상점 및 인벤토리 설정"""
from dataclasses import dataclass


@dataclass(frozen=True)
class ShopConfig:
    """상점 설정"""

    DEFAULT_SKILL_PRICE: int = 500
    """등급 정보 없는 스킬 기본 가격"""

    SELL_PRICE_RATIO: float = 0.5
    """판매 가격 비율 (구매가의 50%)"""


SHOP = ShopConfig()


@dataclass(frozen=True)
class InventoryConfig:
    """인벤토리 설정"""

    MAX_SLOTS: int = 100
    """최대 인벤토리 슬롯"""


INVENTORY = InventoryConfig()
