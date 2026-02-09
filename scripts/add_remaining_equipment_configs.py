"""
특수능력 설명은 있지만 config이 없는 장비에 config 추가

현재 구현된 컴포넌트로 처리 가능한 것들만 우선 추가합니다.
"""
import csv
import json
from typing import Dict, Any


# 누락된 config 설정 (현재 컴포넌트로 구현 가능한 것들만)
REMAINING_CONFIGS = {
    # ========================================================================
    # 조건부 데미지 보너스
    # ========================================================================
    1014: {  # 심판의 검: 최대 HP 비례 추가 데미지
        "components": [{
            "tag": "conditional_damage_boost",
            "condition": "target_high_hp",
            "damage_bonus": 0.3,
            "threshold_high": 0.8
        }]
    },
    1107: {  # 처형자의 도끼: HP 30% 이하 적 +100%
        "components": [{
            "tag": "conditional_damage_boost",
            "condition": "target_low_hp",
            "damage_bonus": 1.0,
            "threshold_low": 0.3
        }]
    },
    3117: {  # 태양신의 반지: 신성 +40%, 확정 치명타 (HP 30% 이상 적)
        "components": [
            {"tag": "passive_buff", "holy_damage": 40},
            {
                "tag": "conditional_damage_boost",
                "condition": "target_high_hp",
                "damage_bonus": 0.5,
                "threshold_high": 0.3,
                "force_critical": True
            }
        ]
    },

    # ========================================================================
    # 마나/자원 관리
    # ========================================================================
    1203: {  # 마법사 지팡이: 마나 소모 -5%
        "components": [{
            "tag": "mana_cost_reduction",
            "reduction_percent": 0.05
        }]
    },
    2017: {  # 현자의 두건: 마나 +5%
        "components": [{
            "tag": "passive_buff",
            "bonus_mp_pct": 5
        }]
    },

    # ========================================================================
    # 쿨다운 감소
    # ========================================================================
    1507: {  # 시간의 파편 단검: 25% 확률 추가 턴, 쿨타임 -20%
        "components": [{
            "tag": "cooldown_reduction",
            "cooldown_reduction": 0.2
        }]
    },
    2209: {  # 천상의 건틀릿: 스킬 쿨타임 -20%
        "components": [{
            "tag": "cooldown_reduction",
            "cooldown_reduction": 0.2
        }]
    },
    2219: {  # 마도사의 장갑: 스킬 쿨타임 -10%
        "components": [{
            "tag": "cooldown_reduction",
            "cooldown_reduction": 0.1
        }]
    },
    4116: {  # 마도사의 오브: 모든 마법 +12%, 쿨타임 -10%
        "components": [
            {"tag": "passive_buff", "fire_damage": 12, "ice_damage": 12, "lightning_damage": 12, "water_damage": 12, "holy_damage": 12, "dark_damage": 12},
            {"tag": "cooldown_reduction", "cooldown_reduction": 0.1}
        ]
    },
    4109: {  # 시간의 오브: 시간 스킬 해금, 버프 지속 +100%
        "components": [{
            "tag": "buff_duration_extension",
            "duration_multiplier": 2.0
        }]
    },

    # ========================================================================
    # 디버프 감소
    # ========================================================================
    2009: {  # 천상의 월계관: 디버프 지속 -50%
        "components": [{
            "tag": "debuff_reduction",
            "reduction_percent": 0.5
        }]
    },
    2326: {  # 별빛의 신발: 디버프 저항 +30%, CC 지속 -40%
        "components": [
            {"tag": "passive_buff", "debuff_resistance": 30},
            {"tag": "debuff_reduction", "reduction_percent": 0.4}
        ]
    },
    2501: {  # 고대 수호자의 투구: CC 지속 -40%, 정신계 면역
        "components": [
            {"tag": "debuff_reduction", "reduction_percent": 0.4},
            {"tag": "status_immunity", "immune_statuses": ["정신지배", "혼란", "공포"]}
        ]
    },

    # ========================================================================
    # 속성 면역
    # ========================================================================
    2014: {  # 태양신의 투구: 신성 면역, 받는 힐 2배
        "components": [
            {"tag": "passive_element_immunity", "immune_elements": ["신성"]},
            {"tag": "passive_buff", "healing_received": 100}
        ]
    },
    2015: {  # 창조신의 왕관: 모든 면역, 매 턴 HP 5% 회복
        "components": [
            {"tag": "passive_element_immunity", "immune_elements": ["화염", "냉기", "번개", "수속성", "신성", "암흑"]},
            {"tag": "regeneration", "regen_per_turn": 0.05, "regen_flat": 0, "regen_per_minute": 0, "combat_only": True}
        ]
    },
    2901: {  # 화염 저항 망토: 화염 면역, 다른 속성 취약 +30%
        "components": [
            {"tag": "passive_element_immunity", "immune_elements": ["화염"]},
            {"tag": "passive_element_resistance", "elements": ["냉기", "번개", "수속성", "신성", "암흑"], "resistance_percent": -0.3}
        ]
    },
    2902: {  # 냉기 저항 코트: 냉기 면역, 다른 속성 취약 +30%
        "components": [
            {"tag": "passive_element_immunity", "immune_elements": ["냉기"]},
            {"tag": "passive_element_resistance", "elements": ["화염", "번개", "수속성", "신성", "암흑"], "resistance_percent": -0.3}
        ]
    },
    2903: {  # 번개 저항 장갑: 번개 면역, 다른 속성 취약 +30%
        "components": [
            {"tag": "passive_element_immunity", "immune_elements": ["번개"]},
            {"tag": "passive_element_resistance", "elements": ["화염", "냉기", "수속성", "신성", "암흑"], "resistance_percent": -0.3}
        ]
    },

    # ========================================================================
    # 속성 저항
    # ========================================================================
    2021: {  # 공허의 투구: 공허 저항 +25%
        "components": [{
            "tag": "passive_element_resistance",
            "elements": ["공허"],
            "resistance_percent": 0.25
        }]
    },
    2904: {  # 완전 속성 갑옷: 모든 속성 저항 +60%, 물리 피해 +40%
        "components": [
            {"tag": "passive_element_resistance", "elements": ["화염", "냉기", "번개", "수속성", "신성", "암흑"], "resistance_percent": 0.6},
            {"tag": "passive_buff", "received_physical_damage": -40}
        ]
    },

    # ========================================================================
    # 상태이상 면역
    # ========================================================================
    2012: {  # 고대 유물 투구: 모든 상태이상 저항 +50%
        "components": [{
            "tag": "passive_buff",
            "status_resistance": 50
        }]
    },
    2013: {  # 초월의 투구: CC 면역, 디버프 반사 30%
        "components": [
            {"tag": "status_immunity", "immune_statuses": ["기절", "동결", "속박", "침묵", "마비"]},
            {"tag": "passive_buff", "debuff_reflection": 30}
        ]
    },
    2116: {  # 태양신의 갑옷: 치명타 면역, 피해 반사 25%
        "components": [
            {"tag": "status_immunity", "immune_statuses": ["치명타"]},
            {"tag": "damage_reflection", "reflection_percent": 0.25}
        ]
    },
    2321: {  # 공허의 부츠: 둔화 면역
        "components": [{
            "tag": "status_immunity",
            "immune_statuses": ["둔화"]
        }]
    },
    2310: {  # 시간의 부츠: 30% 확률 추가 턴, 둔화 면역
        "components": [{
            "tag": "status_immunity",
            "immune_statuses": ["둔화"]
        }]
    },
    2327: {  # 질풍신의 부츠: 추가 턴 25%, 둔화/속박 면역
        "components": [{
            "tag": "status_immunity",
            "immune_statuses": ["둔화", "속박"]
        }]
    },
    2503: {  # 고대 드워프 갑옷: 물리 피해 -20%, 넉백 면역
        "components": [
            {"tag": "passive_buff", "received_physical_damage": -20},
            {"tag": "status_immunity", "immune_statuses": ["넉백"]}
        ]
    },
    4010: {  # 초월의 방패: 치명타 면역, 피해 -30%
        "components": [
            {"tag": "status_immunity", "immune_statuses": ["치명타"]},
            {"tag": "passive_buff", "received_all_damage": -30}
        ]
    },

    # ========================================================================
    # 재생
    # ========================================================================
    2124: {  # 심해의 로브: 매 턴 HP 3% 회복
        "components": [{
            "tag": "regeneration",
            "regen_per_turn": 0.03,
            "regen_flat": 0,
            "regen_per_minute": 0,
            "combat_only": True
        }]
    },
    2502: {  # 별의 로브: 마법 피해 -25%, 별빛 아래 HP 5%/턴 회복
        "components": [
            {"tag": "passive_buff", "received_magic_damage": -25},
            {"tag": "regeneration", "regen_per_turn": 0.05, "regen_flat": 0, "regen_per_minute": 0, "combat_only": True}
        ]
    },

    # ========================================================================
    # 가시 피해 (피해 반사)
    # ========================================================================
    2114: {  # 고대 유물 갑옷: 물리 피해 -40%, 반사 15%
        "components": [
            {"tag": "passive_buff", "received_physical_damage": -40},
            {"tag": "damage_reflection", "reflection_percent": 0.15}
        ]
    },
    4006: {  # 심연의 방패: 피해 -15%, 반사 10%
        "components": [
            {"tag": "passive_buff", "received_all_damage": -15},
            {"tag": "damage_reflection", "reflection_percent": 0.1}
        ]
    },
    4009: {  # 고대 유물 방패: 피해 -25%, 반사 20%
        "components": [
            {"tag": "passive_buff", "received_all_damage": -25},
            {"tag": "damage_reflection", "reflection_percent": 0.2}
        ]
    },
    4011: {  # 태양신의 방패: 물리/마법 면역 교대, 반사 30%
        "components": [{
            "tag": "damage_reflection",
            "reflection_percent": 0.3
        }]
    },

    # ========================================================================
    # 추가 공격
    # ========================================================================
    2210: {  # 시간의 건틀릿: 공격속도 +30%, 연속 공격 +1회
        "components": [
            {"tag": "passive_buff", "speed": 30},
            {"tag": "extra_attack", "extra_attack_chance": 0.5, "max_chains": 1, "damage_multiplier": 0.8}
        ]
    },
    2223: {  # 뇌신의 건틀릿: 공격속도 +20%, 연쇄 공격 +1회
        "components": [
            {"tag": "passive_buff", "speed": 20},
            {"tag": "extra_attack", "extra_attack_chance": 0.4, "max_chains": 1, "damage_multiplier": 0.7}
        ]
    },

    # ========================================================================
    # 스탯 보너스 (passive_buff)
    # ========================================================================
    2119: {  # 현자의 로브: 마법 데미지 +5%
        "components": [{
            "tag": "passive_buff",
            "magic_damage": 5
        }]
    },
    2121: {  # 마도사의 로브: 마법 데미지 +10%
        "components": [{
            "tag": "passive_buff",
            "magic_damage": 10
        }]
    },
    2126: {  # 비전의 로브: 마법 데미지 +20%
        "components": [{
            "tag": "passive_buff",
            "magic_damage": 20
        }]
    },
    2127: {  # 파멸의 갑옷: 물리 데미지 +20%, 피해 -15%
        "components": [{
            "tag": "passive_buff",
            "physical_damage": 20,
            "received_all_damage": -15
        }]
    },
    2217: {  # 현자의 장갑: 마법 데미지 +5%
        "components": [{
            "tag": "passive_buff",
            "magic_damage": 5
        }]
    },
    2214: {  # 전쟁신의 건틀릿: 확정 치명타, 공격력 +40%
        "components": [{
            "tag": "passive_buff",
            "attack": 40,
            "critical_chance": 100
        }]
    },
    2309: {  # 천상의 부츠: 행동 후 회피 +25% (1턴)
        "components": [{
            "tag": "passive_buff",
            "evasion": 25
        }]
    },
    2315: {  # 창조신의 부츠: 완전 회피 30%, 텔레포트 스킬 해금
        "components": [{
            "tag": "passive_buff",
            "evasion": 30
        }]
    },
    2319: {  # 마도사의 신발: 마법 피해 -8%
        "components": [{
            "tag": "passive_buff",
            "received_magic_damage": -8
        }]
    },
    2324: {  # 비전의 신발: 마법 피해 -15%, 디버프 저항 +20%
        "components": [{
            "tag": "passive_buff",
            "received_magic_damage": -15,
            "debuff_resistance": 20
        }]
    },
    2506: {  # 잠든 거인의 건틀릿: 공격력 +30%, 기절 확률 +15%
        "components": [{
            "tag": "passive_buff",
            "attack": 30,
            "stun_chance": 15
        }]
    },
    2604: {  # 순찰대 경갑: 이동속도 +15%, 기습 피해 -20%
        "components": [{
            "tag": "passive_buff",
            "speed": 15,
            "ambush_damage_reduction": 20
        }]
    },
    3009: {  # 혼돈의 목걸이: 모든 데미지 +15%, 받는 피해 +10%
        "components": [{
            "tag": "passive_buff",
            "all_damage": 15,
            "received_all_damage": 10
        }]
    },
    3015: {  # 초월의 목걸이: 모든 피해 +30%, 받는 피해 -20%
        "components": [{
            "tag": "skill_damage_boost",
            "damage_bonus": 0.3
        }]
    },
    3109: {  # 용의 반지: 모든 데미지 +10%
        "components": [{
            "tag": "skill_damage_boost",
            "damage_bonus": 0.1
        }]
    },
    4115: {  # 현자의 오브: 모든 마법 +8%
        "components": [{
            "tag": "passive_buff",
            "fire_damage": 8, "ice_damage": 8, "lightning_damage": 8, "water_damage": 8, "holy_damage": 8, "dark_damage": 8
        }]
    },
    4119: {  # 별빛의 오브: 신성 +35%, 모든 힐 +30%
        "components": [{
            "tag": "passive_buff",
            "holy_damage": 35,
            "healing_power": 30
        }]
    },
    2111: {  # 천상의 갑옷: 회복 +20%, 저항 +25%
        "components": [{
            "tag": "passive_buff",
            "healing_received": 20,
            "all_resistance": 25
        }]
    },
    2115: {  # 초월의 갑옷: 모든 피해 -25%, 회복 +30%
        "components": [{
            "tag": "passive_buff",
            "received_all_damage": -25,
            "healing_received": 30
        }]
    },
    2022: {  # 심해의 관: 회복량 +15%
        "components": [{
            "tag": "passive_buff",
            "healing_power": 15
        }]
    },
    2020: {  # 월광의 투구: 야간 시야 확보
        "components": [{
            "tag": "exploration_speed",
            "exploration_speed": 0.1,
            "gathering_speed": 0.0,
            "encounter_rate": 0.0
        }]
    },
    2603: {  # 광부 안전모: 낙석 피해 면역, 어둠 시야 확보
        "components": [
            {"tag": "status_immunity", "immune_statuses": ["낙석"]},
            {"tag": "exploration_speed", "exploration_speed": 0.15, "gathering_speed": 0.0, "encounter_rate": 0.0}
        ]
    },
    2607: {  # 병사의 군화: 행군 속도 +25%, 피로도 감소
        "components": [{
            "tag": "exploration_speed",
            "exploration_speed": 0.25,
            "gathering_speed": 0.0,
            "encounter_rate": 0.0
        }]
    },

    # ========================================================================
    # 속성 화살 (attribute_damage_boost)
    # ========================================================================
    1304: {  # 화염의 활: 화염 화살 (화상 15%)
        "components": [{
            "tag": "passive_buff",
            "fire_damage": 25
        }]
    },
    1305: {  # 폭풍의 활: 번개 화살 (연쇄 15%)
        "components": [{
            "tag": "passive_buff",
            "lightning_damage": 25
        }]
    },
    1306: {  # 드래곤 본 활: 관통 사격 (방어 -20%)
        "components": [{
            "tag": "passive_buff",
            "armor_penetration": 20
        }]
    },

    # ========================================================================
    # 랜덤 회피
    # ========================================================================
    2701: {  # 점술사의 로브: 회피 10~30% 랜덤 (전투마다 변경)
        "components": [{
            "tag": "random_damage_variance",
            "variance_min": 0.1,
            "variance_max": 0.3,
            "mode": "per_combat"
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


def add_remaining_configs_to_csv(input_path: str, output_path: str, dry_run: bool = True):
    """
    장비 CSV에 남은 config 추가

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

            if item_id in REMAINING_CONFIGS:
                existing_config_str = row.get('config', '')
                existing_config = {}
                if existing_config_str:
                    try:
                        existing_config = json.loads(existing_config_str)
                    except json.JSONDecodeError:
                        pass

                new_config = REMAINING_CONFIGS[item_id]
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
    print("남은 장비 config 추가 결과")
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
        print("실제 변환: python scripts/add_remaining_equipment_configs.py --commit")
        print()

    add_remaining_configs_to_csv(input_path, output_path, dry_run=dry_run)


if __name__ == "__main__":
    main()
