"""
CSV 파일의 쉼표 개수 및 구조 문제 확인
"""
import csv


def count_commas_in_line(line):
    """라인의 실제 필드 구분자 쉼표 개수 세기 (따옴표 안의 쉼표는 제외)"""
    in_quotes = False
    comma_count = 0

    for char in line:
        if char == '"':
            in_quotes = not in_quotes
        elif char == ',' and not in_quotes:
            comma_count += 1

    return comma_count


def check_csv_structure():
    """CSV 파일의 구조 검증"""
    input_file = "data/items_equipment.csv"

    with open(input_file, 'r', encoding='utf-8-sig') as f:
        lines = f.readlines()

    # 헤더 확인
    header_line = lines[0].strip()
    header_comma_count = count_commas_in_line(header_line)
    expected_commas = header_comma_count

    print(f"✅ 헤더 라인 쉼표 개수: {header_comma_count} (필드 {header_comma_count + 1}개)")
    print(f"   헤더: {header_line[:100]}...")
    print()

    issues = []

    # 각 라인 검증
    for i, line in enumerate(lines[1:], start=2):
        line = line.strip()
        if not line:
            continue

        comma_count = count_commas_in_line(line)

        if comma_count != expected_commas:
            # 라인에서 ID 추출 (첫 번째 필드)
            item_id = line.split(',')[0] if ',' in line else line

            issues.append({
                'line': i,
                'id': item_id,
                'expected': expected_commas,
                'actual': comma_count,
                'diff': comma_count - expected_commas,
                'preview': line[:150]
            })

    print(f"📊 총 {len(lines) - 1}개 라인 검증")
    print()

    if issues:
        print(f"⚠️  {len(issues)}개의 쉼표 개수 불일치 발견:\n")
        print(f"{'Line':<6} {'ID':<6} {'예상':<6} {'실제':<6} {'차이':<6} 미리보기")
        print("-" * 100)

        for issue in issues:
            line_num = issue['line']
            item_id = issue['id']
            expected = issue['expected']
            actual = issue['actual']
            diff = issue['diff']
            preview = issue['preview']

            print(f"{line_num:<6} {item_id:<6} {expected:<6} {actual:<6} {diff:+<6} {preview}...")

        # 신규 아이템 (5001-5108) 중 문제가 있는 것만 필터
        print("\n" + "=" * 100)
        print("신규 아이템 (5001-5108) 중 문제:")
        print("=" * 100)

        new_item_issues = [
            issue for issue in issues
            if issue['id'].isdigit() and 5001 <= int(issue['id']) <= 5108
        ]

        if new_item_issues:
            for issue in new_item_issues:
                print(f"\nLine {issue['line']}: ID {issue['id']}")
                print(f"  예상 쉼표: {issue['expected']}, 실제 쉼표: {issue['actual']} (차이: {issue['diff']:+})")
                print(f"  내용: {issue['preview']}...")

                # 전체 라인 출력
                full_line = lines[issue['line'] - 1].strip()
                print(f"\n  전체 라인:")
                print(f"  {full_line}")
        else:
            print("✅ 신규 아이템은 모두 정상입니다!")
    else:
        print("✅ 모든 라인의 쉼표 개수가 일치합니다!")


if __name__ == "__main__":
    check_csv_structure()
