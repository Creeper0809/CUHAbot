"""
CUHABot 게임 설정 상수

모든 매직 넘버와 게임 밸런스 관련 상수를 여기서 관리합니다.
설정 변경 시 이 파일만 수정하면 됩니다.
"""
from dataclasses import dataclass
from enum import IntEnum


# =============================================================================
# 스킬/덱 관련 상수
# =============================================================================

SKILL_DECK_SIZE = 10
"""스킬 덱 최대 슬롯 수"""

DEFAULT_SKILL_SLOT = 0
"""빈 스킬 슬롯 값"""


# =============================================================================
# 전투 관련 상수
# =============================================================================

@dataclass(frozen=True)
class CombatConfig:
    """전투 설정"""

    # 전투 로그
    COMBAT_LOG_MAX_LENGTH: int = 6
    """전투 로그 최대 줄 수"""

    EVENT_QUEUE_MAX_LENGTH: int = 5
    """이벤트 큐 최대 길이"""

    # 턴 순서 계산
    SPEED_ADVANTAGE_CAP: int = 50
    """속도 우위 최대값 (±50)"""

    BASE_TURN_PROBABILITY: int = 50
    """기본 선공 확률 (%)"""

    # 딜레이 (초)
    MAIN_LOOP_DELAY: float = 5.0
    """던전 메인 루프 딜레이"""

    TURN_PHASE_DELAY: float = 1.0
    """턴 페이즈 간 딜레이"""

    COMBAT_END_DELAY: float = 2.0
    """전투 종료 후 딜레이"""

    # 도주
    FLEE_SUCCESS_RATE: float = 0.5
    """도주 성공 확률 (일반 몬스터)"""

    FLEE_ELITE_SUCCESS_RATE: float = 0.0
    """도주 성공 확률 (엘리트/보스)"""


COMBAT = CombatConfig()


# =============================================================================
# 데미지 계산 상수
# =============================================================================

@dataclass(frozen=True)
class DamageConfig:
    """데미지 계산 설정"""

    # 방어력 적용
    PHYSICAL_DEFENSE_RATIO: float = 0.5
    """물리 방어력 적용 비율 (데미지 = 공격력 - 방어력 × 0.5)"""

    MAGICAL_DEFENSE_RATIO: float = 0.4
    """마법 방어력 적용 비율 (데미지 = 마공 - 마방 × 0.4)"""

    # 방어력 무시
    MAX_ARMOR_PENETRATION: float = 0.7
    """최대 방어력 무시 비율 (70%)"""

    # 데미지 변동
    DAMAGE_VARIANCE: float = 0.2
    """데미지 랜덤 변동폭 (±20%, 0.8~1.2배)"""

    MIN_DAMAGE: int = 1
    """최소 데미지 (0 이하로 떨어지지 않음)"""

    # 치명타
    CRITICAL_MULTIPLIER: float = 1.5
    """치명타 데미지 배율"""

    DEFAULT_CRITICAL_RATE: float = 0.05
    """기본 치명타 확률 (5%)"""


DAMAGE = DamageConfig()


# =============================================================================
# 속성 상성 상수
# =============================================================================

@dataclass(frozen=True)
class AttributeConfig:
    """속성 상성 설정"""

    ADVANTAGE_MULTIPLIER: float = 1.5
    """유리한 속성 데미지 배율 (+50%)"""

    DISADVANTAGE_MULTIPLIER: float = 0.5
    """불리한 속성 데미지 배율 (-50%)"""

    SAME_ELEMENT_MULTIPLIER: float = 0.5
    """동일 속성 데미지 배율 (-50%)"""

    NEUTRAL_MULTIPLIER: float = 1.0
    """무속성 데미지 배율"""

    MAX_RESISTANCE: float = 0.75
    """최대 속성 저항 (75%)"""


ATTRIBUTE = AttributeConfig()


# =============================================================================
# 상태이상 상수
# =============================================================================

@dataclass(frozen=True)
class StatusEffectConfig:
    """상태이상 설정"""

    # 화상
    BURN_DAMAGE_PERCENT: float = 0.03
    """화상 턴당 피해 (최대 HP의 3%)"""

    BURN_MAX_STACKS: int = 5
    """화상 최대 스택"""

    BURN_DEFAULT_DURATION: int = 3
    """화상 기본 지속 턴"""

    # 독
    POISON_DAMAGE_PERCENT: float = 0.02
    """독 턴당 피해 (최대 HP의 2%)"""

    POISON_MAX_STACKS: int = 3
    """독 최대 스택"""

    POISON_DEFAULT_DURATION: int = 5
    """독 기본 지속 턴"""

    # 출혈
    BLEED_DAMAGE_PERCENT: float = 0.04
    """출혈 턴당 피해 (최대 HP의 4%)"""

    BLEED_DEFAULT_DURATION: int = 2
    """출혈 기본 지속 턴"""

    # 둔화
    SLOW_SPEED_REDUCTION: float = 0.3
    """둔화 속도 감소율 (30%)"""

    SLOW_DEFAULT_DURATION: int = 2
    """둔화 기본 지속 턴"""

    # 동결
    FREEZE_DAMAGE_INCREASE: float = 0.2
    """동결 시 받는 피해 증가 (20%)"""

    FREEZE_DEFAULT_DURATION: int = 1
    """동결 기본 지속 턴"""

    # 상태이상 저항
    MAX_STATUS_RESISTANCE: float = 0.8
    """최대 상태이상 저항 (80%)"""


STATUS_EFFECT = StatusEffectConfig()


# =============================================================================
# 유저 스탯 관련 상수
# =============================================================================

@dataclass(frozen=True)
class UserStatsConfig:
    """유저 스탯 설정"""

    # 초기 스탯
    INITIAL_HP: int = 300
    """초기 HP"""

    INITIAL_ATTACK: int = 10
    """초기 공격력"""

    INITIAL_SPEED: int = 10
    """초기 속도"""

    INITIAL_LEVEL: int = 1
    """초기 레벨"""

    # 레벨업 스탯 증가
    HP_PER_LEVEL: int = 20
    """레벨당 HP 증가"""

    ATTACK_PER_LEVEL: int = 2
    """레벨당 공격력 증가"""

    # 스탯 포인트
    STAT_POINTS_PER_LEVEL: int = 3
    """레벨당 스탯 포인트"""


USER_STATS = UserStatsConfig()


# =============================================================================
# 던전 관련 상수
# =============================================================================

@dataclass(frozen=True)
class DungeonConfig:
    """던전 설정"""

    # 레벨 제한
    MIN_LEVEL_DIFFERENCE: int = -10
    """던전 입장 최소 레벨 차이 (권장 레벨보다 최대 10 낮아도 입장 가능)"""

    # 보상 배율
    ELITE_EXP_MULTIPLIER: float = 2.0
    """엘리트 몬스터 경험치 배율"""

    BOSS_EXP_MULTIPLIER: float = 5.0
    """보스 몬스터 경험치 배율"""

    ELITE_GOLD_MULTIPLIER: float = 2.5
    """엘리트 몬스터 골드 배율"""

    BOSS_GOLD_MULTIPLIER: float = 10.0
    """보스 몬스터 골드 배율"""

    BOSS_SPAWN_RATE: float = 0.05
    """보스 몬스터 기본 등장 확률 (스폰 테이블 내 존재 시)"""


DUNGEON = DungeonConfig()


# =============================================================================
# 아이템 드롭 상수
# =============================================================================

@dataclass(frozen=True)
class DropConfig:
    """드롭 설정"""

    # 등급별 기본 드롭률 (일반 몬스터)
    DROP_RATE_D: float = 0.20
    DROP_RATE_C: float = 0.10
    DROP_RATE_B: float = 0.05
    DROP_RATE_A: float = 0.02
    DROP_RATE_S: float = 0.005
    DROP_RATE_SS: float = 0.001
    DROP_RATE_SSS: float = 0.0001
    DROP_RATE_MYTHIC: float = 0.00005

    # 타입별 드롭률 배율
    ELITE_DROP_MULTIPLIER: float = 3.0
    """엘리트 몬스터 드롭률 배율"""

    BOSS_DROP_MULTIPLIER: float = 10.0
    """보스 몬스터 드롭률 배율"""

    # 상자 드롭
    CHEST_DROP_RATE: float = 0.2
    """몬스터 처치 시 상자 드롭 확률"""

    CHEST_GOLD_RATE: float = 0.85
    """상자에서 골드가 나올 확률"""

    CHEST_GRADE_WEIGHTS: tuple[int, int, int] = (70, 25, 5)
    """상자 등급 가중치 (normal, silver, gold)"""

    CHEST_ITEM_NORMAL_ID: int = 5901
    """일반 상자 아이템 ID"""

    CHEST_ITEM_SILVER_ID: int = 5902
    """실버 상자 아이템 ID"""

    CHEST_ITEM_GOLD_ID: int = 5903
    """골드 상자 아이템 ID"""

    # 스킬 드롭
    SKILL_DROP_RATE: float = 0.001
    """몬스터 스킬 드롭 확률 (0.1%)"""


DROP = DropConfig()


# =============================================================================
# 주간 타워 상수
# =============================================================================

@dataclass(frozen=True)
class WeeklyTowerConfig:
    """주간 타워 설정"""

    TOTAL_FLOORS: int = 100
    """타워 총 층수"""

    BOSS_FLOOR_INTERVAL: int = 10
    """보스층 간격 (10, 20, 30...)"""

    ITEMS_ALLOWED: bool = False
    """아이템 사용 허용 여부"""

    SKILL_CHANGE_BETWEEN_FLOORS: bool = True
    """층 사이 스킬 변경 허용 여부"""

    FLEE_ALLOWED: bool = False
    """도주 허용 여부"""


WEEKLY_TOWER = WeeklyTowerConfig()


# =============================================================================
# 파티/멀티플레이 상수
# =============================================================================

@dataclass(frozen=True)
class PartyConfig:
    """파티 설정"""

    MAX_PARTY_SIZE: int = 5
    """파티 최대 인원"""

    INTERVENTION_WINDOW_TURNS: int = 3
    """전투 난입 가능 턴 수"""

    INTERVENTION_COOLDOWN_SECONDS: int = 300
    """전투 난입 쿨타임 (5분)"""

    RESCUE_REQUEST_HP_THRESHOLD: float = 0.3
    """구조 요청 HP 임계값 (30%)"""

    URGENT_RESCUE_HP_THRESHOLD: float = 0.1
    """긴급 구조 요청 HP 임계값 (10%)"""


PARTY = PartyConfig()


# =============================================================================
# 옥션 상수
# =============================================================================

@dataclass(frozen=True)
class AuctionConfig:
    """옥션 설정"""

    LISTING_FEE_PERCENT: float = 0.02
    """등록 수수료 (2%)"""

    SALE_FEE_PERCENT: float = 0.05
    """판매 수수료 (5%)"""

    MIN_LISTING_PRICE: int = 100
    """최소 등록 가격"""

    MAX_LISTING_DURATION_HOURS: int = 72
    """최대 등록 기간 (72시간)"""


AUCTION = AuctionConfig()


# =============================================================================
# Discord UI 상수
# =============================================================================

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

    # 페이지네이션
    ITEMS_PER_PAGE: int = 10
    """페이지당 아이템 수"""

    MAX_EMBED_FIELD_VALUE: int = 1024
    """임베드 필드 값 최대 길이"""


UI = UIConfig()
