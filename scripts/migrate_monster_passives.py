"""
monsters.csv 마이그레이션: 패시브/드롭 스킬 분리

1. skill_ids에서 80xx 스킬 → drop_skill_ids로 이동
2. 패시브 텍스트에 해당하는 95xx 스킬 ID를 skill_ids에 추가
3. drop_skill_ids 컬럼 추가
"""
import csv
import json
import re

# 패시브 텍스트 → 95xx 스킬 ID 매핑
PASSIVE_MAPPING = {
    3: [9501],      # 늑대 - 무리 본능 (공격력 +20%)
    4: [9510],      # 고블린 궁수 - 원거리 (회피율 +10%)
    5: [9531],      # 고블린 주술사 - 마력 보호막 (방어력 +25%)
    11: [9503],     # 마그마 골렘 - 용암 갑옷 (방+30%, 속-50%)
    12: [9502],     # 화염 임프 - 화염 민첩 (회피율 +15%)
    14: [],         # 얼음 정령 - 냉기 오라 (Phase 2: 적 속도 -10%)
    19: [9505],     # 폭풍 하피 - 폭풍의 가호 (회피율 +25%)
    22: [9522],     # 물 정령 - 회복의 물 (매 턴 HP 3%)
    26: [9539],     # 타락한 사제 - 타락한 축복 (공격력 +10%)
    27: [9508],     # 타락한 기사 - 신성 갑옷 (방어력 +25%)
    32: [9509],     # 유령 - 비실체화 (방어력 +50%)
    33: [],         # 망령 - 공포의 존재 (Phase 2: 적 공격력 -10%)
    34: [9540],     # 어린 드래곤 - 성장 (공격력 +10%)
    35: [9506],     # 드래곤 가드 - 용의 비늘 (방어력 +15%)
    42: [9504],     # 폭풍 그리폰 - 질풍 비행 (회피율 +20%)
    43: [9532],     # 심해 거북 - 단단한 등껍질 (방어력 +30%)
    44: [9534],     # 신성 수호상 - 신성한 석상 (방어력 +25%)
    46: [9507],     # 용의 현자 - 용의 지혜 (마법 공격력 +20%)
    58: [9536],     # 심해 리바이어던 - 심해의 압력 (방+40%, 속-20%)
    62: [9512],     # 각성한 용사 - 전사의 각성 (HP 50% 이하 시)
    70: [9538],     # 시련의 용사 - 영광의 전사 (공격력 +15%)
    78: [9537],     # 초월한 기사 - 한계 초월 (HP 25% 이하 시)
    82: [9524],     # 몰락한 반신 - 잔존하는 신격 (방+25%, HP 5%)
    86: [9515],     # 원초의 타이탄 - 원초의 힘 (HP 50% 이하 시 공+100%)
    90: [9533],     # 각성의 현자 - 원소 적응 (방어력 +20%)
    92: [9513],     # 시련의 검투사 - 투기장의 의지 (HP 30% 이하 시)
    94: [9537],     # 초월의 문지기 - 한계 초월 (HP 25% 이하 시)
    95: [9535],     # 전쟁의 심판관 - 신격의 잔재 (방어력 +15%)
    96: [9518],     # 원초의 사자 - 원초의 힘(약) (HP 50% 이하 시 공+30%)
    101: [9511],    # 고블린 족장 - 부족의 힘 (HP 30% 이하 시)
    108: [],        # 고대 드래곤 - 고대의 지혜 (Phase 2: 디버프 지속 -50%)
    110: [9516],    # 심연의 군주 - 심연의 각성 (HP 25% 이하 시)
    121: [9527],    # 창조신의 그림자 - 창조신의 잔재 (HP 3%)
    122: [9521],    # 숲의 정령왕 - 숲의 주인 (HP 2%)
    123: [9514],    # 몰락한 왕 - 타락한 왕관 (HP 50% 이하 시)
    124: [9523],    # 세계수의 수호자 - 세계수의 축복 (HP 5%)
    125: [9517],    # 마왕 발더스 - 마왕의 위엄 (HP 30% 이하 시)
    128: [9525],    # 용신 티아마트 - 용신의 권능 (HP 3%)
    129: [],        # 죽음의 지배자 - Phase 2 (부활)
    130: [9529],    # 태양신 라 - 태양신의 권능 (HP 5%)
    131: [9526],    # 원초의 신 - 원초의 존재 (HP 5%)
    132: [9528],    # 창조신 - 창조신의 권능 (HP 10%)
}


def parse_skill_ids(raw: str) -> list[int]:
    """skill_ids 문자열을 파싱"""
    raw = raw.strip()
    if not raw:
        return []
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # "[9061, 9061, ...]" 형태
        raw = raw.strip('[]')
        if not raw:
            return []
        return [int(x.strip()) for x in raw.split(',') if x.strip()]


def migrate():
    input_path = 'data/monsters.csv'
    output_path = 'data/monsters.csv'

    rows = []
    with open(input_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames)
        for row in reader:
            rows.append(row)

    # drop_skill_ids 컬럼 추가
    if 'drop_skill_ids' not in fieldnames:
        # 그룹 앞에 삽입
        idx = fieldnames.index('그룹') if '그룹' in fieldnames else len(fieldnames)
        fieldnames.insert(idx, 'drop_skill_ids')

    for row in rows:
        monster_id = int(row['ID'])
        skill_ids = parse_skill_ids(row.get('skill_ids', '[]'))

        # 80xx → drop_skill_ids로 이동
        drop_ids = [sid for sid in skill_ids if 8000 <= sid <= 8999]
        active_ids = [sid for sid in skill_ids if sid != 0 and not (8000 <= sid <= 8999)]

        # 95xx 패시브 추가
        passive_ids = PASSIVE_MAPPING.get(monster_id, [])

        # 새 skill_ids 구성: active + passive, 10슬롯 패딩
        new_skill_ids = active_ids + passive_ids
        new_skill_ids = (new_skill_ids + [0] * 10)[:10]

        # drop_skill_ids: 중복 제거
        unique_drops = list(dict.fromkeys(drop_ids))

        row['skill_ids'] = json.dumps(new_skill_ids)
        row['drop_skill_ids'] = json.dumps(unique_drops) if unique_drops else '[]'

    with open(output_path, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Migrated {len(rows)} monsters")
    print(f"Monsters with passives: {sum(1 for mid in PASSIVE_MAPPING if PASSIVE_MAPPING[mid])}")
    print(f"Monsters with drops: {sum(1 for row in rows if row['drop_skill_ids'] != '[]')}")


if __name__ == '__main__':
    migrate()
