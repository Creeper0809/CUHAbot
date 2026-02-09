# 아이템 특수 효과 구현

## 개요

아이템 특수 효과를 패시브 시스템과 유사한 방식으로 구현했습니다.
CSV의 "특수 효과" 컬럼에서 자연어 텍스트를 파싱하여 JSON config로 변환하고, 장비 착용 시 스탯에 자동 반영됩니다.

## 구현 단계

### Phase 1: 분석 (완료 ✅)
- **스크립트**: `scripts/analyze_item_effects.py`
- **결과**: 295개 아이템 분석, 12개 카테고리로 분류
  - 스탯 % (53), 치명타 (33), 흡혈 (11), 저항 (32), 면역 (15)
  - 속성 데미지 (16), 스킬 강화 (22), 종족 특효 (8), 상태이상 (2)
  - 조건부 효과 (8), 특수 메커니즘 (37), 기타 (47)

### Phase 2: 파싱 (완료 ✅)
- **스크립트**: `scripts/parse_item_effects.py`
- **파싱 통계**:
  - 완전 파싱: 81개 (27%)
  - 부분 파싱: 73개 (25%)
  - 미파싱: 141개 (48%)
- **지원 효과**: 20+ 가지 효과 타입

### Phase 3: 구현 (완료 ✅)
1. **아이템 효과 파서 모듈**: `service/item/item_effect_parser.py`
   - 자연어 → JSON config 변환
   - 20+ 정규식 패턴 매칭

2. **장비 서비스 통합**: `service/item/equipment_service.py`
   - `calculate_equipment_stats()` 수정
   - Item.description에서 특수 효과 파싱 및 적용

3. **스탯 적용 확장**: `_apply_special_effects_to_stats()`
   - 퍼센트 기반 스탯 보너스
   - 고정값 스탯 보너스
   - 전투 효과 (치명타, 흡혈, 회피 등)
   - 속성 저항/데미지
   - 비전투 효과 (드롭률, 경험치)

4. **테스트**: `scripts/test_item_effects.py`
   - 파싱 테스트: ✅ 모두 통과
   - 스탯 계산 테스트: ✅ 통과 (유저 필요)

## 지원 효과 목록

### 전투 효과
- `crit_rate` - 치명타 확률 (%)
- `crit_damage` - 치명타 데미지 (%)
- `lifesteal` - 흡혈 (%)
- `armor_pen` - 물리 관통 (%)
- `magic_pen` - 마법 관통 (%)
- `evasion` - 회피 (%)
- `accuracy` - 명중률 (%)
- `block_rate` - 블록 (%)

### 스탯 보너스
- `bonus_hp_pct` - HP % 증가
- `bonus_speed_pct` - 속도 % 증가
- `bonus_all_stats_pct` - 모든 스탯 % 증가
- `attack`, `ap_attack` - 공격력 고정값
- `ad_defense`, `ap_defense` - 방어력 고정값
- `speed` - 속도 고정값

### 속성 저항
- `fire_resist`, `ice_resist`, `lightning_resist`
- `water_resist`, `holy_resist`, `dark_resist`

### 속성 데미지 보너스
- `fire_damage`, `ice_damage`, `lightning_damage`
- `water_damage`, `holy_damage`, `dark_damage`

### 비전투 효과
- `drop_rate` - 드롭률 (%)
- `exp_bonus` - 경험치 보너스 (%)

## 사용 예시

### CSV에서
```csv
ID,이름,특수 효과
1003,강철검,치명타 +3%
1007,심해검,흡혈 5%
1009,마검,흡혈 10%, HP -50
```

### 파싱 결과
```json
[
  {"type": "crit_rate", "value": 3},
  {"type": "lifesteal", "value": 5},
  {"type": "lifesteal", "value": 10}
]
```

### 적용 과정
1. 유저가 장비 착용
2. `EquipmentService.calculate_equipment_stats()` 호출
3. `Item.description`에서 특수 효과 파싱
4. `_apply_special_effects_to_stats()`로 스탯에 반영
5. 유저 스탯에 자동 적용 (`user.equipment_stats`)

## 미구현 효과

다음 효과들은 추가 구현이 필요합니다:

### On-Attack 트리거
- "공격 시 화상 10%"
- "공격 시 둔화 15%"
- "공격 시 연쇄 피해 20%"

### 조건부 효과
- "HP 30% 이하 적 +100%"
- "선공 시 확정 치명타"
- "전투 중 영구 공격력 +5%/턴"

### 특수 메커니즘
- "반사 10%"
- "부활 1회"
- "디버프 반사 30%"
- "피해 이연 30%"

### 종족 특효
- "드래곤 종족 +50%"
- "언데드 특효 +80%"

### 면역
- "CC 면역"
- "화염 면역"
- "치명타 면역"

### 스킬 강화
- "모든 스킬 +20%"
- "궁극기 쿨타임 -50%"
- "각성 스킬 +50%"

## 확장 방법

### 새 효과 타입 추가하기

1. **파서에 패턴 추가** (`item_effect_parser.py`):
```python
elif m := re.match(r'공격력\s*\+(\d+)%', part):
    effects.append({"type": "attack_pct", "value": int(m.group(1))})
```

2. **스탯 적용 로직 추가** (`equipment_service.py`):
```python
attack_pct = effects_agg.get("attack_pct", 0)
if attack_pct > 0 and stats["attack"] > 0:
    stats["attack"] += int(stats["attack"] * attack_pct / 100)
```

### 전투 중 효과 구현하기

1. **컴포넌트 생성** (예: `on_attack_burn.py`):
```python
@register_skill_with_tag("on_attack_burn")
class OnAttackBurnComponent(SkillComponent):
    def __init__(self, config: dict):
        self.chance = config.get("chance", 0)  # 10% 등

    def on_post_attack(self, user, target, damage, context):
        if random.random() < self.chance / 100:
            # 화상 적용
            apply_status_effect(target, StatusType.BURN, ...)
```

2. **전투 시스템에 훅 추가**:
- `combat_executor.py`에서 `process_skill_effects()` 후
- 장비 효과의 `on_post_attack()` 호출

## 아키텍처

```
Item (CSV)
  └─ description: "치명타 +5%, 흡혈 3%"
       │
       ↓ (seed_from_csv.py)
       │
Item (DB)
  └─ description: "치명타 +5%, 흡혈 3%"
       │
       ↓ (장비 착용)
       │
UserEquipment
       │
       ↓ (calculate_equipment_stats)
       │
parse_item_effect()
       │
       ↓ [{"type": "crit_rate", "value": 5}, ...]
       │
_apply_special_effects_to_stats()
       │
       ↓
User.equipment_stats
       │
       ↓ (get_stat)
       │
전투/UI에서 사용
```

## 참고 파일

- `service/item/item_effect_parser.py` - 파서
- `service/item/equipment_service.py` - 적용 로직
- `scripts/parse_item_effects.py` - 전체 파싱 스크립트
- `scripts/test_item_effects.py` - 테스트
- `data/parsed_item_effects.json` - 파싱 결과

## 컴포넌트 방식 전환 (완료 ✅)

### 변경 사항

**Phase 4: 아키텍처 개선 (2024)**

기존의 직접 스탯 조작 방식에서 집계 기반 방식으로 전환했습니다.

#### Before (Old Architecture)
```python
def _apply_special_effects_to_stats(stats, effects_agg):
    """100줄의 복잡한 if-elif 구조로 각 효과 타입별 직접 처리"""
    if "bonus_hp_pct" in effects_agg:
        stats["hp"] += int(stats["hp"] * effects_agg["bonus_hp_pct"] / 100)
    # ... 모든 효과 타입에 대한 반복적인 코드
```

#### After (New Architecture)
```python
# 1. 단순 집계 (equipment_passive_adapter.py)
def aggregate_equipment_effects(effects):
    """효과 타입별 합산만 수행"""
    aggregated = {}
    for effect in effects:
        aggregated[effect["type"]] = aggregated.get(effect["type"], 0) + effect["value"]
    return aggregated

# 2. 퍼센트 계산 (equipment_service.py)
def _aggregate_equipment_effects(effects, base_stats):
    """집계 후 퍼센트 효과만 계산"""
    effects_agg = aggregate_equipment_effects(effects)
    # 퍼센트 기반 효과만 특수 처리
    if "bonus_hp_pct" in effects_agg:
        effects_agg["hp"] = int(base_stats["hp"] * effects_agg["bonus_hp_pct"] / 100)
    return effects_agg
```

#### 개선 효과
- **코드 라인 수**: 100줄 → 30줄 (70% 감소)
- **복잡도**: O(n*m) → O(n) (m = 효과 타입 수)
- **책임 분리**: 집계 로직과 계산 로직 분리
- **테스트 용이성**: 각 함수를 독립적으로 테스트 가능
- **확장성**: 새 효과 타입 추가 시 코드 변경 최소화

#### 새로운 파일 구조
```
service/item/
  ├── equipment_service.py          (기존: 장비 착용/해제, 스탯 계산)
  │   └── _aggregate_equipment_effects()  (새: 퍼센트 계산)
  └── equipment_passive_adapter.py  (새: 효과 집계 전용)
      └── aggregate_equipment_effects()   (새: 단순 합산)
```

#### 테스트 커버리지
- `scripts/test_equipment_passive.py`
  - ✅ 효과 집계 테스트
  - ✅ 여러 장비 효과 집계
  - ✅ 퍼센트 효과 계산
  - ✅ 모든 스탯 퍼센트 보너스
  - ✅ 혼합 효과 (고정값 + 퍼센트)

