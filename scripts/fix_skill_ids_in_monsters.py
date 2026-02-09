"""
스킬 ID 변경사항을 monsters.csv에 반영하는 스크립트
8201→8220, 8202→8221, 8203→8222, 8204→8223, 8205→8224
"""
import csv
from pathlib import Path

project_root = Path(__file__).parent.parent
monsters_csv = project_root / "data" / "monsters.csv"

# ID 매핑
id_mapping = {
    "8201": "8220",
    "8202": "8221",
    "8203": "8222",
    "8204": "8223",
    "8205": "8224",
}

def replace_ids_in_array(array_str: str) -> str:
    """배열 문자열 내의 스킬 ID 교체"""
    if not array_str or array_str == "":
        return array_str

    result = array_str
    for old_id, new_id in id_mapping.items():
        result = result.replace(old_id, new_id)

    return result

def main():
    print("🔄 monsters.csv에서 스킬 ID 업데이트 중...")

    # CSV 읽기
    with open(monsters_csv, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    # skill_ids와 drop_skill_ids 컬럼 찾기
    skill_ids_col = None
    drop_skill_ids_col = None

    for field in fieldnames:
        if 'skill_ids' in field.lower() and 'drop' not in field.lower():
            skill_ids_col = field
        elif 'drop_skill_ids' in field.lower():
            drop_skill_ids_col = field

    print(f"skill_ids 컬럼: {skill_ids_col}")
    print(f"drop_skill_ids 컬럼: {drop_skill_ids_col}")

    # ID 교체
    updated_count = 0
    for row in rows:
        changed = False

        # skill_ids 컬럼 처리
        if skill_ids_col and row.get(skill_ids_col):
            original = row[skill_ids_col]
            updated = replace_ids_in_array(original)
            if original != updated:
                row[skill_ids_col] = updated
                changed = True
                print(f"  Monster {row.get('ID', row.get('id', '?'))}: skill_ids 업데이트")

        # drop_skill_ids 컬럼 처리
        if drop_skill_ids_col and row.get(drop_skill_ids_col):
            original = row[drop_skill_ids_col]
            updated = replace_ids_in_array(original)
            if original != updated:
                row[drop_skill_ids_col] = updated
                changed = True
                print(f"  Monster {row.get('ID', row.get('id', '?'))}: drop_skill_ids 업데이트")

        if changed:
            updated_count += 1

    # CSV 쓰기
    with open(monsters_csv, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n✅ {updated_count}개 몬스터 업데이트 완료!")
    print("변경된 ID 매핑:")
    for old_id, new_id in id_mapping.items():
        print(f"  {old_id} → {new_id}")

if __name__ == "__main__":
    main()
