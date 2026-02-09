"""
누락된 장비 config 추가

특수 효과 설명은 있지만 config가 비어있는 장비들에 적용합니다.
"""
import csv
import json
from typing import Dict, Any


# 누락된 config 설정
MISSING_CONFIGS = {
    # ========================================================================
    # 스킬 데미지 부스트 - 모든 스킬
    # ========================================================================
    1212: {  # 창세의 지팡이: 모든 스킬 +25%
        "components": [{
            "tag": "skill_damage_boost",
            "damage_bonus": 0.25
        }]
    },
    1220: {  # 초월의 지팡이: 모든 스킬 +45%
        "components": [{
            "tag": "skill_damage_boost",
            "damage_bonus": 0.45
        }]
    },
    1222: {  # 창조의 지팡이: 모든 스킬 +60%
        "components": [{
            "tag": "skill_damage_boost",
            "damage_bonus": 0.6
        }]
    },
    1024: {  # 창세의 검: 모든 스킬 +40%
        "components": [{
            "tag": "skill_damage_boost",
            "damage_bonus": 0.4
        }]
    },
    2226: {  # 별빛의 장갑: 모든 스킬 +18%
        "components": [{
            "tag": "skill_damage_boost",
            "damage_bonus": 0.18
        }]
    },
    3017: {  # 창조신의 목걸이: 모든 스킬 +30%
        "components": [{
            "tag": "skill_damage_boost",
            "damage_bonus": 0.3
        }]
    },
    3118: {  # 창조신의 반지: 모든 스킬 +20%
        "components": [{
            "tag": "skill_damage_boost",
            "damage_bonus": 0.2
        }]
    },
    4108: {  # 창세의 오브: 모든 스킬 +20%
        "components": [{
            "tag": "skill_damage_boost",
            "damage_bonus": 0.2
        }]
    },
    4112: {  # 초월의 오브: 모든 스킬 +40%
        "components": [{
            "tag": "skill_damage_boost",
            "damage_bonus": 0.4
        }]
    },
    4114: {  # 창조신의 오브: 모든 스킬 +60%
        "components": [{
            "tag": "skill_damage_boost",
            "damage_bonus": 0.6
        }]
    },

    # ========================================================================
    # 스킬 타입 데미지 부스트 - 각성 스킬
    # ========================================================================
    1216: {  # 각성의 지팡이: 각성 스킬 +60%, 원소 피해 +25%
        "components": [
            {
                "tag": "skill_type_damage_boost",
                "skill_type": "awakening",
                "damage_bonus": 0.6
            },
            {
                "tag": "skill_damage_boost",
                "damage_bonus": 0.25
            }
        ]
    },
    2011: {  # 각성의 투구: 각성 스킬 +30%, 원소 저항 +20%
        "components": [{
            "tag": "skill_type_damage_boost",
            "skill_type": "awakening",
            "damage_bonus": 0.3
        }]
    },
    3013: {  # 각성의 목걸이: 각성 스킬 +40%, 원소 저항 +25%
        "components": [{
            "tag": "skill_type_damage_boost",
            "skill_type": "awakening",
            "damage_bonus": 0.4
        }]
    },
    4110: {  # 각성의 오브: 각성 스킬 +50%, 원소 +20%
        "components": [
            {
                "tag": "skill_type_damage_boost",
                "skill_type": "awakening",
                "damage_bonus": 0.5
            },
            {
                "tag": "skill_damage_boost",
                "damage_bonus": 0.2
            }
        ]
    },

    # ========================================================================
    # 속성 스킬 데미지
    # ========================================================================
    1210: {  # 용언의 지팡이: 모든 속성 +10%
        "components": [
            {"tag": "passive_buff", "fire_damage": 10, "ice_damage": 10, "lightning_damage": 10, "water_damage": 10, "holy_damage": 10, "dark_damage": 10}
        ]
    },
    1218: {  # 시련의 지팡이: 모든 원소 +35%
        "components": [
            {"tag": "passive_buff", "fire_damage": 35, "ice_damage": 35, "lightning_damage": 35, "water_damage": 35}
        ]
    },
    4107: {  # 용의 오브: 모든 속성 스킬 +12%
        "components": [
            {"tag": "passive_buff", "fire_damage": 12, "ice_damage": 12, "lightning_damage": 12, "water_damage": 12, "holy_damage": 12, "dark_damage": 12}
        ]
    },
    4113: {  # 태양신의 오브: 신성 +80%, 아군 힐 2배
        "components": [
            {"tag": "passive_buff", "holy_damage": 80}
        ]
    },

    # ========================================================================
    # 회복/힐 스킬
    # ========================================================================
    1207: {  # 심해의 지팡이: 회복 스킬 +20%
        "components": [{
            "tag": "skill_type_damage_boost",
            "skill_type": "heal",
            "damage_bonus": 0.2
        }]
    },
    4106: {  # 심해의 오브: 회복 스킬 +20%
        "components": [{
            "tag": "skill_type_damage_boost",
            "skill_type": "heal",
            "damage_bonus": 0.2
        }]
    },

    # ========================================================================
    # 랜덤 속성
    # ========================================================================
    1211: {  # 혼돈의 지팡이: 랜덤 속성 +30%
        "components": [{
            "tag": "random_attribute",
            "mode": "per_combat",
            "damage_bonus": 0.3,
            "attributes": ["화염", "냉기", "번개", "수속성", "신성", "암흑"]
        }]
    },
    1219: {  # 차원 지팡이: 랜덤 속성 +80%
        "components": [{
            "tag": "random_attribute",
            "mode": "per_combat",
            "damage_bonus": 0.8,
            "attributes": ["화염", "냉기", "번개", "수속성", "신성", "암흑"]
        }]
    },

    # ========================================================================
    # 버프 지속시간
    # ========================================================================
    1213: {  # 시간의 지팡이: 버프 지속시간 +50%, 디버프 저항 +30%
        "components": [{
            "tag": "buff_duration_extension",
            "duration_multiplier": 1.5
        }]
    },
    2010: {  # 시간의 투구: 버프 지속 +100%, 시간 저항
        "components": [{
            "tag": "buff_duration_extension",
            "duration_multiplier": 2.0
        }]
    },
    3012: {  # 시간의 목걸이: 버프 지속 +100%, 시간 정지 저항
        "components": [{
            "tag": "buff_duration_extension",
            "duration_multiplier": 2.0
        }]
    },
    3113: {  # 시간의 반지: 쿨타임 -30%, 버프 지속 +50%
        "components": [
            {
                "tag": "buff_duration_extension",
                "duration_multiplier": 1.5
            }
        ]
    },

    # ========================================================================
    # 재생 (전투 중 턴당 회복)
    # ========================================================================
    1215: {  # 심해의 지팡이: 회복 스킬 +50%, 매 턴 HP 5% 회복
        "components": [
            {
                "tag": "skill_type_damage_boost",
                "skill_type": "heal",
                "damage_bonus": 0.5
            },
            {
                "tag": "regeneration",
                "regen_per_turn": 0.05,
                "regen_flat": 0,
                "regen_per_minute": 0,
                "combat_only": True
            }
        ]
    },

    # ========================================================================
    # 전투 성장 (턴당 스탯 증가)
    # ========================================================================
    1023: {  # 전쟁신의 검: 전투 중 영구 공격력 +5%/턴, 치명타 100%
        "components": [{
            "tag": "combat_stat_growth",
            "stat": "attack",
            "growth_per_turn": 0.05,
            "max_stacks": 0,  # 무제한
            "trigger": "per_turn"
        }]
    },

    # ========================================================================
    # 복합 효과 (이미 일부 있는 장비)
    # ========================================================================
    1022: {  # 초월의 검: 모든 피해 +30%, 받는 피해 -15%
        "components": [{
            "tag": "skill_damage_boost",
            "damage_bonus": 0.3
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


def assign_missing_configs_to_csv(input_path: str, output_path: str, dry_run: bool = True):
    """
    장비 CSV에 누락된 config 추가

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

            if item_id in MISSING_CONFIGS:
                existing_config_str = row.get('config', '')
                existing_config = {}
                if existing_config_str:
                    try:
                        existing_config = json.loads(existing_config_str)
                    except json.JSONDecodeError:
                        pass

                new_config = MISSING_CONFIGS[item_id]
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
    print("누락된 장비 config 추가 결과")
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
        print("실제 변환: python scripts/assign_missing_equipment_configs.py --commit")
        print()

    assign_missing_configs_to_csv(input_path, output_path, dry_run=dry_run)


if __name__ == "__main__":
    main()
