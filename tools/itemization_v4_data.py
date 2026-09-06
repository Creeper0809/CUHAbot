"""Deterministically add explicit V4 set keys and the five missing set contracts."""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EQUIPMENT = ROOT / "data" / "items_equipment.csv"
SETS = ROOT / "data" / "set_effects.csv"
CANONICAL_ORDER = (
    "나무", "화염", "냉기", "번개", "수속성", "천상", "심연", "드래곤", "혼돈", "혼돈 II",
    "각성", "고대 유물", "초월", "시간", "생명", "창조신", "태양신", "사냥꾼", "현자", "그림자",
    "마도사", "월광", "공허", "심해", "뇌신", "질풍신", "별빛", "비전", "파멸", "시련", "전쟁신",
    "광전사", "다양성", "도박", "성장", "희생",
)
CANONICAL = frozenset(CANONICAL_ORDER)
NEW_SET_EFFECTS = (
    ("광전사", "방어를 공격으로 바꾸는 위험 보상", 2, "방어 전환 준비: 공격력 +2%, 흡혈 +2%", '{"attack_pct":2.0,"lifesteal":2.0}'),
    ("광전사", "방어를 공격으로 바꾸는 위험 보상", 4, "낮은 HP에서 물리 피해를 증폭", '{"phys_dmg_pct":6.0,"dmg_taken_pct":-4.0}'),
    ("다양성", "서로 다른 스킬 태그를 잇는 혼합 엔진", 2, "서로 다른 계열 사용을 위한 속도 +4%", '{"speed_pct":4.0}'),
    ("다양성", "서로 다른 스킬 태그를 잇는 혼합 엔진", 3, "혼합 피해와 생존을 함께 증폭", '{"phys_dmg_pct":3.0,"mag_dmg_pct":3.0,"hp_pct":4.0}'),
    ("도박", "리롤과 재장전 변동성을 보상", 2, "선제 확률과 속도 증가", '{"first_strike":2.0,"speed_pct":2.0}'),
    ("도박", "리롤과 재장전 변동성을 보상", 3, "변동성 성공 시 추가 행동 확률", '{"extra_action":6.0,"crit_rate":4.0}'),
    ("성장", "긴 전투의 턴 누적 성장을 강화", 2, "재생으로 성장 구간 유지", '{"regen_pct":2.0,"hp_pct":2.0}'),
    ("성장", "긴 전투의 턴 누적 성장을 강화", 3, "장기전 공격·방어 기반 강화", '{"attack_pct":4.0,"ad_defense_pct":3.0,"ap_defense_pct":3.0}'),
    ("희생", "HP 비용을 피해와 흡혈로 회수", 2, "흡혈과 공격력으로 희생 준비", '{"lifesteal":2.0,"attack_pct":2.0}'),
    ("희생", "HP 비용을 피해와 흡혈로 회수", 3, "피해 증가와 받는 피해 증가를 교환", '{"phys_dmg_pct":8.0,"dmg_taken_pct":2.0}'),
)

SET_PURPOSE = {
    "나무": "기본기를 고르게 보강하는 무속성 입문 세트",
    "화염": "화상 생성과 화염 피해의 안정적인 누적",
    "냉기": "마법 방어와 둔화로 버틴 뒤 냉기 피해를 확보",
    "번개": "속도와 감전 확률을 묶는 안정형 연쇄 세트",
    "수속성": "높은 체력과 회복 효율로 침수 계열 장기전을 지원",
    "천상": "신성 주문과 저항·회복을 함께 확보하는 보호 세트",
    "심연": "공격과 흡혈을 쌓아 암흑 피해로 회수",
    "드래곤": "체력·양 공격·방어를 섞고 드래곤 대상 규칙을 변경",
    "혼돈": "치명타와 치명 피해의 변동성을 받아들이는 덱 운용 세트",
    "혼돈 II": "물리·마법 혼합 공격과 관통에 집중하는 공격형 변주",
    "각성": "양 공격을 함께 올려 궁극 전환의 기반을 만드는 세트",
    "고대 유물": "체력과 물리 방어를 중심으로 피해 감소까지 연결",
    "초월": "여러 기본 능력치를 고르게 올린 뒤 혼합 피해로 전환",
    "시간": "속도·회피·첫 행동·추가 행동으로 전투 템포를 선점",
    "생명": "체력·회복·재생으로 장기전의 누적 이득을 확보",
    "창조신": "복합 능력과 양 계열 피해·드롭을 함께 연구하는 최상위 혼합 세트",
    "태양신": "체력을 기반으로 신성 주문과 피해를 키우는 화염·신성 혼합 세트",
    "사냥꾼": "공격·속도·명중·치명타를 이어 빠른 물리 처형을 지원",
    "현자": "마법 공격·방어와 회복을 함께 다루는 안정형 주문 세트",
    "그림자": "속도·회피 뒤 치명 반격을 노리는 방어적 선제 세트",
    "마도사": "마법 공격과 관통을 집중해 주문 피해를 완성",
    "월광": "마법 공격·회피·주문 피해를 섞는 잔향형 세트",
    "공허": "양 공격과 관통을 묶고 피해 감소로 위험을 상쇄",
    "심해": "체력·마법 방어로 버티며 수속성 피해를 축적",
    "뇌신": "공격과 번개 피해를 빠르게 집중하는 단일 대상 과부하 세트",
    "질풍신": "속도·회피·선제 강화를 극대화하는 연타 세트",
    "별빛": "신성 주문과 방어·회복을 묶는 보호 후 심판 세트",
    "비전": "마법 공격·관통·주문 피해로 덱의 주문 반복을 보상",
    "파멸": "물리 공격·치명 피해·관통을 이어 저주 계열 피니시를 지원",
    "시련": "공격과 방어를 함께 올려 위험 구간 돌파를 보상",
    "전쟁신": "물리 공격과 방어를 동시에 확보하는 반격형 세트",
    "광전사": "생존 안정성을 대가로 물리 피해와 흡혈 고점을 얻는 세트",
    "다양성": "서로 다른 계열을 섞을수록 양 피해와 생존을 보상",
    "도박": "선제·추가 행동의 변동성을 치명타로 회수하는 세트",
    "성장": "체력·재생에서 시작해 장기전 누적 능력으로 확장",
    "희생": "받는 피해 증가를 감수하고 공격과 흡혈을 강화",
}

KEY_LABELS = {
    "hp_pct": "HP", "attack_pct": "AD", "ap_attack_pct": "AP",
    "ad_defense_pct": "물리 방어", "ap_defense_pct": "마법 방어",
    "speed_pct": "속도", "phys_dmg_pct": "물리 피해", "mag_dmg_pct": "마법 피해",
    "fire_dmg_pct": "화염 피해", "ice_damage_pct": "냉기 피해",
    "lightning_dmg_pct": "번개 피해", "water_dmg_pct": "수속성 피해",
    "holy_dmg_pct": "신성 피해", "dark_dmg_pct": "암흑 피해",
    "heal_pct": "회복 효과", "regen_pct": "재생", "lifesteal": "흡혈",
    "crit_rate": "치명타 확률", "crit_damage": "치명타 피해",
    "armor_pen": "물리 관통", "magic_pen": "마법 관통", "accuracy": "명중",
    "evasion": "회피", "all_resistance": "모든 속성 저항",
    "dmg_taken_pct": "받는 피해", "first_strike": "첫 사용 강화",
    "extra_action": "추가 행동 확률", "burn_chance": "화상 생성 확률",
    "slow_chance": "둔화 생성 확률", "shock_chance": "감전 생성 확률",
    "dragon_bonus": "드래곤 대상 피해", "drop_rate": "드롭률",
}

SLOT_PURPOSE = {
    "검": "물리 공격의 기준 베이스", "낫": "위험 보상형 물리 공격 베이스",
    "지팡이": "마법 공격의 기준 베이스", "활": "속도·명중 기반 공격 베이스",
    "보조무기": "주 공격과 연계를 보완하는 보조 베이스", "갑옷": "HP와 양 방어의 중심 베이스",
    "로브": "마법 방어와 주문 유지의 중심 베이스", "투구": "생존 상한과 상태 저항을 보완하는 베이스",
    "장갑": "공격·소비기 효율을 조정하는 베이스", "신발": "속도·회피 템포를 조정하는 베이스",
    "목걸이": "연계와 유지 효과를 연결하는 액세서리", "반지": "조건부 피해와 덱 운용을 연결하는 액세서리",
}


def item_contract(row: dict) -> dict:
    existing = json.loads(row.get("config") or "{}")
    slot = row.get("슬롯", "")
    existing["itemization_v4"] = {
        "item_id": int(row["ID"]),
        "fantasy": row.get("description") or f"{row.get('이름', '장비')}의 고정 베이스",
        "purpose": SLOT_PURPOSE.get(slot, "자유 조합에서 특정 능력 예산을 담당하는 베이스"),
        "affix_profile": slot,
        "series": row.get("계열", ""),
        "set_key": row.get("set_key", ""),
        "acquisition_source": row.get("획득처", ""),
        "tradeoff": "다른 부위·계열의 기본 예산과 랜덤 옵션 기회를 포기한다.",
        "manual_revision": "V4-authored-contract",
    }
    return existing


def describe_config(raw: str) -> str:
    config = json.loads(raw or "{}")
    parts = []
    for key, value in config.items():
        label = KEY_LABELS.get(key, key)
        sign = "+" if float(value) >= 0 else ""
        parts.append(f"{label} {sign}{float(value):g}%")
    return ", ".join(parts) or "효과 없음"


def normalized(value: str) -> str:
    value = re.sub(r"[^\w\sⅡ]", "", value or "", flags=re.UNICODE)
    return re.sub(r"\s+", " ", value).strip()


def generate() -> None:
    with EQUIPMENT.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
        fields = list(rows[0])
    if "set_key" not in fields:
        fields.insert(fields.index("세트") + 1, "set_key")
    for row in rows:
        candidate = normalized(row.get("세트", ""))
        row["set_key"] = candidate if candidate in CANONICAL else ""
        row["config"] = json.dumps(item_contract(row), ensure_ascii=False, separators=(",", ":"))
    with EQUIPMENT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader(); writer.writerows(rows)

    with SETS.open(encoding="utf-8", newline="") as handle:
        set_rows = list(csv.DictReader(handle))
        set_fields = list(set_rows[0])
    existing = {(row["세트이름"], int(row["필요수"])) for row in set_rows}
    for name, description, pieces, effect_description, config in NEW_SET_EFFECTS:
        if (name, pieces) not in existing:
            set_rows.append({"세트이름": name, "설명": description, "필요수": pieces, "효과설명": effect_description, "효과config": config})
    by_set: dict[str, list[dict]] = {}
    for row in set_rows:
        by_set.setdefault(row["세트이름"], []).append(row)
    for name, group in by_set.items():
        group.sort(key=lambda row: int(row["필요수"]))
        for index, row in enumerate(group):
            stage = "진입" if index == 0 else ("완성" if index == len(group) - 1 else "엔진")
            row["설명"] = SET_PURPOSE.get(name, row["설명"])
            row["효과설명"] = f"{stage} · {describe_config(row['효과config'])}"
    order = {name: index for index, name in enumerate(CANONICAL_ORDER)}
    set_rows.sort(key=lambda row: (order.get(row["세트이름"], 999), int(row["필요수"])))
    with SETS.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=set_fields, lineterminator="\n")
        writer.writeheader(); writer.writerows(set_rows)


if __name__ == "__main__":
    generate()
    print("V4 equipment set keys and set contracts generated")
