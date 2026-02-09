"""
장비 특수 효과를 컴포넌트로 변환하는 스크립트

Priority 1~3 장비를 자동으로 컴포넌트화합니다.
"""
import csv
import json
import re
from typing import Optional, Dict, List


def parse_stat_bonus(effect: str) -> Optional[Dict]:
    """
    스탯 보너스 효과를 파싱하여 passive_buff config 생성

    예시:
        "치명타 +15%" -> {"tag": "passive_buff", "crit_rate": 15}
        "흡혈 +5%" -> {"tag": "passive_buff", "lifesteal": 5}
    """
    config = {"tag": "passive_buff"}

    # 치명타
    m = re.search(r'치명타.*?\+(\d+)%', effect)
    if m:
        config["crit_rate"] = int(m.group(1))

    # 치명타 데미지
    m = re.search(r'치명타.*?데미지.*?\+(\d+)%', effect)
    if m:
        config["crit_damage"] = int(m.group(1))

    # 흡혈
    m = re.search(r'흡혈.*?(\d+)%', effect)
    if m:
        config["lifesteal"] = int(m.group(1))

    # 회피
    m = re.search(r'회피.*?\+(\d+)%', effect)
    if m:
        config["evasion"] = int(m.group(1))

    # 명중률
    m = re.search(r'명중률.*?([+-])(\d+)%', effect)
    if m:
        sign = 1 if m.group(1) == '+' else -1
        config["accuracy"] = sign * int(m.group(2))

    # 방어력 관통
    m = re.search(r'관통.*?\+(\d+)%', effect)
    if m:
        config["armor_pen"] = int(m.group(1))

    m = re.search(r'방어.*?관통.*?\+(\d+)%', effect)
    if m:
        config["armor_pen"] = int(m.group(1))

    # 마법 관통
    m = re.search(r'마법.*?관통.*?\+(\d+)%', effect)
    if m:
        config["magic_pen"] = int(m.group(1))

    # 블록
    m = re.search(r'블록.*?\+(\d+)%', effect)
    if m:
        config["block_rate"] = int(m.group(1))

    # 속성 저항
    for attr, key in [
        ('화염', 'fire_resist'), ('냉기', 'ice_resist'), ('번개', 'lightning_resist'),
        ('수속성', 'water_resist'), ('신성', 'holy_resist'), ('암흑', 'dark_resist')
    ]:
        m = re.search(rf'{attr}.*?저항.*?\+(\d+)%', effect)
        if m:
            config[key] = int(m.group(1))

    # 속성 데미지
    for attr, key in [
        ('화염', 'fire_damage'), ('냉기', 'ice_damage'), ('번개', 'lightning_damage'),
        ('수속성', 'water_damage'), ('신성', 'holy_damage'), ('암흑', 'dark_damage')
    ]:
        m = re.search(rf'{attr}.*?(\d+)%', effect)
        if m and '저항' not in effect:
            config[key] = int(m.group(1))

    # 스킬 데미지
    m = re.search(r'스킬.*?\+(\d+)%', effect)
    if m:
        # TODO: 스킬 데미지는 게임 시스템에서 처리 필요
        pass

    # 모든 스탯
    m = re.search(r'모든 스탯.*?\+(\d+)%', effect)
    if m:
        config["bonus_all_stats_pct"] = int(m.group(1))

    # HP 보너스
    m = re.search(r'HP.*?\+(\d+)%', effect)
    if m:
        config["bonus_hp_pct"] = int(m.group(1))

    # 속도
    m = re.search(r'속도.*?\+(\d+)', effect)
    if m:
        config["speed"] = int(m.group(1))

    # 경험치
    m = re.search(r'경험치.*?\+(\d+)%', effect)
    if m:
        config["exp_bonus"] = int(m.group(1))

    # 드롭률
    m = re.search(r'드롭.*?\+(\d+)%', effect)
    if m:
        config["drop_rate"] = int(m.group(1))

    # 받는 피해 감소
    m = re.search(r'받는 피해.*?-(\d+)%', effect)
    if m:
        # TODO: 받는 피해는 damage reduction 시스템 필요
        pass

    # config에 tag만 있으면 파싱 실패
    if len(config) == 1:
        return None

    return config


def parse_regen(effect: str) -> Optional[Dict]:
    """HP 재생 효과 파싱"""
    m = re.search(r'HP.*?재생.*?\+?(\d+)/분', effect)
    if m:
        return {
            "tag": "passive_regen",
            "hp_per_turn": int(m.group(1))
        }

    m = re.search(r'매 턴.*?HP.*?(\d+)%.*?회복', effect)
    if m:
        return {
            "tag": "passive_regen",
            "hp_percent_per_turn": float(m.group(1))
        }

    return None


def parse_turn_scaling(effect: str) -> Optional[Dict]:
    """턴당 스탯 증가 효과 파싱"""
    m = re.search(r'전투 중.*?영구.*?공격력.*?\+(\d+)%/턴', effect)
    if m:
        return {
            "tag": "passive_turn_scaling",
            "attack_per_turn": int(m.group(1))
        }

    return None


def effect_to_config(effect: str) -> Optional[str]:
    """
    효과 텍스트를 config JSON으로 변환

    Returns:
        JSON string 또는 None (변환 불가)
    """
    if not effect:
        return None

    # 복합 효과 (쉼표로 구분)
    if ',' in effect:
        parts = [p.strip() for p in effect.split(',')]
        components = []

        for part in parts:
            # 각 부분을 개별 파싱
            comp = parse_stat_bonus(part)
            if comp:
                components.append(comp)
            else:
                comp = parse_regen(part)
                if comp:
                    components.append(comp)
                else:
                    comp = parse_turn_scaling(part)
                    if comp:
                        components.append(comp)

        if components:
            # 모든 컴포넌트를 하나의 passive_buff로 병합
            merged = {"tag": "passive_buff"}
            for comp in components:
                if comp["tag"] == "passive_buff":
                    merged.update({k: v for k, v in comp.items() if k != "tag"})
                elif comp["tag"] == "passive_regen":
                    # 재생은 별도 컴포넌트로
                    return json.dumps({"components": components}, ensure_ascii=False)

            if len(merged) > 1:
                return json.dumps({"components": [merged]}, ensure_ascii=False)

        return None

    # 단일 효과
    config = parse_stat_bonus(effect)
    if config:
        return json.dumps({"components": [config]}, ensure_ascii=False)

    config = parse_regen(effect)
    if config:
        return json.dumps({"components": [config]}, ensure_ascii=False)

    config = parse_turn_scaling(effect)
    if config:
        return json.dumps({"components": [config]}, ensure_ascii=False)

    return None


def convert_equipment_csv(input_path: str, output_path: str, dry_run: bool = True):
    """
    장비 CSV를 읽어서 특수 효과를 컴포넌트로 변환

    Args:
        input_path: 입력 CSV 경로
        output_path: 출력 CSV 경로
        dry_run: True면 미리보기만, False면 실제 변환
    """
    rows = []
    stats = {
        "total": 0,
        "already_has_config": 0,
        "no_effect": 0,
        "converted": 0,
        "failed": 0,
    }

    converted_items = []
    failed_items = []

    with open(input_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames

        for row in reader:
            stats["total"] += 1
            item_id = row['ID']
            name = row['이름']
            effect = row.get('특수 효과', '').strip()
            config = row.get('config', '').strip()

            # 이미 config 있으면 스킵
            if config:
                stats["already_has_config"] += 1
                rows.append(row)
                continue

            # 효과 없으면 스킵
            if not effect:
                stats["no_effect"] += 1
                rows.append(row)
                continue

            # 변환 시도
            new_config = effect_to_config(effect)

            if new_config:
                row['config'] = new_config
                stats["converted"] += 1
                converted_items.append((item_id, name, effect, new_config))
            else:
                stats["failed"] += 1
                failed_items.append((item_id, name, effect))

            rows.append(row)

    # 결과 출력
    print("=" * 80)
    print("장비 효과 변환 결과")
    print("=" * 80)
    print(f"총 장비: {stats['total']}개")
    print(f"  - 이미 config 있음: {stats['already_has_config']}개")
    print(f"  - 효과 없음: {stats['no_effect']}개")
    print(f"  - 변환 성공: {stats['converted']}개")
    print(f"  - 변환 실패: {stats['failed']}개")
    print()

    if converted_items:
        print("=" * 80)
        print(f"✅ 변환 성공 ({len(converted_items)}개)")
        print("=" * 80)
        for item_id, name, effect, config in converted_items[:20]:
            print(f"[{item_id}] {name}")
            print(f"  효과: {effect}")
            print(f"  설정: {config}")
            print()

        if len(converted_items) > 20:
            print(f"... 외 {len(converted_items) - 20}개")
            print()

    if failed_items:
        print("=" * 80)
        print(f"❌ 변환 실패 ({len(failed_items)}개)")
        print("=" * 80)
        for item_id, name, effect in failed_items[:10]:
            print(f"[{item_id}] {name}: {effect}")

        if len(failed_items) > 10:
            print(f"... 외 {len(failed_items) - 10}개")
        print()

    # 파일 저장
    if not dry_run:
        with open(output_path, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        print(f"✅ 변환 완료: {output_path}")
    else:
        print("⚠️ Dry run 모드 - 실제 파일은 변경되지 않았습니다.")
        print(f"   실제 변환하려면 dry_run=False로 실행하세요.")


def main():
    import sys

    input_path = "data/items_equipment.csv"
    output_path = "data/items_equipment_converted.csv"

    # 인자로 --commit 전달 시 실제 변환
    dry_run = "--commit" not in sys.argv

    if dry_run:
        print("=" * 80)
        print("🔍 DRY RUN 모드 - 미리보기만 수행합니다")
        print("=" * 80)
        print("실제 변환하려면: python scripts/convert_equipment_to_components.py --commit")
        print()

    convert_equipment_csv(input_path, output_path, dry_run=dry_run)


if __name__ == "__main__":
    main()
