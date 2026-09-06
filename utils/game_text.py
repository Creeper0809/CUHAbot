"""Canonical Korean labels for player-facing game text.

Runtime configuration deliberately uses stable English keys.  Discord output must
never expose those keys directly, so every renderer and combat log goes through
this module.
"""
from __future__ import annotations

from collections.abc import Iterable
import re
from typing import Any


STATUS_LABELS = {
    "bleed": "출혈", "blessing": "축복", "blind": "실명", "buff": "강화 효과",
    "buff_duration": "강화 지속시간", "burn": "화상", "charge": "전하",
    "charm": "매혹", "combo": "연계", "conviction": "신념", "curse": "저주",
    "death_mark": "죽음의 표식", "dot": "지속 피해", "ember": "불씨",
    "erode": "침식", "fear": "공포", "freeze": "빙결", "frost": "서리",
    "infection": "감염", "mark": "표식", "momentum": "기세", "paralyze": "마비",
    "poison": "중독", "root": "속박", "shield": "보호막", "shock": "감전",
    "slow": "둔화", "soul": "영혼", "stun": "기절", "submerge": "침수",
    "taunt": "도발", "tide": "조류",
}

STAT_LABELS = {
    "attack": "공격력", "attack_percent": "공격력", "attack_bonus": "공격력",
    "ap_attack": "마법공격력", "ap_attack_percent": "마법공격력",
    "hp": "최대 HP", "hp_percent": "최대 HP", "defense": "방어력",
    "defense_percent": "방어력", "speed": "속도", "speed_percent": "속도",
    "crit_rate": "치명타 확률", "crit_damage": "치명타 피해", "accuracy": "명중률",
    "evasion": "회피율", "evasion_percent": "회피율", "armor_pen": "방어 관통",
    "heal_received": "받는 회복량", "damage_reduction": "받는 피해",
    "damage_reduce": "받는 피해", "damage_bonus": "주는 피해", "all_resist": "모든 속성 저항",
    "status_resist": "상태이상 저항", "all_stats": "모든 능력치",
    "buff_duration": "강화 효과 지속시간", "debuff_duration": "해로운 효과 지속시간",
    "skill_bonus": "스킬 효과", "low_hp_skill_bonus": "낮은 HP에서 스킬 효과",
    "holy_bonus": "신성 피해", "gold_bonus": "골드 획득량", "exp_bonus": "경험치 획득량",
    "drop_rate": "아이템 발견 확률", "rare_drop": "희귀 아이템 발견 확률",
    "shop_discount": "상점 할인율", "sell_bonus": "판매 가격", "enhance_luck": "강화 성공률",
    "regen_percent": "턴당 HP 재생", "lifesteal": "흡혈", "weakness_bonus": "약점 피해",
    "execute_bonus": "처형 피해", "low_hp_bonus": "낮은 HP에서 피해",
    "hit_stack_attack": "공격 적중당 공격력", "all_element": "모든 속성 피해",
    "poison_chance": "중독 부여 확률", "poison_damage": "중독 피해",
    "slow_chance": "둔화 부여 확률", "paralyze_chance": "마비 부여 확률",
    "trap_detect": "함정 발견 확률", "trap_damage_reduce": "함정 피해 감소",
    "secret_find": "비밀방 발견 확률", "ambush_reduce": "기습 위험 감소",
    "chest_find": "상자 발견 확률", "grade_up_chance": "등급 상승 확률",
    "grade_up2_chance": "두 단계 등급 상승 확률", "kill_heal": "처치 시 HP 회복",
    "reduction_percent": "해로운 효과 감소율", "heal_block": "회복 차단",
    "skill_seal": "스킬 봉인", "invincible": "무적", "death_mark": "죽음의 표식",
    "self_destruct": "자폭 준비", "effect_reverse": "효과 반전", "buff_reverse": "강화 효과 반전",
    "random": "무작위 능력치", "random_all": "모든 능력치 중 무작위",
    "random_redistribute": "능력치 무작위 재분배", "all": "모든 능력치",
    "all_debuffs": "모든 해로운 효과", "taunt": "도발", "hit_stack_max": "누적 공격력 상한",
    "execute_threshold": "처형 발동 HP", "low_hp_threshold": "낮은 HP 기준",
    "execute_crit_threshold": "확정 치명타 HP 기준",
}

TARGET_LABELS = {
    "single": "적 1명", "enemy": "적 1명", "self": "자신", "ally": "아군 1명",
    "all": "모든 적", "all_enemies": "모든 적", "all_enemy": "모든 적", "enemies": "모든 적",
    "all_allies": "모든 아군", "all_ally": "모든 아군", "allies": "모든 아군",
    "random": "무작위 적",
}

FAMILY_LABELS = {
    "fire_combustion": "화염·연소", "frost_shatter": "냉기·파쇄",
    "holy_judgement": "신성·심판", "neutral_technique": "물리·범용 전투",
    "neutral_utility": "범용 지원", "shadow_sacrifice": "암흑·희생",
    "storm_overload": "번개·과부하", "tide_cycle": "수속성·순환",
    "cross_family": "복합 연계",
}

ROLE_LABELS = {
    "basic": "기본기", "bridge": "계열 연결기", "converter": "상태 변환기",
    "defender": "방어기", "engine": "지속 엔진", "finisher": "피니셔",
    "passive": "지속 패시브", "payoff": "조건 소비기", "phase_capstone": "페이즈 결정기",
    "pressure": "압박기", "primer": "연계 생성기", "punish": "전조 처벌기",
    "recovery": "회복기", "setup": "준비기", "stacker": "누적기", "summon": "소환기",
    "sustain": "유지기", "utility": "보조기",
}

TYPE_LABELS = {"active": "액티브", "passive": "패시브", "ultimate": "궁극기"}
CATEGORY_LABELS = {
    "attack": "공격", "heal": "회복", "buff": "강화", "debuff": "약화",
    "combat": "전투 패시브", "exploration": "탐험", "economic": "경제",
    "special": "특수", "ultimate": "궁극기", "utility": "보조",
}

INTERNAL_TERM_LABELS = {
    **STATUS_LABELS, **STAT_LABELS, **FAMILY_LABELS, **ROLE_LABELS,
    "AP_Attack": "마법공격력", "AD_Defense": "물리방어", "AP_Defense": "마법방어",
    "passive_buff": "지속 패시브", "passive_regen": "턴당 재생",
    "conditional_passive": "조건부 패시브", "passive_aura_debuff": "약화 오라",
    "passive_debuff_reduction": "해로운 효과 감소", "on_death_summon": "사망 시 소환",
    "self_damage": "HP 소모", "self_destruct": "자폭", "resource_payoff": "자원 소비",
    "status_transform": "상태 변환", "combat_resource": "전투 자원",
    "attack": "공격", "status": "상태이상", "debuff": "약화", "heal": "회복",
    "cleanse": "정화", "combo": "연계", "lifesteal": "흡혈", "consume": "소비",
    "summon": "소환", "shield": "보호막", "revive": "부활",
    "player_shadow": "플레이어의 그림자", "double_cast": "연속 시전",
    "death_resist": "치명상 저항", "material_double": "재료 추가 획득",
    "shop_rare": "상점 희귀 상품", "heal_seal": "회복 봉인",
    "cc_immune": "행동 불가 면역", "invincible_turns": "조건부 무적",
}
_INTERNAL_TERM_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_])(" + "|".join(
        re.escape(key) for key in sorted(INTERNAL_TERM_LABELS, key=len, reverse=True)
    ) + r")(?![A-Za-z0-9_])"
)


def status_label(value: Any) -> str:
    text = str(value or "")
    return STATUS_LABELS.get(text, text if not _looks_internal(text) else "특수 상태")


def stat_label(value: Any) -> str:
    text = str(value or "")
    return STAT_LABELS.get(text, STATUS_LABELS.get(text, text if not _looks_internal(text) else "특수 효과"))


def target_label(value: Any) -> str:
    text = str(value or "single")
    return TARGET_LABELS.get(text, "대상")


def design_tag_label(value: Any) -> str:
    return STATUS_LABELS.get(str(value), stat_label(value))


def design_tags_text(values: Iterable[Any]) -> str:
    return ", ".join(design_tag_label(value) for value in values)


def family_label(value: Any) -> str:
    return FAMILY_LABELS.get(str(value), "복합 계열")


def role_label(value: Any) -> str:
    return ROLE_LABELS.get(str(value), "특수 역할")


def type_label(value: Any) -> str:
    return TYPE_LABELS.get(str(value), str(value or "-") if not _looks_internal(str(value or "")) else "특수")


def category_label(value: Any) -> str:
    return CATEGORY_LABELS.get(str(value), str(value or "-") if not _looks_internal(str(value or "")) else "특수")


def localize_internal_terms(value: Any) -> str:
    """Translate stable config identifiers embedded in legacy authored prose."""
    text = str(value or "")
    return _INTERNAL_TERM_PATTERN.sub(lambda match: INTERNAL_TERM_LABELS[match.group(1)], text)


def turns_text(value: Any) -> str:
    turns = int(float(value or 0))
    return "전투 종료까지" if turns >= 99 else f"{turns}턴"


def percent_text(value: Any, *, signed: bool = False) -> str:
    number = float(value or 0)
    prefix = "+" if signed and number > 0 else ""
    return f"{prefix}{number * 100:.2f}".rstrip("0").rstrip(".") + "%"


def _looks_internal(text: str) -> bool:
    return "_" in text or (text.isascii() and text.isalpha())
