"""키워드 시너지 시스템 설정"""
from dataclasses import dataclass


@dataclass(frozen=True)
class SynergyTier:
    """시너지 단계"""
    threshold: int
    effect: str
    damage_mult: float = 1.0
    heal_mult: float = 1.0
    damage_taken_mult: float = 1.0
    status_duration_bonus: int = 0
    status_chance_bonus: float = 0.0
    lifesteal_bonus: float = 0.0
    finisher_damage_mult: float = 1.0
    ultimate_damage_mult: float = 1.0


# 속성 밀도 시너지 (3/5/7/10)
ATTRIBUTE_SYNERGIES = {
    "화염": [
        SynergyTier(3, "화염 +10%", damage_mult=1.10),
        SynergyTier(5, "화염 +20%, 화상+1턴", damage_mult=1.20, status_duration_bonus=1),
        SynergyTier(7, "화염 +35%, 화상 확률 +20%", damage_mult=1.35, status_chance_bonus=0.20),
        SynergyTier(10, "모든 공격 화상 부여, 화상 2배", damage_mult=1.50, status_duration_bonus=2),
    ],
    "냉기": [
        SynergyTier(3, "냉기 +10%", damage_mult=1.10),
        SynergyTier(5, "냉기 +20%, 동결+10%", damage_mult=1.20, status_chance_bonus=0.10),
        SynergyTier(7, "냉기 +35%, 동결 확률 2배", damage_mult=1.35, status_chance_bonus=0.35),
        SynergyTier(10, "모든 공격 둔화, 50% 동결", damage_mult=1.50, status_chance_bonus=0.50),
    ],
    "번개": [
        SynergyTier(3, "번개 +10%", damage_mult=1.10),
        SynergyTier(5, "번개 +20%, 연쇄+1", damage_mult=1.20),
        SynergyTier(7, "번개 +35%, 마비 +30%", damage_mult=1.35, status_chance_bonus=0.30),
        SynergyTier(10, "모든 공격 2체 연쇄, 마비+30%", damage_mult=1.50, status_chance_bonus=0.30),
    ],
    "수속성": [
        SynergyTier(3, "회복 +15%", heal_mult=1.15),
        SynergyTier(5, "회복 +25%, 턴당 HP3%", heal_mult=1.25),
        SynergyTier(7, "회복 +40%, 화염 -30%", heal_mult=1.40, damage_taken_mult=0.90),
        SynergyTier(10, "매 턴 HP 10%, 힐 2배", heal_mult=2.00, damage_taken_mult=0.85),
    ],
    "신성": [
        SynergyTier(3, "회복 +15%", heal_mult=1.15),
        SynergyTier(5, "신성 +20%, 언데드+30%", damage_mult=1.20),
        SynergyTier(7, "디버프 -50%, 회복 +35%", heal_mult=1.35),
        SynergyTier(10, "디버프 면역, 언데드 2배", heal_mult=1.50, damage_taken_mult=0.90),
    ],
    "암흑": [
        SynergyTier(3, "흡혈 +5%", lifesteal_bonus=0.05),
        SynergyTier(5, "흡혈 +15%, 저주+1턴", lifesteal_bonus=0.15, status_duration_bonus=1),
        SynergyTier(7, "흡혈 +25%, 처치 시 HP10%", lifesteal_bonus=0.25),
        SynergyTier(10, "흡혈 +40%, 킬당 공격+5%", lifesteal_bonus=0.40),
    ],
    "물리": [
        SynergyTier(3, "물리 +10%", damage_mult=1.10),
        SynergyTier(5, "물리 +20%", damage_mult=1.20),
        SynergyTier(7, "물리 +35%", damage_mult=1.35),
        SynergyTier(10, "물리 +50%", damage_mult=1.50),
    ],
}


# 효과 키워드 밀도 시너지 (3/5)
EFFECT_SYNERGIES = {
    "잠식": [
        SynergyTier(3, "잠식 스택당 방어 감소 +2%"),
        SynergyTier(5, "잠식 5스택 시 방어력 0 취급"),
    ],
    "침수": [
        SynergyTier(3, "침수 지속 +1턴", status_duration_bonus=1),
        SynergyTier(5, "침수 대상 번개 피해 3배"),
    ],
    "둔화": [
        SynergyTier(3, "둔화 지속 +1턴", status_duration_bonus=1),
        SynergyTier(5, "둔화 중 회피율 0"),
    ],
    "동결": [
        SynergyTier(3, "동결 확률 +10%", status_chance_bonus=0.10),
        SynergyTier(5, "동결 지속 +1턴", status_duration_bonus=1),
    ],
    "기절": [
        SynergyTier(3, "기절 확률 +10%", status_chance_bonus=0.10),
        SynergyTier(5, "기절 해제 직후 1턴 둔화 부여"),
    ],
    "출혈": [
        SynergyTier(3, "출혈 데미지 +15%", damage_mult=1.15),
        SynergyTier(5, "출혈 스택 상한 +3"),
    ],
    "콤보": [
        SynergyTier(3, "콤보 유지시간 +1턴", status_duration_bonus=1),
        SynergyTier(5, "콤보 피니셔 데미지 +25%", finisher_damage_mult=1.25),
    ],
    "파쇄": [
        SynergyTier(3, "파쇄 데미지 +20%", damage_mult=1.20),
        SynergyTier(5, "파쇄 시 방어력 50% 영구 감소"),
    ],
    "중독": [
        SynergyTier(3, "중독 데미지 +15%", damage_mult=1.15),
        SynergyTier(5, "중독 스택당 회복량 -5%"),
    ],
    "저주": [
        SynergyTier(3, "저주 효과 +10%", status_chance_bonus=0.10),
        SynergyTier(5, "저주 대상 버프 지속 -1턴"),
    ],
    "흡혈": [
        SynergyTier(3, "흡혈량 +5%", lifesteal_bonus=0.05),
        SynergyTier(5, "흡혈량 +15%", lifesteal_bonus=0.15),
    ],
    "감염": [
        SynergyTier(3, "감염 전파 범위 +1"),
        SynergyTier(5, "감염 전파 시 스택 100% 유지"),
    ],
    "화상": [
        SynergyTier(3, "화상 데미지 +15%", damage_mult=1.15),
        SynergyTier(5, "화상 스택 상한 +3"),
    ],
    "소각": [
        SynergyTier(3, "소각 시 버프 제거 +1개"),
        SynergyTier(5, "소각된 버프당 데미지 +20%", damage_mult=1.20),
    ],
    "연소": [
        SynergyTier(3, "연소 폭발 데미지 +20%", damage_mult=1.20),
        SynergyTier(5, "연소 후 화상 1스택 재부여"),
    ],
    "감전": [
        SynergyTier(3, "연쇄 전이 대상 +1"),
        SynergyTier(5, "전이 데미지 100% (감소 없음)", damage_mult=1.10),
    ],
    "마비": [
        SynergyTier(3, "마비 확률 +10%", status_chance_bonus=0.10),
        SynergyTier(5, "마비 지속 +1턴", status_duration_bonus=1),
    ],
    "과부하": [
        SynergyTier(3, "과부하 폭발 범위 +1"),
        SynergyTier(5, "소모 상태당 데미지 +30%", damage_mult=1.30),
    ],
    "표식": [
        SynergyTier(3, "표식 데미지 증가량 +5%", damage_mult=1.05),
        SynergyTier(5, "표식 대상 치명타율 +15%"),
    ],
    "재생": [
        SynergyTier(3, "재생량 +20%", heal_mult=1.20),
        SynergyTier(5, "재생 스택 비례 받는 피해 -10%", damage_taken_mult=0.90),
    ],
    "보호막": [
        SynergyTier(3, "보호막 효율 +20%", damage_taken_mult=0.90),
        SynergyTier(5, "초과 회복 → 보호막 전환", damage_taken_mult=0.85),
    ],
    "환류": [
        SynergyTier(3, "환류 버프 강화량 +5%", heal_mult=1.05),
        SynergyTier(5, "환류 시 HP 5% 추가 회복", heal_mult=1.10),
    ],
    "축복": [
        SynergyTier(3, "축복 효과 +10%", heal_mult=1.10),
        SynergyTier(5, "축복 지속 +2턴", status_duration_bonus=2),
    ],
    "정화": [
        SynergyTier(3, "정화 시 해제 수 +1"),
        SynergyTier(5, "정화 시 해제 디버프당 HP 3% 회복", heal_mult=1.10),
    ],
    "결계": [
        SynergyTier(3, "결계 무효화 횟수 +1", damage_taken_mult=0.95),
        SynergyTier(5, "결계 파괴 시 정화 자동 발동", damage_taken_mult=0.90),
    ],
    "공명": [
        SynergyTier(3, "공명 지속 +1턴", status_duration_bonus=1),
        SynergyTier(5, "공명 중 버프 효과 3배", heal_mult=1.20),
    ],
}


@dataclass(frozen=True)
class ComboSynergy:
    """복합 시너지"""
    name: str
    description: str
    conditions: dict[str, int]
    damage_mult: float = 1.0
    heal_mult: float = 1.0
    damage_taken_mult: float = 1.0
    lifesteal_bonus: float = 0.0
    status_chance_bonus: float = 0.0
    status_duration_bonus: int = 0
    finisher_damage_mult: float = 1.0
    ultimate_damage_mult: float = 1.0
    berserker_low_hp_damage_mult: float = 1.0
    berserker_low_hp_threshold: float = 0.0


COMBO_SYNERGIES = [
    ComboSynergy(
        "원소 조화",
        "모든 속성 +15%",
        {"화염": 2, "냉기": 2, "번개": 2, "수속성": 2},
        damage_mult=1.15,
    ),
    ComboSynergy(
        "빛과 어둠",
        "데미지 +25%, 흡혈 +10%",
        {"신성": 4, "암흑": 4},
        damage_mult=1.25,
        lifesteal_bonus=0.10,
    ),
    ComboSynergy(
        "글래스 캐논",
        "데미지 +40%, 받는 피해 +20%",
        {"__attack_count__": 8},
        damage_mult=1.40,
        damage_taken_mult=1.20,
    ),
    ComboSynergy(
        "철벽 방어",
        "받는 피해 -25%, 데미지 -30%",
        {"__heal_buff_count__": 7},
        damage_mult=0.70,
        damage_taken_mult=0.75,
    ),
    ComboSynergy(
        "버서커",
        "공격력 +15%, HP 50% 이하 시 +30%",
        {"__attack_count__": 5, "흡혈": 1},
        damage_mult=1.15,
        berserker_low_hp_damage_mult=1.30,
        berserker_low_hp_threshold=0.50,
    ),
    ComboSynergy(
        "서바이버",
        "받는 피해 -15%, 힐 +20%",
        {"__heal_count__": 4},
        damage_taken_mult=0.85,
        heal_mult=1.20,
    ),
    ComboSynergy(
        "상태이상 마스터",
        "상태이상 확률 +15%, 지속 +1턴",
        {"__distinct_effect_count__": 3},
        status_chance_bonus=0.15,
        status_duration_bonus=1,
    ),
    ComboSynergy(
        "셋업-피니셔 특화",
        "피니셔 데미지 +25%",
        {"__setup_count__": 3, "__finisher_count__": 3},
        finisher_damage_mult=1.25,
    ),
    ComboSynergy(
        "궁극기 특화",
        "궁극기 데미지 +50%",
        {"__ultimate_count__": 2},
        ultimate_damage_mult=1.50,
    ),
]
