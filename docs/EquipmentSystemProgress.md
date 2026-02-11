# 장비 시스템 구현 진행 상황

## 📊 전체 진행률: 60% (189/332 items)

---

## ✅ Phase 1: 완료 (171 items)

### 1. Passive Stat Bonuses (154 items)
**컴포넌트**: `PassiveBuffComponent` (`passive_buff`)

**구현 완료 스탯**:
- 기본 스탯 보너스: 공격력, 방어력, 속도, HP 등
- 전투 스탯: 치명타율, 치명타 데미지, 흡혈
- 속성 저항: 화염, 냉기, 번개, 수속성, 신성, 암흑 저항
- 속성 데미지: 화염, 냉기, 번개, 수속성, 신성, 암흑 데미지
- 특수: 회피율, 명중률, 방어력 관통, 블록률
- 파밍: 드롭률, 경험치 보너스

### 2. Race Bonus (12 items)
**컴포넌트**: `RaceBonusComponent` (`race_bonus`)

**대상 종족**:
- Dragon, Beast, Undead, Demon, Slime, Goblin
- Elemental, Golem, Magic User

**적용 장비 예시**:
- [1010] 드래곤 슬레이어: 드래곤 +50%
- [1901] 슬라임 베인: 슬라임 +500%
- [1905] 성스러운 퇴마검: 언데드/악마 +250%

### 3. On-Attack Proc Effects (5 items)
**컴포넌트**: `OnAttackProcComponent` (`on_attack_proc`)

**효과 종류**:
- 상태이상 부여: 화상, 둔화, 감전 등
- 추가 데미지 (연쇄 피해)

**적용 장비 예시**:
- [1004] 화염검: 10% 확률 화상 부여
- [1006] 뇌전검: 20% 확률 감전 + 20% 연쇄 피해

---

## ✅ Phase 2: 완료 (21 items)

### 4. Skill Damage Boost (21 items)
**컴포넌트**:
- `SkillDamageBoostComponent` (`skill_damage_boost`) - 4 items
- `SkillTypeDamageBoostComponent` (`skill_type_damage_boost`) - 3 items
- `AttributeDamageBoostComponent` (`attribute_damage_boost`) - 8 items
- `ConditionalDamageBoostComponent` (`conditional_damage_boost`) - 6 items

**통합 완료**:
- ✅ 전투 시스템에 통합 (`DamageComponent`)
- ✅ 장비 캐싱 시스템 구현
- ✅ 스킬 참조 시스템 구현

**적용 장비 예시**:
- [1007] 심해검: 모든 스킬 +25%
- [1008] 성검: 각성 스킬 +50%
- [1501-1506] 속성 부적: 각 속성 스킬 +30%
- [1009] 마검: HP 30% 이하 적 +100%

---

## 🚧 Phase 3: 컴포넌트 구현 완료, 통합 대기 (13 items)

### 5. Cooldown Reduction (5 items)
**컴포넌트**: `CooldownReductionComponent` (`cooldown_reduction`)

**상태**: ⚠️ 컴포넌트 구현 완료, 스킬 쿨다운 시스템 미구현

**필요 작업**:
1. 스킬 모델에 `cooldown` 필드 추가
2. 사용 시 쿨다운 적용 로직
3. 장비 효과 적용 (쿨다운 감소)

**대상 장비**:
- [1013] 심연의 검: 쿨타임 -20%
- [1014] 심판의 검: 쿨타임 -25%
- [1022] 초월의 검: 쿨타임 -30%
- [1023] 전쟁신의 검: 쿨타임 -35%
- [1024] 창세의 검: 쿨타임 -40%

### 6. Buff Duration Extension (6 items)
**컴포넌트**: `BuffDurationExtensionComponent` (`buff_duration_extension`)

**상태**: ⚠️ 컴포넌트 구현 완료, 버프 지속시간 시스템 부분 구현

**필요 작업**:
1. 버프 적용 시 장비 효과 확인
2. 지속시간에 배율 적용

**대상 장비**:
- [2503] 고대 드워프 갑옷: 버프 지속시간 +50%
- [2601] 두꺼운 가죽 갑옷: 버프 지속시간 +30%
- [2804] 희생자의 로브: 버프 지속시간 +80% (복합 효과)

### 7. Mana Cost Reduction (2 items)
**컴포넌트**: `ManaCostReductionComponent` (`mana_cost_reduction`)

**상태**: ⚠️ 컴포넌트 구현 완료, 마나 시스템 미구현

**필요 작업**:
1. 스킬 모델에 `mana_cost` 필드 추가
2. 사용 시 마나 소모 로직
3. 장비 효과 적용 (마나 소모 감소)

**대상 장비**:
- [1612] 현자의 스태프: 마나 소모 -5%
- [1615] 별빛의 스태프: 마나 소모 -8%

---

## ⏳ Phase 4: 설계 필요 (remaining ~90 items)

### 8. On-Kill Stack (1 item - 완료)
**컴포넌트**: `OnKillStackComponent` (`on_kill_stack`)

**상태**: ✅ 구현 완료

**적용 장비**:
- [1020] 시련의 검: 처치 시 영구 공격력 +1% (최대 +20%)

### 9. Random Attribute Effects (6 items)
**상태**: 🔴 구현 필요

**효과 종류**:
- 랜덤 속성 부여
- 랜덤 속성 데미지 증가
- 데미지 변동성 증가

**대상 장비**:
- [1701] 운명의 주사위 검: 랜덤 속성 +30%
- [1702] 도박사의 단검: 데미지 -20%~+40% 랜덤
- [1703] 변덕스러운 마법봉: 매 턴 랜덤 속성
- [2701] 점술사의 로브: 랜덤 저항 +40%
- [2702] 도박꾼의 조끼: 데미지 -30%~+60% 랜덤

### 10. Special Combat Mechanics (11 items)
**상태**: 🔴 구현 필요

**효과 종류**:
- 선공권 (First Strike) - 전투 시작 시 먼저 공격
- 반격 (Counter Attack) - 피격 시 반격
- 추가 공격 (Extra Attack) - 공격 후 재공격
- 재생 (Regeneration) - 매 턴 HP 회복
- 부활 (Revive) - 사망 시 부활
- 데미지 반사 (Damage Reflection) - ✅ 이미 구현됨 (Phase 2 패시브)

**대상 장비**:
- [1308] 시간의 활: 30% 확률 즉시 재공격 (추가 공격)
- [1951] 살아있는 검: 매 턴 HP 5% 회복 (재생)
- [1952] 영혼 수집 낫: 처치 시 HP 20% 회복
- [1953] 전투 학습 장갑: 전투 중 영구 공격력 증가 (스택)
- [2804] 희생자의 로브: HP 소모 후 버프

### 11. Farming & Utility (already in passive_buff)
**상태**: ✅ 이미 구현됨

**효과 종류**:
- 드롭률 증가 (drop_rate)
- 경험치 보너스 (exp_bonus)

**적용 장비**: 이미 passive_buff로 구현됨

### 12. Conditional Stat Bonuses (~70 items)
**상태**: 🔴 대부분 미구현

**효과 종류**:
- HP 조건부 스탯 (HP 낮을수록 공격력 증가 등)
- 전투 중 스탯 증가 (턴당 증가) - ✅ 일부 구현됨 (`passive_turn_scaling`)
- 시간 조건부 (낮/밤, 요일 등)
- 상태이상 조건부

**대상 장비 예시**:
- [1801] 신앙의 검: HP 높을수록 공격력 증가
- [1802] 어둠을 삼킨 검: HP 낮을수록 공격력 증가
- [1803] 균형의 지팡이: HP 50%일 때 최대 데미지
- [1804] 고독한 전사의 검: 솔로 플레이 시 보너스
- [1805] 분노의 도끼: 피격 시 공격력 증가
- [1806] 수호자의 방패검: HP 높을수록 방어력 증가

### 13. Set Equipment (~228 members in 31 sets)
**상태**: ✅ 이미 구현됨

**시스템**: `set_detection_service.py`에서 세트 효과 처리

---

## 📈 구현 우선순위 제안

### High Priority (즉시 적용 가능)
1. ✅ **On-Kill Stack** - 구현 완료
2. ✅ **Skill Damage Boost** - 구현 완료
3. 🔴 **Random Attribute Effects** - 소규모, 재미 요소

### Medium Priority (시스템 확장 필요)
4. ⚠️ **Cooldown Reduction** - 쿨다운 시스템 구현 필요
5. ⚠️ **Buff Duration Extension** - 버프 시스템 일부 수정 필요
6. ⚠️ **Mana Cost Reduction** - 마나 시스템 구현 필요

### Low Priority (대규모 작업)
7. 🔴 **Special Combat Mechanics** - 전투 로직 수정 필요
8. 🔴 **Conditional Stat Bonuses** - 다양한 조건 처리 필요
9. 🔴 **Time-based Effects** - 시간 시스템 구현 필요

---

## 🎯 다음 단계 권장사항

### Option A: 완성도 우선
현재 구현된 시스템 (Phase 1-2)을 테스트하고 밸런스 조정에 집중

### Option B: 시스템 확장
Phase 3의 컴포넌트들을 실제 게임 시스템에 통합:
1. 스킬 쿨다운 시스템 구현
2. 마나 시스템 구현
3. 버프 지속시간 시스템 개선

### Option C: 특수 효과 추가
Phase 4의 재미있는 효과들 구현:
1. 랜덤 속성 효과 (도박 요소)
2. 선공권/반격 시스템
3. 조건부 스탯 보너스

---

## 📝 기술 부채 목록

1. **스킬 쿨다운 시스템**: 스킬 모델에 cooldown 필드 및 사용 제한 로직 필요
2. **마나 시스템**: 유저/몬스터 모델에 mana 필드 및 소모/회복 로직 필요
3. **버프 지속시간 API**: 현재 버프 시스템은 duration을 다루지만, 장비 효과 연동 미흡
4. **시간 시스템**: 낮/밤, 요일 등 시간 기반 효과를 위한 게임 시간 시스템 필요
5. **반격 시스템**: 피격 시 자동 반격을 위한 전투 훅 필요
6. **재공격 시스템**: 공격 후 즉시 재공격을 위한 행동 게이지 조정 필요

---

## 📚 관련 문서

- `docs/SkillDamageBoostSystem.md` - 스킬 데미지 강화 시스템 상세 문서
- `docs/ItemEffects_Implementation.md` - 아이템 효과 구현 계획 (기존)
- `docs/TODO.md` - 전체 프로젝트 TODO
