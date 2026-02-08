"""키워드 시너지 시스템 설정"""
from dataclasses import dataclass


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
