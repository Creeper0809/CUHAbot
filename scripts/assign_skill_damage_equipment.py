"""
스킬 데미지 강화 장비에 컴포넌트 할당

수동으로 검증된 매핑 데이터를 기반으로 스킬 데미지 강화 효과를 가진
장비에 컴포넌트를 할당합니다.
"""
import csv
import json
from typing import Dict

# 수동 매핑: 장비 ID -> config
SKILL_DAMAGE_CONFIGS = {
    # 모든 스킬 데미지 증가
    1007: {  # 마법검: 모든 스킬 +25%
        "components": [{
            "tag": "skill_damage_boost",
            "damage_bonus": 0.25
        }]
    },
    1613: {  # 무한의 스태프: 모든 스킬 +40%
        "components": [{
            "tag": "skill_damage_boost",
            "damage_bonus": 0.40
        }]
    },
    1621: {  # 창조자의 지팡이: 모든 스킬 +45%
        "components": [{
            "tag": "skill_damage_boost",
            "damage_bonus": 0.45
        }]
    },

    # 각성 스킬 데미지 증가
    1008: {  # 각성의 검: 각성 스킬 +50%
        "components": [{
            "tag": "skill_type_damage_boost",
            "skill_type": "awakening",
            "damage_bonus": 0.50
        }]
    },
    1627: {  # 각성의 반지: 각성 스킬 +35%
        "components": [{
            "tag": "skill_type_damage_boost",
            "skill_type": "awakening",
            "damage_bonus": 0.35
        }]
    },

    # 회복 스킬 강화
    1624: {  # 생명의 반지: 회복 스킬 +40%
        "components": [{
            "tag": "skill_type_damage_boost",
            "skill_type": "healing",
            "damage_bonus": 0.40
        }]
    },

    # 물리 스킬 강화
    1309: {  # 전사의 활: 물리 공격 스킬 +30%
        "components": [{
            "tag": "skill_type_damage_boost",
            "skill_type": "physical",
            "damage_bonus": 0.30
        }]
    },

    # 마법 스킬 강화
    1310: {  # 마법사의 활: 마법 공격 스킬 +30%
        "components": [{
            "tag": "skill_type_damage_boost",
            "skill_type": "magical",
            "damage_bonus": 0.30
        }]
    },

    # 속성별 스킬 데미지 증가
    1501: {  # 화염 부적: 화염 스킬 +30%
        "components": [{
            "tag": "attribute_damage_boost",
            "attribute": "화염",
            "damage_bonus": 0.30
        }]
    },
    1502: {  # 냉기 부적: 냉기 스킬 +30%
        "components": [{
            "tag": "attribute_damage_boost",
            "attribute": "냉기",
            "damage_bonus": 0.30
        }]
    },
    1503: {  # 번개 부적: 번개 스킬 +30%
        "components": [{
            "tag": "attribute_damage_boost",
            "attribute": "번개",
            "damage_bonus": 0.30
        }]
    },
    1504: {  # 수속성 부적: 수속성 스킬 +30%
        "components": [{
            "tag": "attribute_damage_boost",
            "attribute": "수속성",
            "damage_bonus": 0.30
        }]
    },
    1505: {  # 신성 부적: 신성 스킬 +30%
        "components": [{
            "tag": "attribute_damage_boost",
            "attribute": "신성",
            "damage_bonus": 0.30
        }]
    },
    1506: {  # 암흑 부적: 암흑 스킬 +30%
        "components": [{
            "tag": "attribute_damage_boost",
            "attribute": "암흑",
            "damage_bonus": 0.30
        }]
    },

    # HP 조건부 데미지 증가
    1009: {  # 광전사의 검: HP 30% 이하 적에게 +100%
        "components": [{
            "tag": "conditional_damage_boost",
            "condition": "low_hp",
            "threshold": 0.30,
            "damage_bonus": 1.00
        }]
    },
    1011: {  # 처형자의 검: HP 20% 이하 적에게 +150%
        "components": [{
            "tag": "conditional_damage_boost",
            "condition": "low_hp",
            "threshold": 0.20,
            "damage_bonus": 1.50
        }]
    },

    # 복합 효과 (skill_damage + conditional)
    1012: {  # 영혼의 검: 모든 스킬 +20%, HP 40% 이하 적 +50%
        "components": [
            {
                "tag": "skill_damage_boost",
                "damage_bonus": 0.20
            },
            {
                "tag": "conditional_damage_boost",
                "condition": "low_hp",
                "threshold": 0.40,
                "damage_bonus": 0.50
            }
        ]
    },

    # 속성 + 스킬 데미지 복합
    1019: {  # 태양의 검: 신성 스킬 +40%, 모든 스킬 +15%
        "components": [
            {
                "tag": "attribute_damage_boost",
                "attribute": "신성",
                "damage_bonus": 0.40
            },
            {
                "tag": "skill_damage_boost",
                "damage_bonus": 0.15
            }
        ]
    },
    1021: {  # 달의 검: 암흑 스킬 +40%, 모든 스킬 +15%
        "components": [
            {
                "tag": "attribute_damage_boost",
                "attribute": "암흑",
                "damage_bonus": 0.40
            },
            {
                "tag": "skill_damage_boost",
                "damage_bonus": 0.15
            }
        ]
    },

    # 상태이상 조건부
    1016: {  # 독살자의 검: 중독 상태 적에게 +80%
        "components": [{
            "tag": "conditional_damage_boost",
            "condition": "status",
            "status_effect": "poison",
            "damage_bonus": 0.80
        }]
    },
    1017: {  # 냉동검: 동결 상태 적에게 +100%
        "components": [{
            "tag": "conditional_damage_boost",
            "condition": "status",
            "status_effect": "freeze",
            "damage_bonus": 1.00
        }]
    },
    1018: {  # 감전검: 감전 상태 적에게 +90%
        "components": [{
            "tag": "conditional_damage_boost",
            "condition": "status",
            "status_effect": "shock",
            "damage_bonus": 0.90
        }]
    },
}


def assign_skill_damage_to_csv(input_path: str, output_path: str, dry_run: bool = True):
    """
    CSV 파일에 스킬 데미지 강화 컴포넌트 할당

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
        "skipped": 0,
    }

    assigned_items = []
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
            if config and item_id in SKILL_DAMAGE_CONFIGS:
                try:
                    existing = json.loads(config)
                    new_config = SKILL_DAMAGE_CONFIGS[item_id]

                    # components 병합
                    if "components" in existing:
                        existing["components"].extend(new_config["components"])
                        row['config'] = json.dumps(existing, ensure_ascii=False)
                        stats["assigned"] += 1
                        assigned_items.append((item_id, name, row['config']))
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
            if not config and item_id in SKILL_DAMAGE_CONFIGS:
                new_config = json.dumps(SKILL_DAMAGE_CONFIGS[item_id], ensure_ascii=False)
                row['config'] = new_config
                stats["assigned"] += 1
                assigned_items.append((item_id, name, new_config))

            rows.append(row)

    # 결과 출력
    print("=" * 80)
    print("스킬 데미지 강화 컴포넌트 할당 결과")
    print("=" * 80)
    print(f"총 장비: {stats['total']}개")
    print(f"  - 새로 할당/병합: {stats['assigned']}개")
    print(f"  - 기존 config 있음: {stats['already_has_config']}개")
    print()

    if assigned_items:
        print("=" * 80)
        print(f"✅ 할당 완료 ({len(assigned_items)}개)")
        print("=" * 80)
        for item_id, name, config in assigned_items:
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
        print("실제 변환: python scripts/assign_skill_damage_equipment.py --commit")
        print()

    assign_skill_damage_to_csv(input_path, output_path, dry_run=dry_run)


if __name__ == "__main__":
    main()
