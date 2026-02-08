"""
데미지 계산 시스템

물리/마법 데미지 계산, 치명타, 명중률, 방어력 무시 등을 처리합니다.
config.py의 DAMAGE 상수를 사용합니다.
"""
import random
from dataclasses import dataclass
from typing import Optional

from config import DAMAGE


@dataclass
class DamageResult:
    """데미지 계산 결과"""

    damage: int
    """최종 데미지"""

    is_critical: bool
    """치명타 여부"""

    is_hit: bool
    """명중 여부"""

    raw_damage: int
    """방어력 적용 전 기본 데미지"""

    defense_reduction: int
    """방어력에 의해 감소된 데미지"""


class DamageCalculator:
    """
    데미지 계산기

    모든 계산은 config.py의 DAMAGE 상수를 기반으로 합니다.
    """

    @staticmethod
    def calculate_physical_damage(
        attack: int,
        defense: int = 0,
        skill_multiplier: float = 1.0,
        armor_penetration: float = 0.0,
        critical_rate: float = DAMAGE.DEFAULT_CRITICAL_RATE,
        critical_multiplier: float = DAMAGE.CRITICAL_MULTIPLIER,
        force_critical: bool = False,
        attribute_multiplier: float = 1.0,
    ) -> DamageResult:
        """
        물리 데미지 계산

        공식: (Attack * skill_multiplier * attribute_multiplier) - (Defense * (1 - armor_pen) * PHYSICAL_DEFENSE_RATIO)

        Args:
            attack: 공격자의 공격력
            defense: 대상의 물리 방어력
            skill_multiplier: 스킬 데미지 배율 (기본 1.0)
            armor_penetration: 방어력 무시 비율 (0.0 ~ MAX_ARMOR_PENETRATION)
            critical_rate: 치명타 확률 (0.0 ~ 1.0)
            critical_multiplier: 치명타 데미지 배율
            force_critical: 강제 치명타 여부
            attribute_multiplier: 속성 배율 (상성 + 피해 증가 효과 포함)

        Returns:
            DamageResult: 계산 결과
        """
        # 방어력 무시 비율 제한
        actual_armor_pen = min(armor_penetration, DAMAGE.MAX_ARMOR_PENETRATION)

        # 기본 데미지 계산 (속성 배율 적용)
        raw_damage = int(attack * skill_multiplier * attribute_multiplier)

        # 방어력 적용
        effective_defense = defense * (1 - actual_armor_pen)
        defense_reduction = int(effective_defense * DAMAGE.PHYSICAL_DEFENSE_RATIO)

        base_damage = raw_damage - defense_reduction

        # 최소 데미지 보장
        base_damage = max(base_damage, DAMAGE.MIN_DAMAGE)

        # 치명타 판정
        is_critical = force_critical or DamageCalculator._roll_critical(critical_rate)
        if is_critical:
            base_damage = int(base_damage * critical_multiplier)

        # 데미지 변동 적용 (±DAMAGE_VARIANCE)
        final_damage = DamageCalculator._apply_variance(base_damage)

        # 최소 데미지 재확인
        final_damage = max(final_damage, DAMAGE.MIN_DAMAGE)

        return DamageResult(
            damage=final_damage,
            is_critical=is_critical,
            is_hit=True,
            raw_damage=raw_damage,
            defense_reduction=defense_reduction,
        )

    @staticmethod
    def calculate_magical_damage(
        ap_attack: int,
        ap_defense: int = 0,
        skill_multiplier: float = 1.0,
        magic_penetration: float = 0.0,
        critical_rate: float = DAMAGE.DEFAULT_CRITICAL_RATE,
        critical_multiplier: float = DAMAGE.CRITICAL_MULTIPLIER,
        force_critical: bool = False,
        attribute_multiplier: float = 1.0,
    ) -> DamageResult:
        """
        마법 데미지 계산

        공식: (AP_Attack * skill_multiplier * attribute_multiplier) - (AP_Defense * (1 - magic_pen) * MAGICAL_DEFENSE_RATIO)

        Args:
            ap_attack: 공격자의 마법 공격력
            ap_defense: 대상의 마법 방어력
            skill_multiplier: 스킬 데미지 배율 (기본 1.0)
            magic_penetration: 마법 관통 비율 (0.0 ~ MAX_ARMOR_PENETRATION)
            critical_rate: 치명타 확률 (0.0 ~ 1.0)
            critical_multiplier: 치명타 데미지 배율
            force_critical: 강제 치명타 여부
            attribute_multiplier: 속성 배율 (상성 + 피해 증가 효과 포함)

        Returns:
            DamageResult: 계산 결과
        """
        # 마법 관통 비율 제한
        actual_magic_pen = min(magic_penetration, DAMAGE.MAX_ARMOR_PENETRATION)

        # 기본 데미지 계산 (속성 배율 적용)
        raw_damage = int(ap_attack * skill_multiplier * attribute_multiplier)

        # 마법 방어력 적용
        effective_defense = ap_defense * (1 - actual_magic_pen)
        defense_reduction = int(effective_defense * DAMAGE.MAGICAL_DEFENSE_RATIO)

        base_damage = raw_damage - defense_reduction

        # 최소 데미지 보장
        base_damage = max(base_damage, DAMAGE.MIN_DAMAGE)

        # 치명타 판정
        is_critical = force_critical or DamageCalculator._roll_critical(critical_rate)
        if is_critical:
            base_damage = int(base_damage * critical_multiplier)

        # 데미지 변동 적용
        final_damage = DamageCalculator._apply_variance(base_damage)

        # 최소 데미지 재확인
        final_damage = max(final_damage, DAMAGE.MIN_DAMAGE)

        return DamageResult(
            damage=final_damage,
            is_critical=is_critical,
            is_hit=True,
            raw_damage=raw_damage,
            defense_reduction=defense_reduction,
        )

    @staticmethod
    def roll_hit(
        accuracy: int = 90,
        evasion: int = 5,
    ) -> bool:
        """
        명중 판정

        공식: hit_rate = accuracy - evasion (최소 5%, 최대 100%)

        Args:
            accuracy: 공격자의 명중률 (%)
            evasion: 대상의 회피율 (%)

        Returns:
            명중 여부
        """
        hit_rate = accuracy - evasion
        hit_rate = max(5, min(100, hit_rate))  # 5% ~ 100%

        return random.randint(1, 100) <= hit_rate

    @staticmethod
    def _roll_critical(critical_rate: float) -> bool:
        """
        치명타 판정

        Args:
            critical_rate: 치명타 확률 (0.0 ~ 1.0)

        Returns:
            치명타 여부
        """
        # 최대 치명타 확률 제한 (80%)
        actual_rate = min(critical_rate, 0.8)
        return random.random() < actual_rate

    @staticmethod
    def _apply_variance(damage: int) -> int:
        """
        데미지 변동 적용 (±DAMAGE_VARIANCE)

        Args:
            damage: 기본 데미지

        Returns:
            변동이 적용된 데미지
        """
        variance = DAMAGE.DAMAGE_VARIANCE
        multiplier = 1 + random.uniform(-variance, variance)
        return int(damage * multiplier)

    @staticmethod
    def calculate_damage_with_hit_check(
        attack: int,
        defense: int = 0,
        skill_multiplier: float = 1.0,
        armor_penetration: float = 0.0,
        critical_rate: float = DAMAGE.DEFAULT_CRITICAL_RATE,
        accuracy: int = 90,
        evasion: int = 5,
        is_physical: bool = True,
    ) -> DamageResult:
        """
        명중 체크를 포함한 데미지 계산

        Args:
            attack: 공격력 (물리 또는 마법)
            defense: 방어력 (물리 또는 마법)
            skill_multiplier: 스킬 배율
            armor_penetration: 방어력 무시 비율
            critical_rate: 치명타 확률
            accuracy: 명중률
            evasion: 회피율
            is_physical: True면 물리, False면 마법

        Returns:
            DamageResult: 계산 결과 (명중 실패 시 damage=0)
        """
        # 명중 판정
        is_hit = DamageCalculator.roll_hit(accuracy, evasion)

        if not is_hit:
            return DamageResult(
                damage=0,
                is_critical=False,
                is_hit=False,
                raw_damage=0,
                defense_reduction=0,
            )

        # 데미지 계산
        if is_physical:
            result = DamageCalculator.calculate_physical_damage(
                attack=attack,
                defense=defense,
                skill_multiplier=skill_multiplier,
                armor_penetration=armor_penetration,
                critical_rate=critical_rate,
            )
        else:
            result = DamageCalculator.calculate_magical_damage(
                ap_attack=attack,
                ap_defense=defense,
                skill_multiplier=skill_multiplier,
                magic_penetration=armor_penetration,
                critical_rate=critical_rate,
            )

        return result
