"""
CUHABot 게임 설정 상수

모든 매직 넘버와 게임 밸런스 관련 상수를 여기서 관리합니다.
설정 변경 시 이 파일만 수정하면 됩니다.
"""
from dataclasses import dataclass
from enum import IntEnum, Enum
from typing import Optional, Dict


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

    # 턴 순서 계산 (1:1 전투용, 레거시)
    SPEED_ADVANTAGE_CAP: int = 50
    """속도 우위 최대값 (±50)"""

    BASE_TURN_PROBABILITY: int = 50
    """기본 선공 확률 (%)"""

    # 행동 게이지 시스템 (1:N 전투용)
    ACTION_GAUGE_MAX: int = 10
    """행동 게이지 최대값 (속도 10 기준)"""

    ACTION_GAUGE_BASE_FILL: int = 10
    """기본 게이지 충전량 (속도 10 기준)"""

    ACTION_GAUGE_SPEED_MULTIPLIER: float = 1.0
    """속도당 게이지 충전 배율 (충전량 = 속도 × 배율)"""

    ACTION_GAUGE_COST: int = 10
    """행동 후 게이지 소모량"""

    MAX_ACTIONS_PER_LOOP: int = 100
    """무한루프 방지용 최대 행동 횟수"""

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
# 속성 타입 및 상성
# =============================================================================


class AttributeType(str, Enum):
    """속성 타입"""
    NONE = "무속성"
    FIRE = "화염"
    ICE = "냉기"
    LIGHTNING = "번개"
    WATER = "수속성"
    HOLY = "신성"
    DARK = "암흑"


# 속성 상성표: key가 value에 강함
# Fire→Ice→Lightning→Water→Fire (순환), Holy↔Dark (상호)
ATTRIBUTE_ADVANTAGE: dict[AttributeType, AttributeType] = {
    AttributeType.FIRE: AttributeType.ICE,
    AttributeType.ICE: AttributeType.LIGHTNING,
    AttributeType.LIGHTNING: AttributeType.WATER,
    AttributeType.WATER: AttributeType.FIRE,
    AttributeType.HOLY: AttributeType.DARK,
    AttributeType.DARK: AttributeType.HOLY,
}

# 역방향 (약점 조회용)
ATTRIBUTE_DISADVANTAGE: dict[AttributeType, AttributeType] = {
    v: k for k, v in ATTRIBUTE_ADVANTAGE.items()
}


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


def get_attribute_multiplier(attacker_attr: str, defender_attr: str) -> float:
    """
    속성 상성에 따른 데미지 배율 계산

    Args:
        attacker_attr: 공격 스킬의 속성 (AttributeType.value 문자열)
        defender_attr: 방어자의 속성 (AttributeType.value 문자열)

    Returns:
        데미지 배율
    """
    if attacker_attr == AttributeType.NONE.value or defender_attr == AttributeType.NONE.value:
        return ATTRIBUTE.NEUTRAL_MULTIPLIER

    if attacker_attr == defender_attr:
        return ATTRIBUTE.SAME_ELEMENT_MULTIPLIER

    try:
        atk_type = AttributeType(attacker_attr)
        def_type = AttributeType(defender_attr)
    except ValueError:
        return ATTRIBUTE.NEUTRAL_MULTIPLIER

    # 강점 체크
    if ATTRIBUTE_ADVANTAGE.get(atk_type) == def_type:
        return ATTRIBUTE.ADVANTAGE_MULTIPLIER

    # 약점 체크
    if ATTRIBUTE_DISADVANTAGE.get(atk_type) == def_type:
        return ATTRIBUTE.DISADVANTAGE_MULTIPLIER

    return ATTRIBUTE.NEUTRAL_MULTIPLIER


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

    BOSS_SPAWN_PROGRESS_THRESHOLD: float = 0.9
    """보스 등장 가능 진행도 (90% 이상)"""

    BOSS_SPAWN_RATE_AT_END: float = 0.1
    """던전 마지막(90% 이상) 진행도에서 보스 등장 확률 (10%)"""

    # 그룹 전투 설정
    GROUP_SPAWN_RATE: float = 0.1
    """몬스터 그룹 등장 확률 (10%)"""

    MAX_GROUP_SIZE: int = 3
    """최대 그룹 크기 (1~3마리)"""

    # 그룹 전투 보너스
    GROUP_EXP_BONUS: float = 1.2
    """그룹 처치 시 경험치 보너스 (+20%)"""

    GROUP_GOLD_BONUS: float = 1.1
    """그룹 처치 시 골드 보너스 (+10%)"""

    MIN_GROUP_SIZE: int = 1
    """최소 그룹 크기"""


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

    # 상자 드롭 (새 시스템)
    BOX_DROP_RATE: float = 0.2
    """몬스터 처치 시 상자 드롭 확률 (20%)"""

    # 스킬 드롭
    SKILL_DROP_RATE: float = 0.001
    """몬스터 스킬 드롭 확률 (0.1%)"""

    # 보물상자 아이템 ID (인카운터용)
    CHEST_ITEM_NORMAL_ID: int = 5940
    """일반 보물상자 아이템 ID (혼합 상자 - 하급)"""

    CHEST_ITEM_SILVER_ID: int = 5941
    """은 보물상자 아이템 ID (혼합 상자 - 중급)"""

    CHEST_ITEM_GOLD_ID: int = 5942
    """금 보물상자 아이템 ID (혼합 상자 - 상급)"""


DROP = DropConfig()


# =============================================================================
# 상자 시스템 (Box System)
# =============================================================================

class BoxRewardType(str, Enum):
    """상자 보상 타입"""
    GOLD = "gold"
    EQUIPMENT = "equipment"
    SKILL = "skill"


@dataclass(frozen=True)
class BoxRewardConfig:
    """단일 보상 설정"""
    reward_type: BoxRewardType
    """보상 타입 (골드/장비/스킬)"""

    probability: float
    """보상 확률 (0.0~1.0)"""

    guaranteed_grade: Optional[str] = None
    """확정 등급 ("D", "C", "B", "A", "S" 등)"""

    grade_table_id: Optional[int] = None
    """등급 확률 테이블 ID (ItemGradeProbability.cheat_id)"""


@dataclass(frozen=True)
class BoxConfig:
    """상자 설정"""
    box_id: int
    """상자 아이템 ID"""

    name: str
    """상자 이름"""

    rewards: list[BoxRewardConfig]
    """보상 목록"""

    gold_multiplier: float = 1.0
    """골드 보상 배율"""

    def validate(self) -> bool:
        """확률 합계 검증 (합이 ~1.0이어야 함)"""
        total = sum(r.probability for r in self.rewards)
        return 0.99 <= total <= 1.01


# 상자 설정 레지스트리
BOX_CONFIGS: Dict[int, BoxConfig] = {
    # 등급별 장비 상자 (5920-5924)
    5920: BoxConfig(
        box_id=5920,
        name="장비 상자 (D등급)",
        rewards=[BoxRewardConfig(BoxRewardType.EQUIPMENT, 1.0, guaranteed_grade="D")]
    ),
    5921: BoxConfig(
        box_id=5921,
        name="장비 상자 (C등급)",
        rewards=[BoxRewardConfig(BoxRewardType.EQUIPMENT, 1.0, guaranteed_grade="C")]
    ),
    5922: BoxConfig(
        box_id=5922,
        name="장비 상자 (B등급)",
        rewards=[BoxRewardConfig(BoxRewardType.EQUIPMENT, 1.0, guaranteed_grade="B")]
    ),
    5923: BoxConfig(
        box_id=5923,
        name="장비 상자 (A등급)",
        rewards=[BoxRewardConfig(BoxRewardType.EQUIPMENT, 1.0, guaranteed_grade="A")]
    ),
    5924: BoxConfig(
        box_id=5924,
        name="장비 상자 (S등급)",
        rewards=[BoxRewardConfig(BoxRewardType.EQUIPMENT, 1.0, guaranteed_grade="S")]
    ),

    # 등급별 스킬 상자 (5930-5934)
    5930: BoxConfig(
        box_id=5930,
        name="스킬 상자 (D등급)",
        rewards=[BoxRewardConfig(BoxRewardType.SKILL, 1.0, guaranteed_grade="D")]
    ),
    5931: BoxConfig(
        box_id=5931,
        name="스킬 상자 (C등급)",
        rewards=[BoxRewardConfig(BoxRewardType.SKILL, 1.0, guaranteed_grade="C")]
    ),
    5932: BoxConfig(
        box_id=5932,
        name="스킬 상자 (B등급)",
        rewards=[BoxRewardConfig(BoxRewardType.SKILL, 1.0, guaranteed_grade="B")]
    ),
    5933: BoxConfig(
        box_id=5933,
        name="스킬 상자 (A등급)",
        rewards=[BoxRewardConfig(BoxRewardType.SKILL, 1.0, guaranteed_grade="A")]
    ),
    5934: BoxConfig(
        box_id=5934,
        name="스킬 상자 (S등급)",
        rewards=[BoxRewardConfig(BoxRewardType.SKILL, 1.0, guaranteed_grade="S")]
    ),

    # 혼합 상자 (5940-5943)
    5940: BoxConfig(
        box_id=5940,
        name="혼합 상자 (하급)",
        rewards=[
            BoxRewardConfig(BoxRewardType.GOLD, 0.5),
            BoxRewardConfig(BoxRewardType.EQUIPMENT, 0.3, grade_table_id=4),
            BoxRewardConfig(BoxRewardType.SKILL, 0.2, grade_table_id=4),
        ],
        gold_multiplier=1.0
    ),
    5941: BoxConfig(
        box_id=5941,
        name="혼합 상자 (중급)",
        rewards=[
            BoxRewardConfig(BoxRewardType.GOLD, 0.4),
            BoxRewardConfig(BoxRewardType.EQUIPMENT, 0.35, grade_table_id=5),
            BoxRewardConfig(BoxRewardType.SKILL, 0.25, grade_table_id=5),
        ],
        gold_multiplier=2.0
    ),
    5942: BoxConfig(
        box_id=5942,
        name="혼합 상자 (상급)",
        rewards=[
            BoxRewardConfig(BoxRewardType.GOLD, 0.3),
            BoxRewardConfig(BoxRewardType.EQUIPMENT, 0.4, grade_table_id=6),
            BoxRewardConfig(BoxRewardType.SKILL, 0.3, grade_table_id=6),
        ],
        gold_multiplier=3.0
    ),
    5943: BoxConfig(
        box_id=5943,
        name="혼합 상자 (최상급)",
        rewards=[
            BoxRewardConfig(BoxRewardType.GOLD, 0.2),
            BoxRewardConfig(BoxRewardType.EQUIPMENT, 0.45, grade_table_id=7),
            BoxRewardConfig(BoxRewardType.SKILL, 0.35, grade_table_id=7),
        ],
        gold_multiplier=5.0
    ),

    # 특수 상자 (5945-5947)
    5945: BoxConfig(
        box_id=5945,
        name="럭키 박스",
        rewards=[
            BoxRewardConfig(BoxRewardType.EQUIPMENT, 0.5, grade_table_id=8),
            BoxRewardConfig(BoxRewardType.SKILL, 0.5, grade_table_id=8),
        ]
    ),
    5946: BoxConfig(
        box_id=5946,
        name="신비한 상자",
        rewards=[
            BoxRewardConfig(BoxRewardType.EQUIPMENT, 0.5, grade_table_id=9),
            BoxRewardConfig(BoxRewardType.SKILL, 0.5, grade_table_id=9),
        ]
    ),
    5947: BoxConfig(
        box_id=5947,
        name="마스터 상자",
        rewards=[
            BoxRewardConfig(BoxRewardType.EQUIPMENT, 0.6, guaranteed_grade="A"),
            BoxRewardConfig(BoxRewardType.SKILL, 0.4, guaranteed_grade="A"),
        ]
    ),
}


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


# =============================================================================
# 키워드 시너지 시스템
# =============================================================================

@dataclass(frozen=True)
class SynergyTier:
    """시너지 단계"""
    threshold: int
    effect: str
    damage_mult: float = 1.0
    status_duration_bonus: int = 0
    status_chance_bonus: float = 0.0


# 속성 밀도 시너지 (Balance.md 기반)
ATTRIBUTE_SYNERGIES = {
    "화염": [
        SynergyTier(3, "화염 +10%", 1.10),
        SynergyTier(5, "화염 +20%, 화상+1턴", 1.20, status_duration_bonus=1),
        SynergyTier(7, "화염 +35%, 화상 확률 +20%", 1.35, status_chance_bonus=0.20),
        SynergyTier(10, "모든 공격 화상, 화상 2배", 1.50, status_duration_bonus=2),
    ],
    "냉기": [
        SynergyTier(3, "냉기 +10%", 1.10),
        SynergyTier(5, "냉기 +20%, 동결+10%", 1.20, status_chance_bonus=0.10),
        SynergyTier(7, "냉기 +35%, 동결 확률 2배", 1.35, status_chance_bonus=0.35),
        SynergyTier(10, "모든 공격 둔화, 50% 동결", 1.50, status_chance_bonus=0.50),
    ],
    "번개": [
        SynergyTier(3, "번개 +10%", 1.10),
        SynergyTier(5, "번개 +20%, 연쇄+1", 1.20),
        SynergyTier(7, "번개 +35%, 마비 +30%", 1.35, status_chance_bonus=0.30),
        SynergyTier(10, "모든 공격 2체 연쇄", 1.50),
    ],
    "수속성": [
        SynergyTier(3, "회복 +15%", 1.15),
        SynergyTier(5, "회복 +25%", 1.25),
        SynergyTier(7, "회복 +40%", 1.40),
        SynergyTier(10, "힐 2배", 2.0),
    ],
    "신성": [
        SynergyTier(3, "회복 +15%", 1.15),
        SynergyTier(5, "신성 +20%", 1.20),
        SynergyTier(7, "회복 +35%", 1.35),
        SynergyTier(10, "힐 2배", 2.0),
    ],
    "암흑": [
        SynergyTier(3, "흡혈 +5%", 1.0),
        SynergyTier(5, "흡혈 +15%", 1.0),
        SynergyTier(7, "흡혈 +25%", 1.0),
        SynergyTier(10, "흡혈 +40%", 1.0),
    ],
    "물리": [
        SynergyTier(3, "물리 +10%", 1.10),
        SynergyTier(5, "물리 +20%", 1.20),
        SynergyTier(7, "물리 +35%", 1.35),
        SynergyTier(10, "물리 +50%", 1.50),
    ],
}


@dataclass(frozen=True)
class ComboSynergy:
    """복합 시너지"""
    name: str
    description: str
    conditions: dict[str, int]
    damage_mult: float = 1.0
    damage_taken_mult: float = 1.0
    lifesteal_bonus: float = 0.0


COMBO_SYNERGIES = [
    ComboSynergy(
        "원소 조화",
        "모든 속성 +15%",
        {"화염": 2, "냉기": 2, "번개": 2, "수속성": 2},
        damage_mult=1.15
    ),
    ComboSynergy(
        "빛과 어둠",
        "데미지 +25%, 흡혈 +10%",
        {"신성": 4, "암흑": 4},
        damage_mult=1.25,
        lifesteal_bonus=0.10
    ),
    ComboSynergy(
        "글래스 캐논",
        "데미지 +40%, 받는 피해 +20%",
        {"__attack_count__": 8},
        damage_mult=1.40,
        damage_taken_mult=1.20
    ),
    ComboSynergy(
        "철벽 방어",
        "받는 피해 -25%, 데미지 -30%",
        {"__heal_buff_count__": 7},
        damage_mult=0.70,
        damage_taken_mult=0.75
    ),
    ComboSynergy(
        "버서커",
        "공격력 +15%",
        {"__attack_count__": 5, "흡혈": 1},
        damage_mult=1.15
    ),
]
