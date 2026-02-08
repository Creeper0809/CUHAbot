"""Discord UI 관련 설정"""
from dataclasses import dataclass
from enum import IntEnum


class EmbedColor(IntEnum):
    """임베드 색상"""

    DEFAULT = 0x3498DB  # 파란색
    SUCCESS = 0x2ECC71  # 초록색
    WARNING = 0xF39C12  # 주황색
    ERROR = 0xE74C3C  # 빨간색
    COMBAT = 0xFF5733  # 전투용 주황색
    DUNGEON = 0x27AE60  # 던전용 초록색
    ITEM_D = 0x95A5A6  # D등급 회색
    ITEM_C = 0x2ECC71  # C등급 초록색
    ITEM_B = 0x3498DB  # B등급 파란색
    ITEM_A = 0x9B59B6  # A등급 보라색
    ITEM_S = 0xF1C40F  # S등급 금색
    ITEM_SS = 0xE74C3C  # SS등급 빨간색
    ITEM_SSS = 0xE91E63  # SSS등급 핑크색
    ITEM_MYTHIC = 0xFF6B6B  # 신화등급


@dataclass(frozen=True)
class UIConfig:
    """UI 설정"""

    # 타임아웃
    VIEW_TIMEOUT_SECONDS: int = 60
    """View 기본 타임아웃 (1분)"""

    FIGHT_OR_FLEE_TIMEOUT: int = 30
    """전투/도주 선택 타임아웃 (30초)"""

    ENCOUNTER_TIMEOUT: int = 30
    """인카운터 타임아웃 (30초)"""

    INVENTORY_TIMEOUT: int = 120
    """인벤토리 View 타임아웃 (2분)"""

    SKILL_DECK_TIMEOUT: int = 180
    """스킬 덱 View 타임아웃 (3분)"""

    ENHANCEMENT_TIMEOUT: int = 180
    """강화 View 타임아웃 (3분)"""

    # 페이지네이션
    ITEMS_PER_PAGE: int = 10
    """페이지당 아이템 수"""

    MAX_EMBED_FIELD_VALUE: int = 1024
    """임베드 필드 값 최대 길이"""


UI = UIConfig()
