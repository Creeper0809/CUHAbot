# 스킬 데미지 강화 시스템 (Skill Damage Boost System)

## 개요

장비에 장착 시 스킬 데미지를 증폭시키는 패시브 효과 시스템입니다.
전투 중 스킬 사용 시 자동으로 적용되며, 4가지 타입의 데미지 강화 효과를 지원합니다.

## 구현 완료 상태

- ✅ 4개 컴포넌트 구현
- ✅ 전투 시스템 통합
- ✅ 장비 캐싱 시스템
- ✅ 21개 장비에 적용 완료

## 컴포넌트 종류

### 1. SkillDamageBoostComponent (`skill_damage_boost`)

**기능**: 모든 스킬의 데미지를 일정 비율만큼 증가시킵니다.

**Config 형식**:
```json
{
  "tag": "skill_damage_boost",
  "damage_bonus": 0.25  // 25% 증가
}
```

**적용 장비**:
- [1007] 심해검: 모든 스킬 +25%
- [1012] 왕의 검: 모든 스킬 +20%
- [1019] 고대 유물검: 모든 스킬 +15%
- [1021] 차원 파괴의 검: 모든 스킬 +15%

### 2. SkillTypeDamageBoostComponent (`skill_type_damage_boost`)

**기능**: 특정 타입의 스킬에만 데미지 보너스를 적용합니다.

**지원 타입**:
- `awakening`: 각성 스킬
- `healing`: 회복 스킬
- `physical`: 물리 공격 스킬
- `magical`: 마법 공격 스킬
- `buff`: 버프 스킬
- `debuff`: 디버프 스킬

**Config 형식**:
```json
{
  "tag": "skill_type_damage_boost",
  "skill_type": "awakening",
  "damage_bonus": 0.50  // 50% 증가
}
```

**적용 장비**:
- [1008] 성검: 각성 스킬 +50%
- [1309] 심해의 활: 물리 공격 스킬 +30%
- [1310] 고대 유물 활: 마법 공격 스킬 +30%

### 3. AttributeDamageBoostComponent (`attribute_damage_boost`)

**기능**: 특정 속성의 스킬 데미지를 증가시킵니다.

**지원 속성**:
- 화염, 냉기, 번개, 수속성, 신성, 암흑

**Config 형식**:
```json
{
  "tag": "attribute_damage_boost",
  "attribute": "화염",
  "damage_bonus": 0.30  // 30% 증가
}
```

**적용 장비**:
- [1501] 잃어버린 왕국의 단검: 화염 스킬 +30%
- [1502] 고대 사제의 홀: 냉기 스킬 +30%
- [1503] 잠든 용의 이빨: 번개 스킬 +30%
- [1504] 요정의 비수: 수속성 스킬 +30%
- [1505] 달빛 검: 신성 스킬 +30%
- [1506] 저주받은 왕의 검: 암흑 스킬 +30%
- [1019] 고대 유물검: 신성 스킬 +40% (복합)
- [1021] 차원 파괴의 검: 암흑 스킬 +40% (복합)

### 4. ConditionalDamageBoostComponent (`conditional_damage_boost`)

**기능**: 특정 조건을 만족하는 대상에게 추가 데미지를 줍니다.

**조건 타입**:
- `low_hp`: HP가 특정 비율 이하인 적 (처형 효과)
- `high_hp`: HP가 특정 비율 이상인 적
- `status`: 특정 상태이상에 걸린 적

**Config 형식**:
```json
{
  "tag": "conditional_damage_boost",
  "condition": "low_hp",
  "threshold": 0.30,      // HP 30% 이하
  "damage_bonus": 1.00    // 100% 추가 데미지
}
```

또는:
```json
{
  "tag": "conditional_damage_boost",
  "condition": "status",
  "status_effect": "poison",  // 중독 상태
  "damage_bonus": 0.80        // 80% 추가 데미지
}
```

**적용 장비**:
- [1009] 마검: HP 30% 이하 적 +100%
- [1011] 혼돈의 검: HP 20% 이하 적 +150%
- [1012] 왕의 검: HP 40% 이하 적 +50% (복합)
- [1016] 공허의 검: 중독 상태 적 +80%
- [1017] 심해의 대검: 동결 상태 적 +100%
- [1018] 각성의 검: 감전 상태 적 +90%

## 복합 효과 예시

장비는 여러 컴포넌트를 동시에 가질 수 있습니다.

**[1012] 왕의 검**:
```json
{
  "components": [
    {"tag": "passive_buff", "crit_damage": 30},
    {"tag": "skill_damage_boost", "damage_bonus": 0.2},
    {"tag": "conditional_damage_boost", "condition": "low_hp", "threshold": 0.4, "damage_bonus": 0.5}
  ]
}
```
- 기본: 치명타 데미지 +30%, 모든 스킬 데미지 +20%
- 조건부: HP 40% 이하 적에게 추가 +50%

**[1019] 고대 유물검**:
```json
{
  "components": [
    {"tag": "passive_buff", "bonus_all_stats_pct": 15},
    {"tag": "attribute_damage_boost", "attribute": "신성", "damage_bonus": 0.4},
    {"tag": "skill_damage_boost", "damage_bonus": 0.15}
  ]
}
```
- 기본: 모든 스탯 +15%, 모든 스킬 데미지 +15%
- 속성: 신성 스킬 추가 +40%

## 시스템 아키텍처

### 1. 컴포넌트 파일

**`service/dungeon/components/skill_damage_components.py`**
- 4개의 스킬 데미지 강화 컴포넌트 정의
- 각 컴포넌트는 `get_skill_damage_multiplier()` 또는 `get_conditional_damage_multiplier()` 메서드 제공

### 2. 장비 모디파이어 시스템

**`service/dungeon/equipment_skill_modifier.py`**
- `cache_equipment_components(user)`: 전투 시작 시 유저의 장비 컴포넌트 캐싱
- `get_equipment_skill_damage_multiplier_sync(attacker, skill, target)`: 캐시에서 스킬 데미지 배율 계산

### 3. 전투 통합

**`service/dungeon/combat_executor.py`**
- 전투 시작 시 `cache_equipment_components()` 호출로 장비 컴포넌트 캐싱

**`service/dungeon/components/attack_components.py`**
- `DamageComponent.on_turn()` 내에서 `get_equipment_skill_damage_multiplier_sync()` 호출
- 스킬 데미지 배율을 `combined_mult`에 곱하여 최종 데미지에 반영

### 4. 스킬 참조

**`service/dungeon/skill.py`**
- `Skill.__init__()` 에서 각 컴포넌트에 `comp.skill = self` 설정
- 컴포넌트가 부모 스킬 정보 접근 가능 (속성, 타입 판별용)

## 데미지 계산 흐름

```
1. 유저가 스킬 사용
   ↓
2. DamageComponent.on_turn() 호출
   ↓
3. get_equipment_skill_damage_multiplier_sync() 호출
   ↓
4. 캐싱된 장비 컴포넌트 순회:
   - skill_damage_boost: 1.0 + bonus
   - skill_type_damage_boost: 스킬 타입 체크 후 배율
   - attribute_damage_boost: 스킬 속성 체크 후 배율
   - conditional_damage_boost: 대상 상태 체크 후 배율
   ↓
5. 모든 배율을 곱셈으로 합산 (예: 1.25 * 1.3 = 1.625)
   ↓
6. 최종 데미지 배율에 적용:
   combined_mult = attr_mult * synergy_mult * damage_taken_mult * hp_dmg_bonus * equipment_skill_mult
```

## 추가 가능한 스킬 타입 (향후 확장)

현재 시스템은 확장 가능하도록 설계되었습니다.

**추가 가능한 skill_type**:
- `aoe`: 전체 공격 스킬
- `single_target`: 단일 대상 스킬
- `dot`: 지속 데미지 스킬
- `summon`: 소환 스킬
- `combo`: 콤보 스킬

**추가 가능한 condition**:
- `critical`: 치명타 발동 시
- `first_hit`: 전투 첫 타격
- `low_mana`: 마나가 낮을 때
- `full_hp`: HP가 만땅일 때

## 테스트 방법

```bash
# 1. 장비 컴포넌트 검증
python scripts/verify_equipment_components.py

# 2. 실제 전투 테스트
# - 봇 실행 후 스킬 데미지 강화 장비 장착
# - 던전 입장하여 전투 시작
# - 데미지 로그에서 증폭된 수치 확인
```

## 주의사항

1. **배율 곱셈**: 여러 효과가 곱셈으로 적용되므로, 과도한 중첩 시 밸런스 주의
2. **캐싱**: 전투 시작 시 한 번만 캐싱되므로, 전투 중 장비 교체 불가 (전투 중 장비 교체는 시스템상 금지됨)
3. **몬스터**: 현재 몬스터는 장비를 착용하지 않으므로, 이 시스템의 혜택을 받지 않음

## 성능 최적화

- ✅ 전투 시작 시 한 번만 장비 컴포넌트 캐싱 (DB 쿼리 최소화)
- ✅ 동기 함수 사용 (`get_equipment_skill_damage_multiplier_sync`) - 턴마다 비동기 대기 불필요
- ✅ 컴포넌트 태그 기반 필터링으로 불필요한 순회 최소화

## 관련 파일

- `service/dungeon/components/skill_damage_components.py` - 컴포넌트 정의
- `service/dungeon/equipment_skill_modifier.py` - 장비 모디파이어 헬퍼
- `service/dungeon/combat_executor.py` - 전투 시작 시 캐싱
- `service/dungeon/components/attack_components.py` - DamageComponent 통합
- `service/dungeon/skill.py` - 스킬 참조 추가
- `scripts/assign_skill_damage_equipment.py` - 장비 컴포넌트 할당 스크립트
- `scripts/verify_equipment_components.py` - 검증 스크립트
