"""
능력치 → 전투 스탯 변환

5대 기본 능력치(STR/INT/DEX/VIT/LUK)를 전투 스탯으로 변환합니다.
변환표는 docs/Stats.md 참조.
"""
from dataclasses import dataclass

from config import STAT_CONVERSION as C


@dataclass(frozen=True)
class CombatStatBonus:
    """능력치에서 변환된 전투 스탯 보너스"""
    hp: int = 0
    attack: int = 0
    ap_attack: int = 0
    ad_defense: int = 0
    ap_defense: int = 0
    speed: int = 0
    accuracy: float = 0.0       # %
    evasion: float = 0.0        # %
    crit_rate: float = 0.0      # %
    crit_damage: float = 0.0    # %
    drop_rate: float = 0.0      # %


def convert_abilities_to_combat_stats(
    str_val: int,
    int_val: int,
    dex: int,
    vit: int,
    luk: int,
) -> CombatStatBonus:
    """
    5대 능력치 → 전투 스탯 변환

    Args:
        str_val: 힘 (STR)
        int_val: 지능 (INT)
        dex: 민첩 (DEX)
        vit: 활력 (VIT)
        luk: 행운 (LUK)

    Returns:
        변환된 전투 스탯 보너스
    """
    return CombatStatBonus(
        hp=int(str_val * C.HP_STR + int_val * C.HP_INT + vit * C.HP_VIT),
        attack=int(str_val * C.ATTACK_STR + dex * C.ATTACK_DEX + luk * C.ATTACK_LUK),
        ap_attack=int(int_val * C.AP_ATTACK_INT),
        ad_defense=int(str_val * C.AD_DEFENSE_STR + vit * C.AD_DEFENSE_VIT),
        ap_defense=int(int_val * C.AP_DEFENSE_INT + vit * C.AP_DEFENSE_VIT),
        speed=int(dex * C.SPEED_DEX),
        accuracy=dex * C.ACCURACY_DEX,
        evasion=dex * C.EVASION_DEX + luk * C.EVASION_LUK,
        crit_rate=dex * C.CRIT_RATE_DEX + luk * C.CRIT_RATE_LUK,
        crit_damage=luk * C.CRIT_DAMAGE_LUK,
        drop_rate=luk * C.DROP_RATE_LUK,
    )


def calculate_hp_regen_rate(vit: int) -> float:
    """
    VIT 기반 HP 자연회복률 계산

    Args:
        vit: 활력 능력치

    Returns:
        분당 회복률 (최대 HP 대비 %)
        예: 0.01 = 1%/분, 0.03 = 3%/분
    """
    return C.HP_REGEN_BASE + vit * C.HP_REGEN_VIT
