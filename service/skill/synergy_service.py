"""
시너지 계산 및 적용 서비스

키워드 밀도를 계산하고 활성화된 시너지를 결정합니다.
"""
import logging
from dataclasses import dataclass
from typing import Optional

from config import (
    ATTRIBUTE_SYNERGIES, EFFECT_SYNERGIES, COMBO_SYNERGIES,
    SynergyTier, ComboSynergy, ULTIMATE_SKILL_IDS,
)
from models import UserStatEnum
from models.repos.static_cache import skill_cache_by_id

logger = logging.getLogger(__name__)

_STATUS_KEYWORD_MAP = {
    "burn": "화상",
    "submerge": "침수",
    "slow": "둔화",
    "freeze": "동결",
    "stun": "기절",
    "bleed": "출혈",
    "combo": "콤보",
    "shatter": "파쇄",
    "poison": "중독",
    "curse": "저주",
    "infection": "감염",
    "shock": "감전",
    "paralyze": "마비",
    "overload": "과부하",
    "mark": "표식",
    "regen": "재생",
    "shield": "보호막",
}

_STATUS_ATTRIBUTE_MAP = {
    "burn": "화염",
    "slow": "냉기",
    "freeze": "냉기",
    "shock": "번개",
    "paralyze": "번개",
    "submerge": "수속성",
    "erode": "수속성",
    "curse": "암흑",
    "poison": "암흑",
    "infection": "암흑",
}


@dataclass
class ActiveSynergy:
    """활성화된 시너지"""
    name: str
    description: str
    tier: Optional[SynergyTier] = None
    combo: Optional[ComboSynergy] = None


class SynergyService:
    """시너지 계산 서비스"""

    @staticmethod
    def parse_keywords(keyword_string: str) -> list[str]:
        if not keyword_string:
            return []
        return [k.strip() for k in keyword_string.split("/") if k.strip()]

    @staticmethod
    def count_keywords(deck: list[int]) -> dict[str, int]:
        keyword_counts: dict[str, int] = {}
        for skill_id in deck:
            if skill_id == 0:
                continue
            keywords = SynergyService._get_skill_keywords(skill_id)
            for keyword in keywords:
                keyword_counts[keyword] = keyword_counts.get(keyword, 0) + 1
        return keyword_counts

    @staticmethod
    def get_active_synergies(deck: list[int]) -> list[ActiveSynergy]:
        keyword_counts = SynergyService.count_keywords(deck)
        active_synergies: list[ActiveSynergy] = []

        # 마스터리(10개) 배타 규칙:
        # 마스터리 달성 시 해당 속성만 적용하고, 다른 속성 밀도 시너지는 제외한다.
        mastery_attr = SynergyService._pick_mastery_attribute(keyword_counts)

        for attribute, tiers in ATTRIBUTE_SYNERGIES.items():
            count = keyword_counts.get(attribute, 0)
            for tier in reversed(tiers):
                if count >= tier.threshold:
                    if mastery_attr and (attribute != mastery_attr or tier.threshold < 10):
                        break
                    active_synergies.append(
                        ActiveSynergy(
                            name=f"{attribute} ×{tier.threshold}",
                            description=tier.effect,
                            tier=tier,
                        )
                    )
                    break

        # 효과 키워드 밀도 시너지 (3/5)
        for effect_keyword, tiers in EFFECT_SYNERGIES.items():
            count = keyword_counts.get(effect_keyword, 0)
            for tier in reversed(tiers):
                if count >= tier.threshold:
                    active_synergies.append(
                        ActiveSynergy(
                            name=f"{effect_keyword} ×{tier.threshold}",
                            description=tier.effect,
                            tier=tier,
                        )
                    )
                    break

        # 조합 시너지
        for combo in COMBO_SYNERGIES:
            if SynergyService._check_combo_conditions(combo, keyword_counts, deck):
                active_synergies.append(
                    ActiveSynergy(
                        name=combo.name,
                        description=combo.description,
                        combo=combo,
                    )
                )

        return active_synergies

    @staticmethod
    def _pick_mastery_attribute(keyword_counts: dict[str, int]) -> str | None:
        for attribute in ATTRIBUTE_SYNERGIES:
            if keyword_counts.get(attribute, 0) >= 10:
                return attribute
        return None

    @staticmethod
    def _check_combo_conditions(
        combo: ComboSynergy,
        keyword_counts: dict[str, int],
        deck: list[int],
    ) -> bool:
        counts = SynergyService._count_special_conditions(deck)

        for key, required in combo.conditions.items():
            if key.startswith("__"):
                if counts.get(key, 0) < required:
                    return False
                continue
            if keyword_counts.get(key, 0) < required:
                return False
        return True

    @staticmethod
    def _count_special_conditions(deck: list[int]) -> dict[str, int]:
        counts = {
            "__attack_count__": 0,
            "__heal_buff_count__": 0,
            "__heal_count__": 0,
            "__setup_count__": 0,
            "__finisher_count__": 0,
            "__ultimate_count__": 0,
            "__distinct_effect_count__": 0,
        }
        effect_kinds: set[str] = set()

        for skill_id in deck:
            if skill_id == 0:
                continue
            skill = skill_cache_by_id.get(skill_id)
            if not skill:
                continue

            components = getattr(skill.skill_model, "config", {}).get("components", [])
            if any(comp.get("tag") == "attack" for comp in components):
                counts["__attack_count__"] += 1
            if any(comp.get("tag") in {"heal", "buff"} for comp in components):
                counts["__heal_buff_count__"] += 1
            if any(comp.get("tag") == "heal" for comp in components):
                counts["__heal_count__"] += 1

            keywords = SynergyService.parse_keywords(getattr(skill.skill_model, "keyword", ""))
            if "셋업" in keywords:
                counts["__setup_count__"] += 1
            if "피니셔" in keywords:
                counts["__finisher_count__"] += 1

            if SynergyService._is_ultimate_skill(skill_id, skill):
                counts["__ultimate_count__"] += 1

            for keyword in keywords:
                if keyword in EFFECT_SYNERGIES:
                    effect_kinds.add(keyword)

        counts["__distinct_effect_count__"] = len(effect_kinds)
        return counts

    @staticmethod
    def _is_ultimate_skill(skill_id: int, skill) -> bool:
        if skill_id in ULTIMATE_SKILL_IDS:
            return True
        if 5000 <= skill_id < 6000:
            return True
        config = getattr(skill.skill_model, "config", {})
        return isinstance(config, dict) and "ultimate" in config

    @staticmethod
    def _get_skill_keywords(skill_id: int) -> list[str]:
        skill = skill_cache_by_id.get(skill_id)
        if not skill:
            return []
        return SynergyService.parse_keywords(getattr(skill.skill_model, "keyword", ""))

    @staticmethod
    def _get_current_skill_keywords(current_skill) -> set[str]:
        if not current_skill:
            return set()
        keyword_text = getattr(current_skill.skill_model, "keyword", "")
        return set(SynergyService.parse_keywords(keyword_text))

    @staticmethod
    def _is_current_skill_ultimate(current_skill) -> bool:
        if not current_skill:
            return False
        sid = getattr(current_skill, "id", 0)
        if sid in ULTIMATE_SKILL_IDS or 5000 <= sid < 6000:
            return True
        config = getattr(current_skill.skill_model, "config", {})
        return isinstance(config, dict) and "ultimate" in config

    @staticmethod
    def _synergy_key(name: str) -> str:
        if " ×" in name:
            return name.split(" ×", 1)[0]
        return name

    @staticmethod
    def _is_low_hp(actor, threshold: float) -> bool:
        if not actor or threshold <= 0:
            return False
        stat = actor.get_stat()
        max_hp = stat.get(UserStatEnum.HP, getattr(actor, "hp", 1))
        if max_hp <= 0:
            return False
        return (getattr(actor, "now_hp", max_hp) / max_hp) <= threshold

    @staticmethod
    def calculate_damage_multiplier(
        deck: list[int],
        attribute: str,
        actor=None,
        current_skill=None,
    ) -> float:
        active_synergies = SynergyService.get_active_synergies(deck)
        current_keywords = SynergyService._get_current_skill_keywords(current_skill)
        is_finisher = "피니셔" in current_keywords
        is_ultimate = SynergyService._is_current_skill_ultimate(current_skill)
        multiplier = 1.0

        for synergy in active_synergies:
            if synergy.tier:
                key = SynergyService._synergy_key(synergy.name)
                if key == attribute:
                    multiplier *= synergy.tier.damage_mult
                if key in current_keywords:
                    multiplier *= synergy.tier.damage_mult
                    if is_finisher:
                        multiplier *= synergy.tier.finisher_damage_mult
                    if is_ultimate:
                        multiplier *= synergy.tier.ultimate_damage_mult
            if synergy.combo:
                multiplier *= synergy.combo.damage_mult
                if is_finisher:
                    multiplier *= synergy.combo.finisher_damage_mult
                if is_ultimate:
                    multiplier *= synergy.combo.ultimate_damage_mult
                if SynergyService._is_low_hp(actor, synergy.combo.berserker_low_hp_threshold):
                    multiplier *= synergy.combo.berserker_low_hp_damage_mult

        return multiplier

    @staticmethod
    def calculate_heal_multiplier(deck: list[int], actor=None, current_skill=None) -> float:
        active_synergies = SynergyService.get_active_synergies(deck)
        current_keywords = SynergyService._get_current_skill_keywords(current_skill)
        multiplier = 1.0

        for synergy in active_synergies:
            if synergy.tier:
                key = SynergyService._synergy_key(synergy.name)
                if key in ATTRIBUTE_SYNERGIES:
                    multiplier *= synergy.tier.heal_mult
                elif key in current_keywords:
                    multiplier *= synergy.tier.heal_mult
            if synergy.combo:
                multiplier *= synergy.combo.heal_mult
        return multiplier

    @staticmethod
    def calculate_damage_taken_multiplier(deck: list[int]) -> float:
        active_synergies = SynergyService.get_active_synergies(deck)
        multiplier = 1.0

        for synergy in active_synergies:
            if synergy.tier:
                multiplier *= synergy.tier.damage_taken_mult
            if synergy.combo:
                multiplier *= synergy.combo.damage_taken_mult
        return multiplier

    @staticmethod
    def calculate_status_chance_bonus(
        deck: list[int],
        status_type: str,
        current_skill=None,
    ) -> float:
        active_synergies = SynergyService.get_active_synergies(deck)
        current_keywords = SynergyService._get_current_skill_keywords(current_skill)
        status_keyword = _STATUS_KEYWORD_MAP.get(status_type, "")
        related_attribute = _STATUS_ATTRIBUTE_MAP.get(status_type, "")
        bonus = 0.0

        for synergy in active_synergies:
            if synergy.tier:
                key = SynergyService._synergy_key(synergy.name)
                if key == status_keyword:
                    bonus += synergy.tier.status_chance_bonus
                elif key == related_attribute and related_attribute in current_keywords:
                    bonus += synergy.tier.status_chance_bonus
            if synergy.combo:
                bonus += synergy.combo.status_chance_bonus
        return bonus

    @staticmethod
    def calculate_status_duration_bonus(
        deck: list[int],
        status_type: str,
        current_skill=None,
    ) -> int:
        active_synergies = SynergyService.get_active_synergies(deck)
        current_keywords = SynergyService._get_current_skill_keywords(current_skill)
        status_keyword = _STATUS_KEYWORD_MAP.get(status_type, "")
        related_attribute = _STATUS_ATTRIBUTE_MAP.get(status_type, "")
        bonus = 0

        for synergy in active_synergies:
            if synergy.tier:
                key = SynergyService._synergy_key(synergy.name)
                if key == status_keyword:
                    bonus += synergy.tier.status_duration_bonus
                elif key == related_attribute and related_attribute in current_keywords:
                    bonus += synergy.tier.status_duration_bonus
            if synergy.combo:
                bonus += synergy.combo.status_duration_bonus
        return bonus

    @staticmethod
    def calculate_lifesteal_bonus(deck: list[int]) -> float:
        active_synergies = SynergyService.get_active_synergies(deck)
        bonus = 0.0
        for synergy in active_synergies:
            if synergy.tier:
                bonus += synergy.tier.lifesteal_bonus
            if synergy.combo:
                bonus += synergy.combo.lifesteal_bonus
        return bonus
