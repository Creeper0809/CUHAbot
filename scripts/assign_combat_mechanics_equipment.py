"""
특수 전투 메커니즘 장비 컴포넌트 할당

선공권, 반격, 추가 공격, 재생, 부활 효과를 장비에 적용합니다.
"""
import csv
import json
from typing import Dict, Any


# 특수 전투 메커니즘 장비 컴포넌트 설정
COMBAT_MECHANICS_CONFIGS = {
    # ========================================================================
    # 선공권 (First Strike)
    # ========================================================================
    1311: {  # 초월의 활: 선공 확정, 연쇄 3회
        "components": [
            {
                "tag": "passive_buff",
                "evasion": 25
            },
            {
                "tag": "first_strike",
                "guaranteed": True,
                "speed_bonus": 0.0
            },
            {
                "tag": "extra_attack",
                "extra_attack_chance": 1.0,  # 확정
                "max_chains": 3,
                "damage_multiplier": 1.0
            }
        ]
    },
    1606: {  # 마을 수비대 창: 선공권 +20%, 방어 태세 시 반격
        "components": [
            {
                "tag": "first_strike",
                "guaranteed": False,
                "speed_bonus": 0.2
            },
            {
                "tag": "counter_attack",
                "counter_chance": 0.3,
                "counter_damage_multiplier": 0.6,
                "condition": "on_defend"
            }
        ]
    },
    2027: {  # 질풍신의 투구: 회피 +20%, 선공 확정
        "components": [
            {
                "tag": "passive_buff",
                "evasion": 20
            },
            {
                "tag": "first_strike",
                "guaranteed": True,
                "speed_bonus": 0.0
            }
        ]
    },
    2227: {  # 질풍신의 장갑: 확정 치명타 (선공 시), 연쇄 공격 +2
        "components": [
            {
                "tag": "extra_attack",
                "extra_attack_chance": 0.8,
                "max_chains": 2,
                "damage_multiplier": 0.9
            }
        ]
    },
    2307: {  # 그림자 부츠: 회피 +15%, 선공 +30%
        "components": [
            {
                "tag": "passive_buff",
                "evasion": 15
            },
            {
                "tag": "first_strike",
                "guaranteed": False,
                "speed_bonus": 0.3
            }
        ]
    },
    2311: {  # 각성의 부츠: 이동속도 +40%, 선공 확정
        "components": [
            {
                "tag": "first_strike",
                "guaranteed": True,
                "speed_bonus": 0.4
            }
        ]
    },
    2314: {  # 태양신의 부츠: 선공 확정, 첫 턴 무적
        "components": [
            {
                "tag": "first_strike",
                "guaranteed": True,
                "speed_bonus": 0.0,
                "first_turn_bonus": 1
            }
        ]
    },
    2318: {  # 그림자 경화: 회피 +10%, 선공 +20%
        "components": [
            {
                "tag": "passive_buff",
                "evasion": 10
            },
            {
                "tag": "first_strike",
                "guaranteed": False,
                "speed_bonus": 0.2
            }
        ]
    },
    2320: {  # 월광의 부츠: 회피 +12%, 선공 +25%
        "components": [
            {
                "tag": "passive_buff",
                "evasion": 12
            },
            {
                "tag": "first_strike",
                "guaranteed": False,
                "speed_bonus": 0.25
            }
        ]
    },
    2323: {  # 뇌신의 부츠: 번개 면역, 선공 확정
        "components": [
            {
                "tag": "first_strike",
                "guaranteed": True,
                "speed_bonus": 0.0
            }
        ]
    },
    3503: {  # 시간의 모래시계: 전투 시작 시 2턴 선공, 버프 지속 +50%
        "components": [
            {
                "tag": "first_strike",
                "guaranteed": True,
                "speed_bonus": 0.0,
                "first_turn_bonus": 2
            },
            {
                "tag": "buff_duration_extension",
                "duration_multiplier": 1.5
            }
        ]
    },

    # ========================================================================
    # 반격 (Counter Attack)
    # ========================================================================
    2325: {  # 파멸의 부츠: 피격 시 반격 15%
        "components": [
            {
                "tag": "counter_attack",
                "counter_chance": 0.15,
                "counter_damage_multiplier": 0.5,
                "condition": "always"
            }
        ]
    },

    # ========================================================================
    # 추가 공격 (Extra Attack)
    # ========================================================================
    1308: {  # 시간의 활: 공격 후 30% 확률 즉시 재공격
        "components": [
            {
                "tag": "extra_attack",
                "extra_attack_chance": 0.3,
                "max_chains": 1,
                "damage_multiplier": 1.0
            }
        ]
    },

    # ========================================================================
    # 재생 (Regeneration)
    # ========================================================================
    3018: {  # 축복받은 목걸이: HP 재생 +10/분
        "components": [
            {
                "tag": "regeneration",
                "regen_per_turn": 0.0,
                "regen_flat": 0,
                "regen_per_minute": 10,
                "combat_only": False
            }
        ]
    },
    3119: {  # 재생 반지: HP 재생 +2/분
        "components": [
            {
                "tag": "regeneration",
                "regen_per_turn": 0.0,
                "regen_flat": 0,
                "regen_per_minute": 2,
                "combat_only": False
            }
        ]
    },
    3120: {  # 생명의 반지: HP 재생 +5/분
        "components": [
            {
                "tag": "regeneration",
                "regen_per_turn": 0.0,
                "regen_flat": 0,
                "regen_per_minute": 5,
                "combat_only": False
            },
            {
                "tag": "passive_buff",
                "bonus_hp_pct": 5
            }
        ]
    },
    3121: {  # 생명의 심장: HP 재생 +20/분
        "components": [
            {
                "tag": "regeneration",
                "regen_per_turn": 0.0,
                "regen_flat": 0,
                "regen_per_minute": 20,
                "combat_only": False
            },
            {
                "tag": "passive_buff",
                "bonus_hp_pct": 10
            }
        ]
    },
    3122: {  # 불멸의 문장: HP 재생 +50/분, 전투 외 HP 회복 2배
        "components": [
            {
                "tag": "regeneration",
                "regen_per_turn": 0.0,
                "regen_flat": 0,
                "regen_per_minute": 100,  # 2배 적용 (50 * 2)
                "combat_only": False
            },
            {
                "tag": "passive_buff",
                "bonus_hp_pct": 20
            }
        ]
    },

    # ========================================================================
    # 부활 (Revive)
    # ========================================================================
    1221: {  # 태양신의 지팡이: 신성 스킬 +80%, 부활 1회 (HP 100%)
        "components": [
            {
                "tag": "passive_buff",
                "holy_damage": 80
            },
            {
                "tag": "revive",
                "revive_hp_percent": 1.0,
                "revive_count": 1,
                "invincible_turns": 0
            }
        ]
    },
    2117: {  # 창조신의 갑옷: 모든 피해 -40%, 부활 1회
        "components": [
            {
                "tag": "revive",
                "revive_hp_percent": 0.5,
                "revive_count": 1,
                "invincible_turns": 0
            }
        ]
    },
    3016: {  # 태양신의 목걸이: 신성 +60%, 부활 1회 (HP 50%)
        "components": [
            {
                "tag": "revive",
                "revive_hp_percent": 0.5,
                "revive_count": 1,
                "invincible_turns": 0
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


def assign_combat_mechanics_to_csv(input_path: str, output_path: str, dry_run: bool = True):
    """
    장비 CSV에 특수 전투 메커니즘 컴포넌트 할당

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

            if item_id in COMBAT_MECHANICS_CONFIGS:
                existing_config_str = row.get('config', '')
                existing_config = {}
                if existing_config_str:
                    try:
                        existing_config = json.loads(existing_config_str)
                    except json.JSONDecodeError:
                        pass

                new_config = COMBAT_MECHANICS_CONFIGS[item_id]
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
    print("특수 전투 메커니즘 장비 컴포넌트 할당 결과")
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
        print("실제 변환: python scripts/assign_combat_mechanics_equipment.py --commit")
        print()

    assign_combat_mechanics_to_csv(input_path, output_path, dry_run=dry_run)


if __name__ == "__main__":
    main()
