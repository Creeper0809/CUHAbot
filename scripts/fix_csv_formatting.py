"""
CSV 포맷 검증 및 수정 스크립트

특수 효과 필드에 쉼표가 있는 경우 따옴표로 감싸야 함
"""
import csv
import json


def validate_and_fix_csv():
    """CSV 파일의 포맷을 검증하고 수정"""
    input_file = "data/items_equipment.csv"
    output_file = "data/items_equipment_fixed.csv"

    with open(input_file, 'r', encoding='utf-8-sig') as f_in:
        reader = csv.DictReader(f_in)
        headers = reader.fieldnames

        print(f"✅ CSV 헤더 ({len(headers)}개): {headers}")
        print()

        rows = []
        issues = []

        for i, row in enumerate(reader, start=2):  # start=2 because line 1 is header
            row_num = i

            # 필드 수 확인
            actual_fields = len([v for v in row.values() if v is not None])
            expected_fields = len(headers)

            # 특수 효과 필드 확인
            special_effect = row.get("특수 효과", "")
            if special_effect and ',' in special_effect:
                # 쉼표가 있으면 문제 가능성
                pass

            # config 필드 확인
            config_str = row.get("config", "")
            if config_str:
                try:
                    config = json.loads(config_str)
                    # JSON 유효성 확인
                except json.JSONDecodeError as e:
                    issues.append(f"Line {row_num}: ID {row.get('ID')} - JSON 파싱 실패: {e}")

            rows.append(row)

        print(f"📊 총 {len(rows)}개 아이템 검증 완료")

        if issues:
            print(f"\n⚠️  {len(issues)}개의 문제 발견:")
            for issue in issues[:10]:  # 처음 10개만 출력
                print(f"  - {issue}")
        else:
            print("✅ 모든 행이 정상입니다!")

        # 수정된 CSV 작성
        with open(output_file, 'w', encoding='utf-8-sig', newline='') as f_out:
            writer = csv.DictWriter(f_out, fieldnames=headers)
            writer.writeheader()
            writer.writerows(rows)

        print(f"\n✅ 수정된 파일 저장: {output_file}")

        # 새로운 아이템(5001-5108) 특별 검증
        print("\n" + "="*80)
        print("신규 아이템 (5001-5108) 검증")
        print("="*80)

        for row in rows:
            item_id = row.get("ID", "")
            if item_id and item_id.isdigit():
                item_id_int = int(item_id)
                if 5001 <= item_id_int <= 5108:
                    name = row.get("이름", "")
                    special = row.get("특수 효과", "")
                    config = row.get("config", "")

                    status = "✅"
                    if not config:
                        status = "❌ config 없음"
                    elif not special:
                        status = "⚠️  특수효과 없음"

                    print(f"{status} {item_id}: {name}")
                    if ',' in special and special:
                        print(f"     특수효과: {special[:50]}...")
                    if config and len(config) > 10:
                        # config 앞부분만 출력
                        config_preview = config[:80] + "..." if len(config) > 80 else config
                        print(f"     config: {config_preview}")


if __name__ == "__main__":
    validate_and_fix_csv()
