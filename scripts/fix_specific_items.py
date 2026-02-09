"""
특정 아이템의 쉼표 개수 수정
"""


def fix_csv_commas():
    """CSV 파일의 쉼표 개수 수정"""
    input_file = "data/items_equipment.csv"
    output_file = "data/items_equipment.csv"

    with open(input_file, 'r', encoding='utf-8-sig') as f:
        lines = f.readlines()

    # 수정할 라인 (line_number - 1 = index)
    fixes = {
        336: None,  # Line 337: ID 5004 (+1 comma)
        340: None,  # Line 341: ID 5008 (-1 comma)
        350: None,  # Line 351: ID 5018 (-1 comma)
        352: None,  # Line 353: ID 5020 (-1 comma)
        357: None,  # Line 358: ID 5025 (-1 comma)
        358: None,  # Line 359: ID 5101 (+1 comma)
        359: None,  # Line 360: ID 5102 (-1 comma)
        362: None,  # Line 363: ID 5105 (-2 commas)
    }

    # 각 라인을 수동으로 수정
    fixed_lines = {
        336: '5004,전술가의 덱,장신구,벨트,55,,,,,,,,180,,,,"스킬 2개 중 강한 것 자동 선택",🎯 전술,전략의 대가,"{""components"": [{""tag"": ""double_draw"", ""proc_chance"": 1.0, ""auto_select_better"": true}]}"\n',
        340: '5008,광기의 검,검,대검,50,40,,,,,280,,,,,"HP 10% 소모, 데미지 +60%",🩸 희생,광기의 화신,"{""components"": [{""tag"": ""hp_cost_empower"", ""hp_cost_percent"": 10.0, ""damage_boost_percent"": 60.0, ""min_hp_threshold"": 5.0}]}"\n',
        350: '5018,카멜레온 망토,망토,망토,55,,,,,,,,180,80,,"다양성 보너스 +8%/종 (최대 5종)",🌈 다양성,변신의 도적,"{""components"": [{""tag"": ""skill_variety_bonus"", ""bonus_per_unique"": 8.0, ""max_unique_count"": 5, ""reset_on_repeat"": false}]}"\n',
        352: '5020,시계태엽 건틀릿,장갑,건틀릿,35,,,,20,,,80,,,,"3턴마다 데미지 200%",⏰ 시간,시계공,"{""components"": [{""tag"": ""turn_count_empower"", ""trigger_interval"": 3, ""damage_multiplier"": 2.0}]}"\n',
        357: '5025,진화하는 갑옷,갑옷,갑옷,75,,,,60,,,,,300,200,"매 턴 8%씩 성장 (최대 200%)",⏳ 성장,진화의 괴물,"{""components"": [{""tag"": ""accumulation"", ""growth_per_turn"": 8.0, ""max_growth"": 200.0}]}"\n',
        358: '5101,도박사의 유물,장신구,목걸이,65,,,,,,,,,280,,,,"스킬 2개 선택 + 30% 재장전",🎲 전설,도박의 신,"{""components"": [{""tag"": ""double_draw"", ""proc_chance"": 1.0}, {""tag"": ""skill_refresh"", ""refresh_chance"": 0.3}]}"\n',
        359: '5102,광전사의 유산,갑옷,갑옷,75,,,,70,,,,,350,220,"HP 소모 강화 + 누적 성장",🩸 전설,광전사의 영혼,"{""components"": [{""tag"": ""hp_cost_empower"", ""hp_cost_percent"": 8.0, ""damage_boost_percent"": 50.0}, {""tag"": ""accumulation"", ""growth_per_turn"": 3.0, ""max_growth"": 60.0}]}"\n',
        362: '5105,만능의 대가,망토,망토,85,,,,,,,,420,180,"다양성 보너스 + 스킬 2개 선택",🌈 전설,만능의 마스터,"{""components"": [{""tag"": ""skill_variety_bonus"", ""bonus_per_unique"": 15.0, ""max_unique_count"": 6, ""reset_on_repeat"": false}, {""tag"": ""double_draw"", ""proc_chance"": 1.0, ""auto_select_better"": true}]}"\n',
    }

    # 라인 교체
    for index, fixed_line in fixed_lines.items():
        old_line = lines[index].strip()
        new_line = fixed_line.strip()

        print(f"Line {index + 1}:")
        print(f"  이전: {old_line[:100]}...")
        print(f"  수정: {new_line[:100]}...")
        print()

        lines[index] = fixed_line

    # 파일 저장
    with open(output_file, 'w', encoding='utf-8-sig', newline='') as f:
        f.writelines(lines)

    print(f"✅ {len(fixed_lines)}개 라인 수정 완료: {output_file}")


if __name__ == "__main__":
    fix_csv_commas()
