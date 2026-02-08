"""
스탯 시너지 정의

능력치 투자량에 따라 자동 발동되는 시너지 효과를 정의합니다.
3단계 티어로 구분되며, 조건만 충족하면 모두 중첩 적용됩니다.

데이터 소스: data/synergies.csv
참조: docs/Stats.md
"""
import csv
import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass(frozen=True)
class SynergyCondition:
    """시너지 발동 조건"""
    str_min: int = 0
    int_min: int = 0
    dex_min: int = 0
    vit_min: int = 0
    luk_min: int = 0
    all_min: int = 0  # 모든 스탯이 이 값 이상

    def is_met(self, str_val: int, int_val: int, dex: int, vit: int, luk: int) -> bool:
        if self.all_min > 0:
            return all(v >= self.all_min for v in (str_val, int_val, dex, vit, luk))
        return (
            str_val >= self.str_min
            and int_val >= self.int_min
            and dex >= self.dex_min
            and vit >= self.vit_min
            and luk >= self.luk_min
        )


@dataclass
class SynergyEffect:
    """시너지 효과 (% 기반, 가산 적용)"""
    hp_pct: float = 0          # HP +%
    phys_dmg_pct: float = 0    # 물리 데미지 +%
    mag_dmg_pct: float = 0     # 마법 데미지 +%
    phys_def_pct: float = 0    # 물리 방어 +%
    mag_def_pct: float = 0     # 마법 방어 +%
    accuracy_pct: float = 0    # 명중률 +%
    evasion_pct: float = 0     # 회피율 +%
    crit_rate_pct: float = 0   # 치명타 확률 +%
    crit_dmg_pct: float = 0    # 치명타 데미지 +%
    armor_pen_pct: float = 0   # 방어 관통 +%
    dmg_taken_pct: float = 0   # 받는 피해 % (음수 = 감소)
    speed_flat: int = 0        # 속도 고정 증가
    drop_rate_pct: float = 0   # 드롭률 +%
    lifesteal_pct: float = 0   # 흡혈 +%
    phys_atk_pct: float = 0    # 물리 공격력 +%
    mag_atk_pct: float = 0     # 마법 공격력 +%
    description: str = ""      # 특수 효과 설명 (조건부 등)
    special: Dict[str, Any] = field(default_factory=dict)  # 특수 효과 JSON


@dataclass(frozen=True)
class Synergy:
    """시너지 정의"""
    name: str
    tier: int  # 1, 2, 3
    condition: SynergyCondition
    effect: SynergyEffect


def _safe_float(value: str | None, default: float = 0.0) -> float:
    """CSV 값을 float로 안전 변환"""
    if value is None or not value.strip():
        return default
    try:
        return float(value.strip())
    except ValueError:
        return default


def _safe_int(value: str | None, default: int = 0) -> int:
    """CSV 값을 int로 안전 변환"""
    if value is None or not value.strip():
        return default
    try:
        return int(value.strip())
    except ValueError:
        return default


def _parse_special(value: str | None) -> Dict[str, Any]:
    """CSV의 special 컬럼을 dict로 파싱"""
    if not value or not value.strip():
        return {}
    try:
        return json.loads(value.strip())
    except (json.JSONDecodeError, ValueError):
        return {}


def _load_synergies_from_csv() -> List[Synergy]:
    """data/synergies.csv에서 시너지 데이터 로드"""
    csv_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data", "synergies.csv"
    )

    synergies = []
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            condition = SynergyCondition(
                str_min=_safe_int(row.get("STR", "0")),
                int_min=_safe_int(row.get("INT", "0")),
                dex_min=_safe_int(row.get("DEX", "0")),
                vit_min=_safe_int(row.get("VIT", "0")),
                luk_min=_safe_int(row.get("LUK", "0")),
                all_min=_safe_int(row.get("ALL", "0")),
            )

            effect = SynergyEffect(
                hp_pct=_safe_float(row.get("hp_pct")),
                phys_dmg_pct=_safe_float(row.get("phys_dmg_pct")),
                mag_dmg_pct=_safe_float(row.get("mag_dmg_pct")),
                phys_def_pct=_safe_float(row.get("phys_def_pct")),
                mag_def_pct=_safe_float(row.get("mag_def_pct")),
                accuracy_pct=_safe_float(row.get("accuracy_pct")),
                evasion_pct=_safe_float(row.get("evasion_pct")),
                crit_rate_pct=_safe_float(row.get("crit_rate_pct")),
                crit_dmg_pct=_safe_float(row.get("crit_dmg_pct")),
                armor_pen_pct=_safe_float(row.get("armor_pen_pct")),
                dmg_taken_pct=_safe_float(row.get("dmg_taken_pct")),
                speed_flat=_safe_int(row.get("speed_flat")),
                drop_rate_pct=_safe_float(row.get("drop_rate_pct")),
                lifesteal_pct=_safe_float(row.get("lifesteal_pct")),
                phys_atk_pct=_safe_float(row.get("phys_atk_pct")),
                mag_atk_pct=_safe_float(row.get("mag_atk_pct")),
                description=(row.get("설명") or "").strip(),
                special=_parse_special(row.get("special")),
            )

            synergies.append(Synergy(
                name=row["이름"].strip(),
                tier=_safe_int(row["티어"], 1),
                condition=condition,
                effect=effect,
            ))

    return synergies


# 모듈 로드 시 CSV에서 시너지 데이터 로드
ALL_SYNERGIES = _load_synergies_from_csv()
