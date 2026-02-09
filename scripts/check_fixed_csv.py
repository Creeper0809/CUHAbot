"""
수정된 CSV 파일 검증
"""
import sys

# 이전 스크립트 재사용
sys.path.insert(0, 'scripts')

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


input_file = "data/items_equipment_fixed.csv"

with open(input_file, 'r', encoding='utf-8-sig') as f:
    lines = f.readlines()

# 헤더 확인
header_line = lines[0].strip()
expected_commas = count_commas_in_line(header_line)

print(f"✅ 수정된 파일 검증: {input_file}")
print(f"   헤더 쉼표: {expected_commas}\n")

# 신규 아이템만 체크
problem_ids = [5004, 5008, 5018, 5020, 5025, 5101, 5102, 5105]
found_issues = []

for i, line in enumerate(lines[1:], start=2):
    line = line.strip()
    if not line:
        continue

    item_id_str = line.split(',')[0]
    if not item_id_str.isdigit():
        continue

    item_id = int(item_id_str)

    if item_id in problem_ids:
        comma_count = count_commas_in_line(line)
        status = "✅" if comma_count == expected_commas else "❌"
        diff = comma_count - expected_commas

        print(f"{status} Line {i}: ID {item_id} - 쉼표 {comma_count} (차이: {diff:+})")

        if comma_count != expected_commas:
            found_issues.append(item_id)

print()
if found_issues:
    print(f"⚠️  여전히 문제가 있는 아이템: {found_issues}")
else:
    print("✅ 모든 아이템이 수정되었습니다!")
    print("\n이제 다음 명령으로 원본 파일을 교체하세요:")
    print("   mv data/items_equipment_fixed.csv data/items_equipment.csv")
