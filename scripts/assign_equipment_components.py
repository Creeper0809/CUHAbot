"""
장비에 컴포넌트를 할당하는 스크립트

수동으로 검증된 매핑 데이터를 기반으로 장비 config를 업데이트합니다.
"""
import csv
import json
from typing import Dict

# 수동 매핑: 장비 ID -> config
EQUIPMENT_CONFIGS = {
    # Priority 2: 공격 시 프록 효과
    1004: {  # 화염검: 공격 시 화상 10%
        "components": [{
            "tag": "on_attack_proc",
            "proc_chance": 0.10,
            "status_effect": "burn",
            "status_duration": 3,
            "status_stacks": 1
        }]
    },
    1005: {  # 빙결검: 공격 시 둔화 15%
        "components": [{
            "tag": "on_attack_proc",
            "proc_chance": 0.15,
            "status_effect": "slow",
            "status_duration": 2
        }]
    },
    1006: {  # 뇌전검: 공격 시 연쇄 피해 20%
        "components": [{
            "tag": "on_attack_proc",
            "proc_chance": 0.20,
            "status_effect": "shock",
            "status_duration": 2,
            "extra_damage_ratio": 0.2
        }]
    },
    1015: {  # 시간의 검: 공격 시 30% 확률 추가 턴 획득
        "components": [{
            "tag": "on_attack_proc",
            "proc_chance": 0.30,
            # 추가 턴은 시스템 레벨 구현 필요 - 일단 스킵
        }]
    },
    1308: {  # 시간의 활: 공격 후 30% 확률 즉시 재공격
        "components": [{
            "tag": "on_attack_proc",
            "proc_chance": 0.30,
            # 재공격은 시스템 레벨 구현 필요 - 일단 스킵
        }]
    },

    # Priority 3: 종족 특효
    1010: {  # 드래곤 슬레이어: 드래곤 종족 +50%
        "components": [{
            "tag": "race_bonus",
            "race": "dragon",
            "damage_bonus": 0.50
        }]
    },
    1604: {  # 사냥꾼의 작살: 짐승 종족 +25%
        "components": [{
            "tag": "race_bonus",
            "race": "beast",
            "damage_bonus": 0.25
        }]
    },
    1605: {  # 실용주의 철퇴: 해골 종족 +40%
        "components": [{
            "tag": "race_bonus",
            "race": "undead",
            "damage_bonus": 0.40
        }]
    },
    1901: {  # 슬라임 베인: 슬라임 종족 +500%
        "components": [{
            "tag": "race_bonus",
            "race": "slime",
            "damage_bonus": 5.00
        }]
    },
    1902: {  # 고블린 사냥꾼의 칼: 고블린 종족 +400%
        "components": [{
            "tag": "race_bonus",
            "race": "goblin",
            "damage_bonus": 4.00
        }]
    },
    1905: {  # 성스러운 퇴마검: 언데드/악마 +250%
        "components": [
            {
                "tag": "race_bonus",
                "race": "undead",
                "damage_bonus": 2.50
            },
            {
                "tag": "race_bonus",
                "race": "demon",
                "damage_bonus": 2.50
            }
        ]
    },
    1906: {  # 드래곤 베인: 드래곤 +300%
        "components": [{
            "tag": "race_bonus",
            "race": "dragon",
            "damage_bonus": 3.00
        }]
    },
    1907: {  # 정령 사냥꾼의 활: 정령 +350%
        "components": [{
            "tag": "race_bonus",
            "race": "elemental",
            "damage_bonus": 3.50
        }]
    },
    1908: {  # 기계 파괴자: 기계/골렘 +400%
        "components": [{
            "tag": "race_bonus",
            "race": "golem",
            "damage_bonus": 4.00
        }]
    },
    1903: {  # 뱀파이어 킬러: 흡혈귀 +300%
        "components": [{
            "tag": "race_bonus",
            "race": "undead",
            "damage_bonus": 3.00
        }]
    },
    1904: {  # 마녀 사냥꾼의 검: 마법사형 +200%
        "components": [{
            "tag": "race_bonus",
            "race": "magic_user",
            "damage_bonus": 2.00
        }]
    },

    # 처치 시 스택
    1020: {  # 시련의 검: 처치 시 영구 공격력 +1% (최대 +20%)
        "components": [{
            "tag": "on_kill_stack",
            "stat": "attack",
            "amount_per_kill": 0.01,
            "max_stacks": 20
        }]
    },
}


def assign_components_to_csv(input_path: str, output_path: str, dry_run: bool = True):
    """
    CSV 파일에 컴포넌트 할당

    Args:
        input_path: 입력 CSV 경로
        output_path: 출력 CSV 경로
        dry_run: True면 미리보기만
    """
    rows = []
    stats = {
        "total": 0,
        "assigned": 0,
        "already_has_config": 0,
    }

    assigned_items = []

    with open(input_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames

        for row in reader:
            stats["total"] += 1
            item_id = int(row['ID'])
            name = row['이름']
            config = row.get('config', '').strip()

            # 이미 config 있으면 스킵
            if config:
                stats["already_has_config"] += 1
                rows.append(row)
                continue

            # 매핑 데이터에서 찾기
            if item_id in EQUIPMENT_CONFIGS:
                new_config = json.dumps(EQUIPMENT_CONFIGS[item_id], ensure_ascii=False)
                row['config'] = new_config
                stats["assigned"] += 1
                assigned_items.append((item_id, name, new_config))

            rows.append(row)

    # 결과 출력
    print("=" * 80)
    print("장비 컴포넌트 할당 결과")
    print("=" * 80)
    print(f"총 장비: {stats['total']}개")
    print(f"  - 이미 config 있음: {stats['already_has_config']}개")
    print(f"  - 새로 할당: {stats['assigned']}개")
    print()

    if assigned_items:
        print("=" * 80)
        print(f"✅ 할당 완료 ({len(assigned_items)}개)")
        print("=" * 80)
        for item_id, name, config in assigned_items:
            print(f"[{item_id}] {name}")
            print(f"  {config}")
            print()

    # 파일 저장
    if not dry_run:
        with open(output_path, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        print(f"✅ 저장 완료: {output_path}")
    else:
        print("⚠️ Dry run 모드 - 실제 파일은 변경되지 않았습니다.")
        print(f"   실제 변환하려면 --commit 옵션을 사용하세요.")


def main():
    import sys

    input_path = "data/items_equipment.csv"
    output_path = "data/items_equipment.csv"  # 원본 덮어쓰기

    # --commit 전달 시 실제 변환
    dry_run = "--commit" not in sys.argv

    if dry_run:
        print("=" * 80)
        print("🔍 DRY RUN 모드")
        print("=" * 80)
        print("실제 변환: python scripts/assign_equipment_components.py --commit")
        print()

    assign_components_to_csv(input_path, output_path, dry_run=dry_run)


if __name__ == "__main__":
    main()
