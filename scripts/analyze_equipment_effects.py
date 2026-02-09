"""
장비 특수 효과 분석 스크립트

모든 장비의 특수 효과를 분석하고 컴포넌트화 계획을 수립합니다.
"""
import csv
import json
import re
from collections import defaultdict
from typing import Dict, List, Tuple

# 현재 사용 가능한 패시브 컴포넌트
AVAILABLE_PASSIVE_COMPONENTS = {
    "passive_buff": "스탯 보너스 (attack, crit_rate, lifesteal, resist, 등)",
    "passive_regen": "HP/MP 재생",
    "conditional_passive": "조건부 스탯 보너스",
    "passive_element_immunity": "속성 면역",
    "passive_element_resistance": "속성 저항",
    "passive_damage_reflection": "피해 반사",
    "passive_status_immunity": "상태이상 면역",
    "passive_turn_scaling": "턴당 스탯 증가",
    "passive_debuff_reduction": "디버프 지속시간 감소",
    "passive_aura_buff": "아군 버프 오라",
    "passive_aura_debuff": "적 디버프 오라",
    "passive_revive": "부활",
}

# 효과 패턴 분류
EFFECT_PATTERNS = {
    # 기존 컴포넌트로 변환 가능
    "stat_bonus": [
        r"치명타.*?\+(\d+)%",
        r"흡혈.*?(\d+)%",
        r"회피.*?\+(\d+)%",
        r"명중률.*?\+(\d+)%",
        r"관통.*?\+(\d+)%",
        r"저항.*?\+(\d+)%",
        r"면역",
        r"스탯.*?\+(\d+)%",
        r"공격력.*?\+(\d+)%",
        r"속도.*?\+(\d+)",
        r"데미지.*?\+(\d+)%",
        r"스킬.*?\+(\d+)%",
        r"방어.*?-(\d+)%",
        r"피해.*?-(\d+)%",
    ],
    "turn_scaling": [
        r"턴당.*?\+(\d+)%",
        r"/턴",
        r"매 턴",
        r"전투 중.*?영구",
    ],
    "regen": [
        r"HP.*?재생",
        r"회복.*?\+(\d+)%",
        r"매 턴.*?HP.*?(\d+)%",
    ],

    # 새 컴포넌트 필요
    "on_attack_proc": [
        r"공격 시.*?(\d+)%",
        r"공격.*?확률",
    ],
    "on_kill": [
        r"처치 시",
        r"킬 시",
    ],
    "race_bonus": [
        r"종족.*?\+(\d+)%",
        r"드래곤.*?\+(\d+)%",
        r"언데드.*?\+(\d+)%",
        r"악마.*?\+(\d+)%",
        r"짐승.*?\+(\d+)%",
        r"마법사.*?\+(\d+)%",
    ],
    "conditional_damage": [
        r"HP.*?(\d+)%.*?이하",
        r"HP.*?(\d+)%.*?이상",
    ],
    "extra_turn": [
        r"추가 턴",
        r"재공격",
    ],
    "combo_stack": [
        r"연속.*?스택",
        r"스택.*?\+(\d+)%",
    ],

    # 특수 처리 필요
    "resource_cost": [
        r"마나.*?소모.*?-(\d+)%",
        r"쿨타임.*?-(\d+)%",
        r"슬롯.*?소모",
    ],
    "buff_duration": [
        r"버프.*?지속.*?\+(\d+)%",
        r"디버프.*?저항.*?\+(\d+)%",
    ],
    "healing_bonus": [
        r"회복.*?\+(\d+)%",
        r"힐.*?\+(\d+)%",
    ],
    "random": [
        r"랜덤",
        r"±(\d+)%",
    ],
    "special": [
        r"해금",
        r"탐지",
        r"감지",
        r"시야",
        r"드롭",
        r"경험치",
        r"선공",
        r"반격",
    ],
}


class EquipmentEffect:
    """장비 효과 데이터 클래스"""
    def __init__(self, item_id: str, name: str, effect: str, config: str):
        self.item_id = item_id
        self.name = name
        self.effect = effect
        self.config = config
        self.category = None
        self.convertible = False
        self.required_component = None
        self.notes = []


def categorize_effect(effect: str) -> Tuple[str, bool, str, List[str]]:
    """
    효과를 분석하여 카테고리, 변환 가능 여부, 필요 컴포넌트, 노트 반환

    Returns:
        (category, convertible, required_component, notes)
    """
    if not effect:
        return ("none", True, None, [])

    notes = []

    # 기존 컴포넌트로 변환 가능한 패턴
    for pattern in EFFECT_PATTERNS["stat_bonus"]:
        if re.search(pattern, effect):
            return ("stat_bonus", True, "passive_buff", ["단순 스탯 보너스"])

    for pattern in EFFECT_PATTERNS["turn_scaling"]:
        if re.search(pattern, effect):
            return ("turn_scaling", True, "passive_turn_scaling", ["턴당 증가 효과"])

    for pattern in EFFECT_PATTERNS["regen"]:
        if re.search(pattern, effect):
            return ("regen", True, "passive_regen", ["재생 효과"])

    # 새 컴포넌트 필요
    for pattern in EFFECT_PATTERNS["on_attack_proc"]:
        if re.search(pattern, effect):
            notes.append("공격 시 프록 효과")
            return ("on_attack_proc", False, "OnAttackProcComponent", notes)

    for pattern in EFFECT_PATTERNS["on_kill"]:
        if re.search(pattern, effect):
            notes.append("처치 시 효과")
            return ("on_kill", False, "OnKillComponent", notes)

    for pattern in EFFECT_PATTERNS["race_bonus"]:
        if re.search(pattern, effect):
            notes.append("종족 특효")
            return ("race_bonus", False, "RaceBonusComponent", notes)

    for pattern in EFFECT_PATTERNS["conditional_damage"]:
        if re.search(pattern, effect):
            notes.append("조건부 데미지 (conditional_passive 활용 가능할 수도)")
            return ("conditional_damage", False, "ConditionalDamageComponent", notes)

    for pattern in EFFECT_PATTERNS["extra_turn"]:
        if re.search(pattern, effect):
            notes.append("추가 턴 획득")
            return ("extra_turn", False, "ExtraTurnProcComponent", notes)

    for pattern in EFFECT_PATTERNS["combo_stack"]:
        if re.search(pattern, effect):
            notes.append("연속 공격 스택")
            return ("combo_stack", False, "ComboStackComponent", notes)

    # 특수 처리
    for pattern in EFFECT_PATTERNS["resource_cost"]:
        if re.search(pattern, effect):
            notes.append("리소스 비용 감소 - 게임 시스템 레벨 수정 필요")
            return ("resource_cost", False, "SystemLevel", notes)

    for pattern in EFFECT_PATTERNS["buff_duration"]:
        if re.search(pattern, effect):
            notes.append("버프 지속시간 - 게임 시스템 레벨 수정 필요")
            return ("buff_duration", False, "SystemLevel", notes)

    for pattern in EFFECT_PATTERNS["special"]:
        if re.search(pattern, effect):
            notes.append("특수 기능 - 개별 구현 필요")
            return ("special", False, "Special", notes)

    # 복합 효과 (여러 효과가 쉼표로 구분)
    if "," in effect:
        notes.append("복합 효과 - 개별 분석 필요")
        return ("complex", False, "Multiple", notes)

    # 알 수 없는 효과
    notes.append(f"알 수 없는 패턴: {effect}")
    return ("unknown", False, "Unknown", notes)


def analyze_equipment_csv(csv_path: str) -> Dict:
    """CSV 파일을 읽어서 장비 효과 분석"""
    effects = []
    stats = {
        "total": 0,
        "with_config": 0,
        "no_effect": 0,
        "text_only": 0,
        "by_category": defaultdict(int),
        "by_component": defaultdict(list),
        "convertible_count": 0,
        "need_new_component": 0,
    }

    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            stats["total"] += 1
            item_id = row['ID']
            name = row['이름']
            effect_text = row.get('특수 효과', '').strip()
            config = row.get('config', '').strip()

            # 이미 config가 있으면 스킵
            if config:
                stats["with_config"] += 1
                continue

            # 효과가 없으면 스킵
            if not effect_text:
                stats["no_effect"] += 1
                continue

            stats["text_only"] += 1

            # 효과 분석
            category, convertible, required_comp, notes = categorize_effect(effect_text)

            effect_obj = EquipmentEffect(item_id, name, effect_text, config)
            effect_obj.category = category
            effect_obj.convertible = convertible
            effect_obj.required_component = required_comp
            effect_obj.notes = notes

            effects.append(effect_obj)

            stats["by_category"][category] += 1
            stats["by_component"][required_comp].append(effect_obj)

            if convertible:
                stats["convertible_count"] += 1
            else:
                stats["need_new_component"] += 1

    return {
        "effects": effects,
        "stats": stats
    }


def generate_markdown_report(analysis: Dict, output_path: str):
    """분석 결과를 Markdown 보고서로 생성"""
    effects = analysis["effects"]
    stats = analysis["stats"]

    lines = []
    lines.append("# 장비 특수 효과 컴포넌트화 분석 보고서")
    lines.append("")
    lines.append(f"**생성일**: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")

    # 요약
    lines.append("## 📊 요약")
    lines.append("")
    lines.append(f"- **총 장비 개수**: {stats['total']}개")
    lines.append(f"- **이미 config 있음**: {stats['with_config']}개 ({stats['with_config']/stats['total']*100:.1f}%)")
    lines.append(f"- **특수 효과 없음**: {stats['no_effect']}개")
    lines.append(f"- **텍스트 효과만 있음**: {stats['text_only']}개")
    lines.append("")
    lines.append(f"### 변환 가능 여부")
    lines.append("")
    lines.append(f"- ✅ **기존 컴포넌트로 변환 가능**: {stats['convertible_count']}개 ({stats['convertible_count']/stats['text_only']*100:.1f}%)")
    lines.append(f"- 🔧 **새 컴포넌트 필요**: {stats['need_new_component']}개 ({stats['need_new_component']/stats['text_only']*100:.1f}%)")
    lines.append("")

    # 카테고리별 통계
    lines.append("## 📈 카테고리별 분류")
    lines.append("")
    lines.append("| 카테고리 | 개수 | 비율 |")
    lines.append("|---------|------|------|")
    for category, count in sorted(stats["by_category"].items(), key=lambda x: -x[1]):
        ratio = count / stats["text_only"] * 100
        lines.append(f"| {category} | {count}개 | {ratio:.1f}% |")
    lines.append("")

    # 필요한 컴포넌트별 분류
    lines.append("## 🔧 필요한 컴포넌트")
    lines.append("")

    for comp_name, items in sorted(stats["by_component"].items(), key=lambda x: -len(x[1])):
        if comp_name in AVAILABLE_PASSIVE_COMPONENTS:
            icon = "✅"
            status = "(기존 컴포넌트)"
        elif comp_name in ["SystemLevel", "Special", "Multiple", "Unknown"]:
            icon = "⚠️"
            status = "(특수 처리)"
        else:
            icon = "🔧"
            status = "(신규 구현 필요)"

        lines.append(f"### {icon} {comp_name} {status}")
        lines.append("")
        lines.append(f"**총 {len(items)}개 장비**")
        lines.append("")

        # 샘플 5개만 표시
        lines.append("| ID | 이름 | 효과 | 노트 |")
        lines.append("|----|------|------|------|")
        for item in items[:10]:
            notes_str = ", ".join(item.notes) if item.notes else "-"
            lines.append(f"| {item.item_id} | {item.name} | {item.effect} | {notes_str} |")

        if len(items) > 10:
            lines.append(f"| ... | ... | ... | 외 {len(items)-10}개 |")

        lines.append("")

    # 우선순위 제안
    lines.append("## 🎯 구현 우선순위 제안")
    lines.append("")

    lines.append("### Priority 1: 즉시 변환 가능 (기존 컴포넌트 활용)")
    lines.append("")
    convertible_items = [e for e in effects if e.convertible]
    lines.append(f"**{len(convertible_items)}개 장비를 즉시 변환 가능**")
    lines.append("")
    lines.append("- `passive_buff`: 스탯 보너스")
    lines.append("- `passive_turn_scaling`: 턴당 스탯 증가")
    lines.append("- `passive_regen`: HP/MP 재생")
    lines.append("")
    lines.append("**추천**: 이 그룹은 바로 CSV 업데이트 가능")
    lines.append("")

    lines.append("### Priority 2: 프록 시스템 구축 (높은 빈도)")
    lines.append("")
    proc_components = ["OnAttackProcComponent", "OnKillComponent"]
    proc_count = sum(len(stats["by_component"][c]) for c in proc_components if c in stats["by_component"])
    lines.append(f"**{proc_count}개 장비에 필요**")
    lines.append("")
    lines.append("**필요 작업**:")
    lines.append("1. 전투 시스템에 `on_attack`, `on_kill` 훅 추가")
    lines.append("2. `OnAttackProcComponent` 구현 (공격 시 확률 효과)")
    lines.append("3. `OnKillComponent` 구현 (처치 시 효과)")
    lines.append("")
    lines.append("**예상 난이도**: 중상 (전투 시스템 수정 필요)")
    lines.append("")

    lines.append("### Priority 3: 조건부 효과 (중간 빈도)")
    lines.append("")
    cond_components = ["RaceBonusComponent", "ConditionalDamageComponent", "ComboStackComponent"]
    cond_count = sum(len(stats["by_component"][c]) for c in cond_components if c in stats["by_component"])
    lines.append(f"**{cond_count}개 장비에 필요**")
    lines.append("")
    lines.append("**필요 작업**:")
    lines.append("1. `RaceBonusComponent` 구현 (종족 특효)")
    lines.append("2. `ConditionalDamageComponent` 구현 (HP 조건)")
    lines.append("3. `ComboStackComponent` 구현 (연속 공격 스택)")
    lines.append("")
    lines.append("**예상 난이도**: 중 (데미지 계산 로직 수정)")
    lines.append("")

    lines.append("### Priority 4: 시스템 레벨 수정 (낮은 빈도)")
    lines.append("")
    system_count = len(stats["by_component"]["SystemLevel"])
    lines.append(f"**{system_count}개 장비에 필요**")
    lines.append("")
    lines.append("**필요 작업**:")
    lines.append("1. 스킬 시스템: 마나 소모, 쿨타임, 슬롯 소모")
    lines.append("2. 버프 시스템: 버프 지속시간 수정")
    lines.append("")
    lines.append("**예상 난이도**: 높음 (코어 시스템 수정)")
    lines.append("**추천**: 나중에 처리 (개별 구현)")
    lines.append("")

    lines.append("### Priority 5: 특수 기능 (개별 구현)")
    lines.append("")
    special_count = len(stats["by_component"]["Special"])
    lines.append(f"**{special_count}개 장비에 필요**")
    lines.append("")
    lines.append("**내용**: 탐지, 시야, 드롭률, 경험치 등")
    lines.append("**추천**: 필요할 때마다 개별 구현")
    lines.append("")

    # 전체 효과 목록
    lines.append("## 📋 전체 장비 효과 목록")
    lines.append("")
    lines.append("| ID | 이름 | 효과 | 카테고리 | 컴포넌트 | 변환가능 |")
    lines.append("|----|------|------|----------|----------|----------|")

    for item in sorted(effects, key=lambda x: (not x.convertible, x.category, x.item_id)):
        conv_icon = "✅" if item.convertible else "❌"
        lines.append(f"| {item.item_id} | {item.name} | {item.effect} | {item.category} | {item.required_component} | {conv_icon} |")

    lines.append("")

    # 보고서 작성
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))


def main():
    csv_path = "data/items_equipment.csv"
    output_path = "docs/EquipmentEffectAnalysis.md"

    print("=" * 80)
    print("장비 특수 효과 컴포넌트화 분석")
    print("=" * 80)
    print()

    print(f"📂 CSV 파일 읽기: {csv_path}")
    analysis = analyze_equipment_csv(csv_path)

    print(f"✅ 분석 완료: {analysis['stats']['text_only']}개 효과 분석됨")
    print()

    print(f"📝 보고서 생성 중: {output_path}")
    generate_markdown_report(analysis, output_path)

    print(f"✅ 보고서 생성 완료!")
    print()

    # 요약 출력
    stats = analysis['stats']
    print("=" * 80)
    print("📊 분석 요약")
    print("=" * 80)
    print(f"총 장비: {stats['total']}개")
    print(f"  - 이미 config 있음: {stats['with_config']}개")
    print(f"  - 특수 효과 없음: {stats['no_effect']}개")
    print(f"  - 텍스트만 있음: {stats['text_only']}개")
    print()
    print(f"변환 가능 분류:")
    print(f"  ✅ 즉시 변환 가능: {stats['convertible_count']}개")
    print(f"  🔧 새 컴포넌트 필요: {stats['need_new_component']}개")
    print()
    print(f"📄 상세 보고서: {output_path}")


if __name__ == "__main__":
    main()
