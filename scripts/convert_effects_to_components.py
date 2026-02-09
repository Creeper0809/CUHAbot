"""
아이템 effects를 components 형식으로 변환

effects 형식을 스킬과 동일한 components 형식으로 변환합니다.
"""
import csv
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

CSV_PATH = PROJECT_ROOT / "data" / "items_equipment.csv"


def effects_to_component_config(effects):
    """
    effects를 component config로 변환

    Input: [{"type": "crit_rate", "value": 5}, ...]
    Output: {"components": [{"tag": "passive_buff", "crit_rate": 5, ...}]}
    """
    if not effects:
        return None

    # 효과 집계
    aggregated = {}
    for effect in effects:
        effect_type = effect.get("type", "")
        value = effect.get("value", 0)
        if effect_type:
            aggregated[effect_type] = aggregated.get(effect_type, 0) + value

    if not aggregated:
        return None

    # PassiveBuffComponent config 생성
    component_config = {"tag": "passive_buff"}

    # 모든 속성을 component config에 추가
    component_config.update(aggregated)

    return {"components": [component_config]}


def main():
    """CSV 파일의 config를 components 형식으로 변환"""

    # CSV 읽기
    with open(CSV_PATH, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    converted_count = 0

    # 각 행 처리
    for row in rows:
        config_str = row.get("config", "").strip()

        if not config_str:
            continue

        try:
            config = json.loads(config_str)

            # effects가 있으면 components로 변환
            if "effects" in config:
                effects = config["effects"]
                new_config = effects_to_component_config(effects)

                if new_config:
                    row["config"] = json.dumps(new_config, ensure_ascii=False)
                    converted_count += 1
                    print(f"✓ {row['이름']}: {len(effects)}개 효과 → components")
        except json.JSONDecodeError:
            print(f"⚠ {row['이름']}: JSON 파싱 실패")
            continue

    # CSV 쓰기
    if converted_count > 0:
        fieldnames = reader.fieldnames
        with open(CSV_PATH, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        print(f"\n✅ {converted_count}개 아이템 변환 완료!")
        print(f"   파일: {CSV_PATH}")
    else:
        print("\n변환할 아이템이 없습니다.")


if __name__ == "__main__":
    print("=" * 60)
    print("아이템 effects → components 변환")
    print("=" * 60 + "\n")

    main()
