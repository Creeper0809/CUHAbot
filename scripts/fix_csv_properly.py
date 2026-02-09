"""
CSV 파일의 쉼표 개수 문제를 올바르게 수정
"""
import csv


def fix_csv_structure():
    """CSV 파일을 읽어서 필드 수를 맞추고 다시 저장"""
    input_file = "data/items_equipment.csv"
    output_file = "data/items_equipment_fixed.csv"

    # CSV 파일 읽기 (quoting=csv.QUOTE_ALL로 모든 따옴표 처리)
    with open(input_file, 'r', encoding='utf-8-sig') as f:
        # 수동으로 라인 읽기
        lines = f.readlines()

    # 헤더 확인
    header_line = lines[0].strip()
    print(f"헤더: {header_line}\n")

    # 각 라인 체크 및 수정
    fixed_lines = [header_line + '\n']

    problem_ids = [5004, 5008, 5018, 5020, 5025, 5101, 5102, 5105]

    for i, line in enumerate(lines[1:], start=2):
        line = line.strip()
        if not line:
            fixed_lines.append('\n')
            continue

        # ID 추출
        item_id_str = line.split(',')[0]
        if not item_id_str.isdigit():
            fixed_lines.append(line + '\n')
            continue

        item_id = int(item_id_str)

        if item_id in problem_ids:
            print(f"Line {i}: ID {item_id}")
            print(f"  원본: {line[:120]}...")

            # 수동으로 필드 재구성
            fixed_line = reconstruct_line(item_id, line)

            if fixed_line:
                print(f"  수정: {fixed_line[:120]}...")
                fixed_lines.append(fixed_line + '\n')
            else:
                print(f"  ⚠️  수정 실패, 원본 유지")
                fixed_lines.append(line + '\n')
            print()
        else:
            fixed_lines.append(line + '\n')

    # 파일 저장
    with open(output_file, 'w', encoding='utf-8-sig') as f:
        f.writelines(fixed_lines)

    print(f"\n✅ 수정 완료: {output_file}")
    print(f"   원본과 비교하여 확인 후 덮어쓰세요.")


def reconstruct_line(item_id, line):
    """문제가 있는 라인을 수동으로 재구성"""

    # 각 아이템별 올바른 데이터
    corrections = {
        5004: "5004,전술가의 덱,장신구,벨트,55,,,,,,,,180,,,,"
              + '"스킬 2개 중 강한 것 자동 선택"'
              + ",🎯 전술,전략의 대가,"
              + '"{""components"": [{""tag"": ""double_draw"", ""proc_chance"": 1.0, ""auto_select_better"": true}]}"',

        5008: "5008,광기의 검,검,대검,50,40,,,,,280,,,,,"
              + '"HP 10% 소모, 데미지 +60%"'
              + ",🩸 희생,광기의 화신,"
              + '"{""components"": [{""tag"": ""hp_cost_empower"", ""hp_cost_percent"": 10.0, ""damage_boost_percent"": 60.0, ""min_hp_threshold"": 5.0}]}"',

        5018: "5018,카멜레온 망토,망토,망토,55,,,,,,,,180,80,,"
              + '"다양성 보너스 +8%/종 (최대 5종)"'
              + ",🌈 다양성,변신의 도적,"
              + '"{""components"": [{""tag"": ""skill_variety_bonus"", ""bonus_per_unique"": 8.0, ""max_unique_count"": 5, ""reset_on_repeat"": false}]}"',

        5020: "5020,시계태엽 건틀릿,장갑,건틀릿,35,,,,20,,,80,,,,"
              + '"3턴마다 데미지 200%"'
              + ",⏰ 시간,시계공,"
              + '"{""components"": [{""tag"": ""turn_count_empower"", ""trigger_interval"": 3, ""damage_multiplier"": 2.0}]}"',

        5025: "5025,진화하는 갑옷,갑옷,갑옷,75,,,,60,,,,,300,200,"
              + '"매 턴 8%씩 성장 (최대 200%)"'
              + ",⏳ 성장,진화의 괴물,"
              + '"{""components"": [{""tag"": ""accumulation"", ""growth_per_turn"": 8.0, ""max_growth"": 200.0}]}"',

        5101: "5101,도박사의 유물,장신구,목걸이,65,,,,,,,,,280,,,,"
              + '"스킬 2개 선택 + 30% 재장전"'
              + ",🎲 전설,도박의 신,"
              + '"{""components"": [{""tag"": ""double_draw"", ""proc_chance"": 1.0}, {""tag"": ""skill_refresh"", ""refresh_chance"": 0.3}]}"',

        5102: "5102,광전사의 유산,갑옷,갑옷,75,,,,70,,,,,350,220,"
              + '"HP 소모 강화 + 누적 성장"'
              + ",🩸 전설,광전사의 영혼,"
              + '"{""components"": [{""tag"": ""hp_cost_empower"", ""hp_cost_percent"": 8.0, ""damage_boost_percent"": 50.0}, {""tag"": ""accumulation"", ""growth_per_turn"": 3.0, ""max_growth"": 60.0}]}"',

        5105: "5105,만능의 대가,망토,망토,85,,,,,,,,420,180,"
              + '"다양성 보너스 + 스킬 2개 선택"'
              + ",🌈 전설,만능의 마스터,"
              + '"{""components"": [{""tag"": ""skill_variety_bonus"", ""bonus_per_unique"": 15.0, ""max_unique_count"": 6, ""reset_on_repeat"": false}, {""tag"": ""double_draw"", ""proc_chance"": 1.0, ""auto_select_better"": true}]}"',
    }

    return corrections.get(item_id)


if __name__ == "__main__":
    fix_csv_structure()
