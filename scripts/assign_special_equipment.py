"""
특수 장비 효과 컴포넌트 할당

랜덤 효과, HP 회복, 전투 성장 등 특수한 장비 효과를 할당합니다.
"""
import csv
import json
from typing import Dict

# 수동 매핑: 장비 ID -> config
SPECIAL_EQUIPMENT_CONFIGS = {
    # ====================================================================
    # 랜덤 속성 효과
    # ====================================================================
    1701: {  # 운명의 주사위 검: 랜덤 속성 +30%
        "components": [{
            "tag": "random_attribute",
            "mode": "per_combat",
            "damage_bonus": 0.30,
            "attributes": ["화염", "냉기", "번개", "수속성", "신성", "암흑"]
        }]
    },
    1703: {  # 변덕스러운 마법봉: 매 공격 랜덤 속성
        "components": [{
            "tag": "random_attribute",
            "mode": "per_attack",
            "damage_bonus": 0.25,
            "attributes": ["화염", "냉기", "번개", "수속성", "신성", "암흑"]
        }]
    },

    # ====================================================================
    # 랜덤 데미지 변동
    # ====================================================================
    1011: {  # 혼돈의 검: 데미지 ±20% 변동
        "components": [{
            "tag": "random_damage_variance",
            "min_multiplier": 0.8,
            "max_multiplier": 1.2
        }]
    },
    1111: {  # 혼돈의 대부: 데미지 ±40% 변동
        "components": [{
            "tag": "random_damage_variance",
            "min_multiplier": 0.6,
            "max_multiplier": 1.4
        }]
    },
    1702: {  # 도박사의 단검: 데미지 -20%~+40% 랜덤
        "components": [{
            "tag": "random_damage_variance",
            "min_multiplier": 0.8,
            "max_multiplier": 1.4
        }]
    },
    2702: {  # 도박꾼의 조끼: 피격 시 50% 확률로 피해 2배 또는 0
        "components": [{
            "tag": "random_damage_variance",
            "min_multiplier": 0.0,
            "max_multiplier": 2.0
        }]
    },

    # ====================================================================
    # 처치 시 HP 회복
    # ====================================================================
    1506: {  # 저주받은 왕의 검: 처치 시 HP 30% 회복
        "components": [{
            "tag": "on_kill_heal",
            "heal_percent": 0.30,
            "heal_flat": 0
        }]
    },
    1952: {  # 영혼 수집 낫: 처치 시 HP 20% 회복
        "components": [{
            "tag": "on_kill_heal",
            "heal_percent": 0.20,
            "heal_flat": 0
        }]
    },

    # ====================================================================
    # 전투 중 스탯 성장
    # ====================================================================
    1951: {  # 살아있는 검: 매 턴 공격력 5% 증가 (최대 10스택)
        "components": [{
            "tag": "combat_stat_growth",
            "stat": "attack",
            "growth_per_turn": 0.05,
            "max_stacks": 10,
            "trigger": "per_turn"
        }]
    },
    1953: {  # 전투 학습 장갑: 매 턴 모든 스탯 3% 증가 (최대 15스택)
        "components": [
            {
                "tag": "combat_stat_growth",
                "stat": "attack",
                "growth_per_turn": 0.03,
                "max_stacks": 15,
                "trigger": "per_turn"
            },
            {
                "tag": "combat_stat_growth",
                "stat": "defense",
                "growth_per_turn": 0.03,
                "max_stacks": 15,
                "trigger": "per_turn"
            }
        ]
    },

    # ====================================================================
    # 조건부 스탯 보너스
    # ====================================================================
    1801: {  # 신앙의 검: HP 80% 이상 시 공격력 +50%
        "components": [{
            "tag": "conditional_stat_bonus",
            "condition": "high_hp",
            "stat": "attack",
            "bonus_amount": 0.50,
            "threshold_high": 0.8
        }]
    },
    1802: {  # 어둠을 삼킨 검: HP 30% 이하 시 공격력 +100%
        "components": [{
            "tag": "conditional_stat_bonus",
            "condition": "low_hp",
            "stat": "attack",
            "bonus_amount": 1.0,
            "threshold_low": 0.3
        }]
    },
    1803: {  # 균형의 지팡이: HP 50% 근처(40~60%)일 때 마법 공격력 +80%
        "components": [{
            "tag": "conditional_stat_bonus",
            "condition": "balanced_hp",
            "stat": "ap_attack",
            "bonus_amount": 0.80
        }]
    },
    1806: {  # 수호자의 방패검: HP 80% 이상 시 방어력 +60%
        "components": [{
            "tag": "conditional_stat_bonus",
            "condition": "high_hp",
            "stat": "defense",
            "bonus_amount": 0.60,
            "threshold_high": 0.8
        }]
    },

    # ====================================================================
    # 희생 효과
    # ====================================================================
    2804: {  # 희생자의 로브: HP 10% 소모 후 3턴간 공격력 +40%, 방어력 +40%
        "components": [{
            "tag": "sacrifice_effect",
            "hp_cost_percent": 0.10,
            "buff_duration": 3,
            "stat_bonus": {
                "attack": 40,
                "defense": 40
            }
        }]
    },

    # ====================================================================
    # 복합 효과 (기존 config 병합)
    # ====================================================================
    # 1506: 저주받은 왕의 검 - 이미 passive_buff + attribute_damage_boost 있음
    # → on_kill_heal 추가 병합 필요
}


def assign_special_to_csv(input_path: str, output_path: str, dry_run: bool = True):
    """
    CSV 파일에 특수 장비 컴포넌트 할당

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
        "merged": 0,
        "skipped": 0,
    }

    assigned_items = []
    merged_items = []
    skipped_items = []

    with open(input_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames

        for row in reader:
            stats["total"] += 1
            item_id = int(row['ID'])
            name = row['이름']
            config = row.get('config', '').strip()

            # 이미 config 있으면 병합
            if config and item_id in SPECIAL_EQUIPMENT_CONFIGS:
                try:
                    existing = json.loads(config)
                    new_config = SPECIAL_EQUIPMENT_CONFIGS[item_id]

                    # components 병합
                    if "components" in existing:
                        existing["components"].extend(new_config["components"])
                        row['config'] = json.dumps(existing, ensure_ascii=False)
                        stats["merged"] += 1
                        merged_items.append((item_id, name, row['config']))
                    else:
                        # 기존 config가 components 형식이 아니면 스킵
                        stats["already_has_config"] += 1
                        skipped_items.append((item_id, name, "기존 config 형식 불일치"))
                except json.JSONDecodeError:
                    stats["already_has_config"] += 1
                    skipped_items.append((item_id, name, "JSON 파싱 실패"))
                rows.append(row)
                continue

            # config 없으면 새로 할당
            if not config and item_id in SPECIAL_EQUIPMENT_CONFIGS:
                new_config = json.dumps(SPECIAL_EQUIPMENT_CONFIGS[item_id], ensure_ascii=False)
                row['config'] = new_config
                stats["assigned"] += 1
                assigned_items.append((item_id, name, new_config))

            rows.append(row)

    # 결과 출력
    print("=" * 80)
    print("특수 장비 컴포넌트 할당 결과")
    print("=" * 80)
    print(f"총 장비: {stats['total']}개")
    print(f"  - 새로 할당: {stats['assigned']}개")
    print(f"  - 기존 config 병합: {stats['merged']}개")
    print(f"  - 기존 config 있음 (스킵): {stats['already_has_config']}개")
    print()

    if assigned_items:
        print("=" * 80)
        print(f"✅ 새로 할당 완료 ({len(assigned_items)}개)")
        print("=" * 80)
        for item_id, name, config in assigned_items:
            print(f"[{item_id}] {name}")
            print(f"  {config}")
            print()

    if merged_items:
        print("=" * 80)
        print(f"🔀 기존 config와 병합 ({len(merged_items)}개)")
        print("=" * 80)
        for item_id, name, config in merged_items:
            print(f"[{item_id}] {name}")
            print(f"  {config}")
            print()

    if skipped_items:
        print("=" * 80)
        print(f"⚠️  스킵됨 ({len(skipped_items)}개)")
        print("=" * 80)
        for item_id, name, reason in skipped_items:
            print(f"[{item_id}] {name}: {reason}")

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
        print("실제 변환: python scripts/assign_special_equipment.py --commit")
        print()

    assign_special_to_csv(input_path, output_path, dry_run=dry_run)


if __name__ == "__main__":
    main()
