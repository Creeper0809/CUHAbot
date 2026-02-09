"""
마지막 특수 능력 장비 config 추가

고급 전투 메커니즘이 필요한 6개 아이템에 config을 추가합니다.
"""
import csv
import json
from typing import Dict, Any


# 마지막 6개 아이템 config
FINAL_SPECIAL_CONFIGS = {
    # ========================================================================
    # 회복 봉인
    # ========================================================================
    1214: {  # 공허의 지팡이: 공허 스킬 +40%, 대상 회복 봉인
        "components": [
            {
                "tag": "skill_type_damage_boost",
                "skill_type": "void",
                "damage_bonus": 0.4
            },
            {
                "tag": "heal_blocking",
                "block_percent": 1.0,
                "duration": 3,
                "on_hit_chance": 0.3
            }
        ]
    },

    # ========================================================================
    # 행동 예측
    # ========================================================================
    1704: {  # 미래를 보는 검: 30% 확률로 적 다음 행동 예측
        "components": [{
            "tag": "action_prediction",
            "prediction_chance": 0.3,
            "evasion_bonus": 0.2,
            "damage_reduction": 0.3
        }]
    },

    # ========================================================================
    # 피해 이연
    # ========================================================================
    2112: {  # 시간의 갑옷: 피해 이연 30% (다음 턴으로)
        "components": [{
            "tag": "damage_delay",
            "delay_percent": 0.3,
            "max_delayed_damage": 0,
            "attribute_resistance": ["시간"]
        }]
    },
    4007: {  # 시간의 방패: 피해 이연 40%, 시간 저항
        "components": [{
            "tag": "damage_delay",
            "delay_percent": 0.4,
            "max_delayed_damage": 0,
            "attribute_resistance": ["시간"]
        }]
    },

    # ========================================================================
    # 주기적 무적
    # ========================================================================
    4012: {  # 창조신의 방패: 모든 피해 -50%, 5턴마다 무적 1턴
        "components": [
            {
                "tag": "passive_buff",
                "received_all_damage": -50
            },
            {
                "tag": "periodic_invincibility",
                "interval": 5,
                "duration": 1,
                "damage_reduction": 1.0
            }
        ]
    },

    # ========================================================================
    # 아군 보호
    # ========================================================================
    2608: {  # 베테랑 수호자 갑옷: 아군 보호 시 피해 -20%, 도발 효과
        "components": [{
            "tag": "ally_protection",
            "damage_reduction": 0.2,
            "taunt_chance": 0.5,
            "taunt_duration": 2
        }]
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


def add_final_special_configs_to_csv(input_path: str, output_path: str, dry_run: bool = True):
    """
    장비 CSV에 마지막 특수 능력 config 추가

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

            if item_id in FINAL_SPECIAL_CONFIGS:
                existing_config_str = row.get('config', '')
                existing_config = {}
                if existing_config_str:
                    try:
                        existing_config = json.loads(existing_config_str)
                    except json.JSONDecodeError:
                        pass

                new_config = FINAL_SPECIAL_CONFIGS[item_id]
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
    print("마지막 특수 능력 장비 config 추가 결과")
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
        print("실제 변환: python scripts/add_final_special_equipment.py --commit")
        print()

    add_final_special_configs_to_csv(input_path, output_path, dry_run=dry_run)


if __name__ == "__main__":
    main()
