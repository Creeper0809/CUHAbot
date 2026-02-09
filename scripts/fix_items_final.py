"""
CSV 아이템 최종 수정 - 수동으로 정확한 필드 개수로 재작성
"""


def create_fixed_lines():
    """올바른 필드 구조로 라인 생성"""
    # 헤더: ID,이름,슬롯,계열,Lv,Req_STR,Req_INT,Req_DEX,Req_VIT,Req_LUK,Attack,AP_Attack,HP,AD_Def,AP_Def,Speed,특수 효과,세트,획득처,config
    # 총 20개 필드 = 19개 쉼표

    lines = {
        5004: ('5004,전술가의 덱,장신구,벨트,55,,,,,,,,180,,,,'
               '"스킬 2개 중 강한 것 자동 선택",🎯 전술,전략의 대가,'
               '"{""components"": [{""tag"": ""double_draw"", ""proc_chance"": 1.0, ""auto_select_better"": true}]}"'),

        5008: ('5008,광기의 검,검,대검,50,40,,,,,280,,,,,,'
               '"HP 10% 소모, 데미지 +60%",🩸 희생,광기의 화신,'
               '"{""components"": [{""tag"": ""hp_cost_empower"", ""hp_cost_percent"": 10.0, ""damage_boost_percent"": 60.0, ""min_hp_threshold"": 5.0}]}"'),

        5018: ('5018,카멜레온 망토,망토,망토,55,,,,,,,,180,80,,'
               '"다양성 보너스 +8%/종 (최대 5종)",🌈 다양성,변신의 도적,'
               '"{""components"": [{""tag"": ""skill_variety_bonus"", ""bonus_per_unique"": 8.0, ""max_unique_count"": 5, ""reset_on_repeat"": false}]}"'),

        5020: ('5020,시계태엽 건틀릿,장갑,건틀릿,35,,,,20,,,80,,,,'
               '"3턴마다 데미지 200%",⏰ 시간,시계공,'
               '"{""components"": [{""tag"": ""turn_count_empower"", ""trigger_interval"": 3, ""damage_multiplier"": 2.0}]}"'),

        5025: ('5025,진화하는 갑옷,갑옷,갑옷,75,,,,60,,,,,300,200,'
               '"매 턴 8%씩 성장 (최대 200%)",⏳ 성장,진화의 괴물,'
               '"{""components"": [{""tag"": ""accumulation"", ""growth_per_turn"": 8.0, ""max_growth"": 200.0}]}"'),

        5101: ('5101,도박사의 유물,장신구,목걸이,65,,,,,,,,,280,,,,'
               '"스킬 2개 선택 + 30% 재장전",🎲 전설,도박의 신,'
               '"{""components"": [{""tag"": ""double_draw"", ""proc_chance"": 1.0}, {""tag"": ""skill_refresh"", ""refresh_chance"": 0.3}]}"'),

        5102: ('5102,광전사의 유산,갑옷,갑옷,75,,,,70,,,,,350,220,'
               '"HP 소모 강화 + 누적 성장",🩸 전설,광전사의 영혼,'
               '"{""components"": [{""tag"": ""hp_cost_empower"", ""hp_cost_percent"": 8.0, ""damage_boost_percent"": 50.0}, {""tag"": ""accumulation"", ""growth_per_turn"": 3.0, ""max_growth"": 60.0}]}"'),

        5105: ('5105,만능의 대가,망토,망토,85,,,,,,,,420,180,'
               '"다양성 보너스 + 스킬 2개 선택",🌈 전설,만능의 마스터,'
               '"{""components"": [{""tag"": ""skill_variety_bonus"", ""bonus_per_unique"": 15.0, ""max_unique_count"": 6, ""reset_on_repeat"": false}, {""tag"": ""double_draw"", ""proc_chance"": 1.0, ""auto_select_better"": true}]}"'),
    }

    # 쉼표 개수 검증
    for item_id, line in lines.items():
        comma_count = sum(1 for c in line if c == ',') - line.count('""') * 2  # JSON 내부 쉼표 제외는 복잡함
        # 단순히 따옴표 밖의 쉼표만 세기
        in_quotes = False
        real_commas = 0
        for c in line:
            if c == '"':
                in_quotes = not in_quotes
            elif c == ',' and not in_quotes:
                real_commas += 1

        print(f"ID {item_id}: 쉼표 {real_commas}개 {'✅' if real_commas == 19 else '❌'}")

    return lines


def apply_fixes():
    """원본 CSV에 수정사항 적용"""
    input_file = "data/items_equipment.csv"
    output_file = "data/items_equipment.csv.backup"
    final_file = "data/items_equipment.csv"

    # 백업 생성
    with open(input_file, 'r', encoding='utf-8-sig') as f:
        lines = f.readlines()

    with open(output_file, 'w', encoding='utf-8-sig') as f:
        f.writelines(lines)

    print(f"✅ 백업 생성: {output_file}\n")

    # 수정할 라인 맵핑 (line_number -> line_index)
    line_fixes = {
        337 - 1: 5004,  # Line 337 = index 336
        341 - 1: 5008,
        351 - 1: 5018,
        353 - 1: 5020,
        358 - 1: 5025,
        359 - 1: 5101,
        360 - 1: 5102,
        363 - 1: 5105,
    }

    fixed_lines = create_fixed_lines()
    print()

    # 라인 교체
    for line_index, item_id in line_fixes.items():
        fixed_line = fixed_lines[item_id]
        old_line = lines[line_index].strip()

        print(f"Line {line_index + 1}: ID {item_id}")
        print(f"  이전: {old_line[:80]}...")
        print(f"  수정: {fixed_line[:80]}...")
        print()

        lines[line_index] = fixed_line + '\n'

    # 최종 파일 저장
    with open(final_file, 'w', encoding='utf-8-sig') as f:
        f.writelines(lines)

    print(f"✅ 수정 완료: {final_file}")
    print(f"   백업: {output_file}")


if __name__ == "__main__":
    apply_fixes()
