"""
SynergyService

능력치 시너지 평가 및 효과 적용을 담당합니다.
"""
from dataclasses import dataclass
from typing import List

from config.stat_synergies import ALL_SYNERGIES, Synergy, SynergyEffect


@dataclass
class ActiveSynergy:
    """활성화된 시너지"""
    synergy: Synergy
    tier: int
    name: str
    effect: SynergyEffect


class SynergyService:
    """시너지 비즈니스 로직"""

    @staticmethod
    def evaluate_synergies(
        bonus_str: int,
        bonus_int: int,
        bonus_dex: int,
        bonus_vit: int,
        bonus_luk: int,
    ) -> List[ActiveSynergy]:
        """
        능력치 기반 활성 시너지 평가

        Args:
            bonus_str~bonus_luk: 5대 능력치

        Returns:
            활성화된 시너지 목록
        """
        active = []
        for synergy in ALL_SYNERGIES:
            if synergy.condition.is_met(
                bonus_str, bonus_int, bonus_dex, bonus_vit, bonus_luk
            ):
                active.append(ActiveSynergy(
                    synergy=synergy,
                    tier=synergy.tier,
                    name=synergy.name,
                    effect=synergy.effect,
                ))
        return active

    @staticmethod
    def aggregate_synergy_effects(
        active_synergies: List[ActiveSynergy],
    ) -> SynergyEffect:
        """
        활성 시너지 효과를 가산 합산

        Args:
            active_synergies: 활성 시너지 목록

        Returns:
            합산된 시너지 효과
        """
        total = {
            "hp_pct": 0.0,
            "phys_dmg_pct": 0.0,
            "mag_dmg_pct": 0.0,
            "phys_def_pct": 0.0,
            "mag_def_pct": 0.0,
            "accuracy_pct": 0.0,
            "evasion_pct": 0.0,
            "crit_rate_pct": 0.0,
            "crit_dmg_pct": 0.0,
            "armor_pen_pct": 0.0,
            "dmg_taken_pct": 0.0,
            "speed_flat": 0,
            "drop_rate_pct": 0.0,
            "lifesteal_pct": 0.0,
            "phys_atk_pct": 0.0,
            "mag_atk_pct": 0.0,
        }

        for active in active_synergies:
            eff = active.effect
            total["hp_pct"] += eff.hp_pct
            total["phys_dmg_pct"] += eff.phys_dmg_pct
            total["mag_dmg_pct"] += eff.mag_dmg_pct
            total["phys_def_pct"] += eff.phys_def_pct
            total["mag_def_pct"] += eff.mag_def_pct
            total["accuracy_pct"] += eff.accuracy_pct
            total["evasion_pct"] += eff.evasion_pct
            total["crit_rate_pct"] += eff.crit_rate_pct
            total["crit_dmg_pct"] += eff.crit_dmg_pct
            total["armor_pen_pct"] += eff.armor_pen_pct
            total["dmg_taken_pct"] += eff.dmg_taken_pct
            total["speed_flat"] += eff.speed_flat
            total["drop_rate_pct"] += eff.drop_rate_pct
            total["lifesteal_pct"] += eff.lifesteal_pct
            total["phys_atk_pct"] += eff.phys_atk_pct
            total["mag_atk_pct"] += eff.mag_atk_pct

        return SynergyEffect(**total)

    @staticmethod
    def format_synergies_display(
        active_synergies: List[ActiveSynergy],
    ) -> str:
        """
        활성 시너지를 표시용 문자열로 변환

        Args:
            active_synergies: 활성 시너지 목록

        Returns:
            줄바꿈으로 구분된 시너지 표시 문자열
        """
        if not active_synergies:
            return "없음"

        lines = []
        for active in active_synergies:
            tier_mark = f"[T{active.tier}]"
            effects = _format_effect(active.effect)
            lines.append(f"{tier_mark} **{active.name}** → {effects}")

        return "\n".join(lines)


def _format_effect(effect: SynergyEffect) -> str:
    """효과를 읽기 쉬운 문자열로 변환"""
    parts = []

    if effect.hp_pct:
        parts.append(f"HP +{effect.hp_pct}%")
    if effect.phys_dmg_pct:
        parts.append(f"물리 데미지 +{effect.phys_dmg_pct}%")
    if effect.mag_dmg_pct:
        parts.append(f"마법 데미지 +{effect.mag_dmg_pct}%")
    if effect.phys_def_pct:
        parts.append(f"물리 방어 +{effect.phys_def_pct}%")
    if effect.mag_def_pct:
        parts.append(f"마법 방어 +{effect.mag_def_pct}%")
    if effect.accuracy_pct:
        parts.append(f"명중 +{effect.accuracy_pct}%")
    if effect.evasion_pct:
        parts.append(f"회피 +{effect.evasion_pct}%")
    if effect.crit_rate_pct:
        parts.append(f"치확 +{effect.crit_rate_pct}%")
    if effect.crit_dmg_pct:
        parts.append(f"치뎀 +{effect.crit_dmg_pct}%")
    if effect.armor_pen_pct:
        parts.append(f"관통 +{effect.armor_pen_pct}%")
    if effect.dmg_taken_pct:
        parts.append(f"받는 피해 {effect.dmg_taken_pct:+}%")
    if effect.speed_flat:
        parts.append(f"속도 +{effect.speed_flat}")
    if effect.drop_rate_pct:
        parts.append(f"드롭률 +{effect.drop_rate_pct}%")
    if effect.lifesteal_pct:
        parts.append(f"흡혈 +{effect.lifesteal_pct}%")
    if effect.phys_atk_pct:
        parts.append(f"물리 공격 +{effect.phys_atk_pct}%")
    if effect.mag_atk_pct:
        parts.append(f"마법 공격 +{effect.mag_atk_pct}%")
    if effect.description:
        parts.append(effect.description)

    return ", ".join(parts) if parts else "없음"
