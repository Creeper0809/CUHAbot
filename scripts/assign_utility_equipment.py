"""
유틸리티 장비 컴포넌트 할당

탐험, 내구도, 강화, 드롭 관련 효과를 장비에 적용합니다.
"""
import csv
import json
from typing import Dict, Any


# 유틸리티 장비 컴포넌트 설정
UTILITY_EQUIPMENT_CONFIGS = {
    # ========================================================================
    # 내구도/수리 관련
    # ========================================================================
    1601: {  # 정제된 강철검: 내구도 2배, 수리비 -50%
        "components": [
            {
                "tag": "durability_bonus",
                "durability_multiplier": 2.0,
                "repair_cost_reduction": 0.5,
                "unlimited_repairs": False
            }
        ]
    },
    1607: {  # 대량생산 군용검: 수리 가능 횟수 무제한, 강화 +1 기본
        "components": [
            {
                "tag": "durability_bonus",
                "durability_multiplier": 1.0,
                "repair_cost_reduction": 0.0,
                "unlimited_repairs": True
            },
            {
                "tag": "enhancement_bonus",
                "enhancement_success_rate": 0.0,
                "base_enhancement": 1,
                "max_enhancement_bonus": 0
            }
        ]
    },
    2601: {  # 두꺼운 가죽 갑옷: 가시 피해 5, 내구도 3배
        "components": [
            {
                "tag": "thorns_damage",
                "thorns_damage": 5,
                "thorns_percent": 0.0
            },
            {
                "tag": "durability_bonus",
                "durability_multiplier": 3.0,
                "repair_cost_reduction": 0.0,
                "unlimited_repairs": False
            }
        ]
    },

    # ========================================================================
    # 강화 관련
    # ========================================================================
    1605: {  # 실용주의 철퇴: 해골 종족 +40%, 강화 성공률 +5%
        "components": [
            {
                "tag": "race_bonus",
                "race": "undead",
                "damage_bonus": 0.4
            },
            {
                "tag": "enhancement_bonus",
                "enhancement_success_rate": 0.05,
                "base_enhancement": 0,
                "max_enhancement_bonus": 0
            }
        ]
    },

    # ========================================================================
    # 탐험/던전 관련
    # ========================================================================
    1608: {  # 노련한 모험가의 검: 던전 탐색 속도 +20%, 함정 감지
        "components": [
            {
                "tag": "exploration_speed",
                "exploration_speed": 0.2,
                "gathering_speed": 0.0,
                "encounter_rate": 0.0
            },
            {
                "tag": "trap_detection",
                "detection_chance": 0.8,
                "trap_damage_reduction": 0.5,
                "auto_disarm": False
            }
        ]
    },
    2605: {  # 농부의 튼튼한 장갑: 채집 속도 +30%, 가시/독 면역
        "components": [
            {
                "tag": "exploration_speed",
                "exploration_speed": 0.0,
                "gathering_speed": 0.3,
                "encounter_rate": 0.0
            }
        ]
    },

    # ========================================================================
    # 특수 드롭 보너스
    # ========================================================================
    1603: {  # 광부의 곡괭이: 광물 드롭 +30%, 암석 몬스터 +20%
        "components": [
            {
                "tag": "special_drop_bonus",
                "item_type": "ore",
                "drop_bonus": 0.3,
                "quality_bonus": 0.1
            }
        ]
    },
    1604: {  # 사냥꾼의 작살: 짐승 종족 +25%, 가죽 드롭 +20%
        "components": [
            {
                "tag": "race_bonus",
                "race": "beast",
                "damage_bonus": 0.25
            },
            {
                "tag": "special_drop_bonus",
                "item_type": "leather",
                "drop_bonus": 0.2,
                "quality_bonus": 0.0
            }
        ]
    },

    # ========================================================================
    # 던전 특화 버프
    # ========================================================================
    2602: {  # 기사단 훈련복: 경험치 +10%, 훈련 던전 전용 버프
        "components": [
            {
                "tag": "passive_buff",
                "exp_bonus": 10
            },
            {
                "tag": "dungeon_specific_buff",
                "dungeon_ids": [],
                "dungeon_types": ["training"],
                "stat_bonuses": {
                    "attack": 20,
                    "defense": 15
                }
            }
        ]
    },
}


def merge_components(existing_config: Dict[str, Any], new_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    기존 config와 새 config를 병합

    Args:
        existing_config: 기존 설정 (JSON)
        new_config: 새 설정

    Returns:
        병합된 설정
    """
    if not existing_config:
        return new_config

    existing_components = existing_config.get("components", [])
    new_components = new_config.get("components", [])

    # 기존 태그 목록
    existing_tags = {comp["tag"] for comp in existing_components}

    # 새 컴포넌트 중 중복되지 않는 것만 추가
    merged_components = existing_components[:]
    for new_comp in new_components:
        if new_comp["tag"] not in existing_tags:
            merged_components.append(new_comp)
        else:
            # 동일 태그 존재 시 업데이트
            for i, comp in enumerate(merged_components):
                if comp["tag"] == new_comp["tag"]:
                    merged_components[i] = new_comp
                    break

    return {"components": merged_components}


def assign_utility_to_csv(input_path: str, output_path: str, dry_run: bool = True):
    """
    장비 CSV에 유틸리티 컴포넌트 할당

    Args:
        input_path: 입력 CSV 경로
        output_path: 출력 CSV 경로
        dry_run: True면 미리보기만
    """
    rows = []
    stats = {
        "total": 0,
        "updated": 0,
        "merged": 0,
        "skipped": 0,
    }
    updates = []

    with open(input_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames)

        for row in reader:
            stats["total"] += 1
            item_id = int(row['ID'])

            if item_id in UTILITY_EQUIPMENT_CONFIGS:
                existing_config_str = row.get('config', '')
                existing_config = {}
                if existing_config_str:
                    try:
                        existing_config = json.loads(existing_config_str)
                    except json.JSONDecodeError:
                        pass

                new_config = UTILITY_EQUIPMENT_CONFIGS[item_id]
                merged_config = merge_components(existing_config, new_config)

                row['config'] = json.dumps(merged_config, ensure_ascii=False)

                if existing_config:
                    stats["merged"] += 1
                    updates.append(f"[{item_id}] {row['이름']}: 기존 config에 병합")
                else:
                    stats["updated"] += 1
                    updates.append(f"[{item_id}] {row['이름']}: 새로 적용")
            else:
                stats["skipped"] += 1

            rows.append(row)

    # 결과 출력
    print("=" * 80)
    print("유틸리티 장비 컴포넌트 할당 결과")
    print("=" * 80)
    print(f"총 장비: {stats['total']}개")
    print(f"새로 적용: {stats['updated']}개")
    print(f"기존 병합: {stats['merged']}개")
    print(f"건너뜀: {stats['skipped']}개")
    print()

    if updates:
        print("업데이트 내역:")
        print("-" * 80)
        for update in updates:
            print(update)
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
        print("실제 변환: python scripts/assign_utility_equipment.py --commit")
        print()

    assign_utility_to_csv(input_path, output_path, dry_run=dry_run)


if __name__ == "__main__":
    main()
