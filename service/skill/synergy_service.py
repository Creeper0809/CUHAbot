"""
시너지 계산 및 적용 서비스

키워드 밀도를 계산하고 활성화된 시너지를 결정합니다.
"""
import logging
from typing import Optional
from dataclasses import dataclass

from models.repos.static_cache import skill_cache_by_id
from config import ATTRIBUTE_SYNERGIES, COMBO_SYNERGIES, SynergyTier, ComboSynergy

logger = logging.getLogger(__name__)


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
        """
        키워드 문자열 파싱

        Args:
            keyword_string: 슬래시로 구분된 키워드 문자열 (예: "화염/화상/셋업")

        Returns:
            키워드 리스트
        """
        if not keyword_string:
            return []
        return [k.strip() for k in keyword_string.split("/") if k.strip()]

    @staticmethod
    def count_keywords(deck: list[int]) -> dict[str, int]:
        """
        덱의 키워드 밀도 계산

        Args:
            deck: 스킬 ID 리스트 (10개)

        Returns:
            키워드별 개수 딕셔너리
        """
        keyword_counts = {}

        for skill_id in deck:
            if skill_id == 0:
                continue

            skill = skill_cache_by_id.get(skill_id)
            if not skill or not hasattr(skill.skill_model, 'keyword'):
                continue

            keywords = SynergyService.parse_keywords(skill.skill_model.keyword)
            for keyword in keywords:
                keyword_counts[keyword] = keyword_counts.get(keyword, 0) + 1

        return keyword_counts

    @staticmethod
    def get_active_synergies(deck: list[int]) -> list[ActiveSynergy]:
        """
        활성화된 시너지 목록 조회

        Args:
            deck: 스킬 ID 리스트 (10개)

        Returns:
            활성화된 시너지 리스트
        """
        keyword_counts = SynergyService.count_keywords(deck)
        active_synergies = []

        # 속성 밀도 시너지
        for attribute, tiers in ATTRIBUTE_SYNERGIES.items():
            count = keyword_counts.get(attribute, 0)

            # 가장 높은 달성 단계 찾기
            for tier in reversed(tiers):
                if count >= tier.threshold:
                    active_synergies.append(ActiveSynergy(
                        name=f"{attribute} ×{tier.threshold}",
                        description=tier.effect,
                        tier=tier
                    ))
                    break

        # 복합 시너지
        for combo in COMBO_SYNERGIES:
            if SynergyService._check_combo_conditions(combo, keyword_counts, deck):
                active_synergies.append(ActiveSynergy(
                    name=combo.name,
                    description=combo.description,
                    combo=combo
                ))

        return active_synergies

    @staticmethod
    def _check_combo_conditions(
        combo: ComboSynergy,
        keyword_counts: dict[str, int],
        deck: list[int]
    ) -> bool:
        """
        복합 시너지 조건 체크

        Args:
            combo: 복합 시너지
            keyword_counts: 키워드별 개수
            deck: 스킬 덱

        Returns:
            조건 만족 여부
        """
        # 특수 조건 처리
        if "__attack_count__" in combo.conditions:
            attack_count = 0
            for skill_id in deck:
                if skill_id == 0:
                    continue
                skill = skill_cache_by_id.get(skill_id)
                if skill:
                    config = skill.skill_model.config
                    components = config.get("components", [])
                    if any(c.get("tag") == "attack" for c in components):
                        attack_count += 1

            if attack_count < combo.conditions["__attack_count__"]:
                return False

        if "__heal_buff_count__" in combo.conditions:
            # heal/buff 타입 카운트 (config에서 추출)
            heal_buff_count = 0
            for skill_id in deck:
                if skill_id == 0:
                    continue
                skill = skill_cache_by_id.get(skill_id)
                if skill:
                    config = skill.skill_model.config
                    components = config.get("components", [])
                    if any(c.get("tag") in ["heal", "buff"] for c in components):
                        heal_buff_count += 1

            if heal_buff_count < combo.conditions["__heal_buff_count__"]:
                return False

        # 일반 키워드 조건
        for keyword, min_count in combo.conditions.items():
            if keyword.startswith("__"):
                continue
            if keyword_counts.get(keyword, 0) < min_count:
                return False

        return True

    @staticmethod
    def calculate_damage_multiplier(deck: list[int], attribute: str) -> float:
        """
        속성별 데미지 배율 계산

        Args:
            deck: 스킬 덱
            attribute: 스킬 속성

        Returns:
            데미지 배율
        """
        active_synergies = SynergyService.get_active_synergies(deck)
        multiplier = 1.0

        for synergy in active_synergies:
            # 속성 밀도 시너지
            if synergy.tier and attribute in synergy.name:
                multiplier *= synergy.tier.damage_mult

            # 복합 시너지
            if synergy.combo:
                multiplier *= synergy.combo.damage_mult

        return multiplier

    @staticmethod
    def calculate_heal_multiplier(deck: list[int]) -> float:
        """
        회복 배율 계산

        Args:
            deck: 스킬 덱

        Returns:
            회복 배율
        """
        active_synergies = SynergyService.get_active_synergies(deck)
        multiplier = 1.0

        for synergy in active_synergies:
            # 회복 관련 시너지만 적용
            if synergy.tier and ("회복" in synergy.description or "힐" in synergy.description):
                multiplier *= synergy.tier.damage_mult

        return multiplier

    @staticmethod
    def calculate_damage_taken_multiplier(deck: list[int]) -> float:
        """
        받는 피해 배율 계산

        Args:
            deck: 스킬 덱

        Returns:
            받는 피해 배율
        """
        active_synergies = SynergyService.get_active_synergies(deck)
        multiplier = 1.0

        for synergy in active_synergies:
            # 복합 시너지의 받는 피해 배율
            if synergy.combo:
                multiplier *= synergy.combo.damage_taken_mult

        return multiplier
