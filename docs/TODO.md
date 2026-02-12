# CUHABot 개발 TODO 목록

> 기획 문서 분석 기반 우선순위 정렬 (2024년 기준)
> 총 기능 수: 355개+ | 복잡도: 하(40), 중(194), 상(121+)

---

## 📊 개발 현황 요약

| Phase | 상태 | 진행률 |
|-------|------|--------|
| Phase 0: 코드 품질 | ✅ 완료 | 100% |
| Phase 1: 핵심 기반 | ✅ 완료 | 100% |
| Phase 2: 게임 루프 | ✅ 완료 | 100% |
| Phase 3: 전투 확장 | ✅ 완료 | 100% |
| Phase 4: 콘텐츠 확장 | 🔄 진행 중 | ~80% |
| Phase 5: 소셜/멀티 | ⏳ 대기 | 0% |
| Phase 6: 엔드게임 | ⏳ 대기 | 0% |

---

## ✅ Phase 0: 코드 품질 (Refactoring) - 완료

> 개발 지침 적용 및 코드 리팩토링

### 0.1 개발 인프라
- [x] `CLAUDE.md` 개발 지침 추가
- [x] `exceptions.py` 커스텀 예외 클래스 (25개+)
- [x] `config.py` 게임 상수 정의 (Magic Numbers 제거)
- [x] `pytest.ini` 테스트 설정

### 0.2 테스트 구조
- [x] `tests/` 디렉토리 구조 생성
- [x] `tests/conftest.py` 공통 픽스처
- [x] `tests/fixtures/` 테스트 데이터
- [x] `tests/unit/test_exceptions.py` 예외 유닛 테스트

### 0.3 모델 리팩토링
- [x] `models/users.py` 클래스 변수 → 인스턴스 변수
- [x] `models/monster.py` 클래스 변수 → 인스턴스 변수
- [x] 타입 힌트 추가
- [x] docstring 추가

### 0.4 서비스 리팩토링
- [x] `dungeon_service.py` fight() 함수 분해 (87줄 → 30줄 이하 함수들)
- [x] 로깅 추가
- [x] 커스텀 예외 적용
- [x] config 상수 적용

---

## 🔴 Phase 1: 핵심 기반 시스템 (Critical)

> 게임이 작동하기 위한 최소 필수 기능

### 1.1 사용자 시스템
- [x] 사용자 등록 (Discord 연동)
- [x] 사용자 정보 조회
- [x] `@requires_registration()` 데코레이터
- [x] 캐릭터 초기 스탯 생성 (`UserService.create_user()`)
- [x] 출석 체크 및 일일 보상 (`UserService.process_attendance()`)

### 1.2 데이터베이스 모델
- [x] Users 모델
- [x] Dungeon 모델
- [x] Monster 모델
- [x] Item 모델 (BaseItem, EquipmentItem, ConsumeItem)
- [x] Skill 모델
- [x] UserInventory 모델 (소지품 관리)
- [x] UserEquipment 모델 (장착 장비)
- [x] UserSkillDeck 모델 (스킬 덱)
- [x] UserStats 모델 (스탯 포인트 분배)

### 1.3 정적 데이터 캐싱
- [x] StaticCache 구현
- [x] 던전 데이터 로드
- [x] 몬스터 데이터 로드
- [x] 아이템 데이터 로드
- [x] 스킬 데이터 로드

### 1.4 세션 관리
- [x] DungeonSession 기본 구조
- [x] 세션 상태 추적 (탐험/전투/휴식) - `SessionType` enum 확장
- [ ] 세션 저장 및 복구 (Phase 2에서 구현)
- [x] 음성 채널 상태 추적 (`set_voice_channel()`)

---

## ✅ Phase 2: 게임 루프 (Essential) - 완료

> 기본 게임 플레이가 가능한 수준

### 2.1 던전 탐험 시스템
- [x] 던전 선택 UI (DungeonSelectView)
- [x] 던전 입장
- [x] 던전 탐험 진행 (스텝 기반) - `DungeonSession.exploration_step`
- [x] 인카운터 발생 시스템 - `EncounterFactory`
- [x] 던전 클리어 조건 - `_handle_dungeon_clear()`
- [x] 던전 귀환 (마을 복귀) - `_handle_dungeon_return()`

### 2.2 인카운터 시스템
- [x] 몬스터 인카운터 (전투) - 60% 확률
- [x] 보물상자 인카운터 - 10% (일반/실버/골드)
- [x] NPC 인카운터 - 5% (상인/현자/여행자)
- [x] 랜덤 이벤트 인카운터 (축복/저주) - 10%
- [x] 함정 인카운터 - 10% (HP 5~15% 피해)
- [x] 숨겨진 방 (5% 확률) - 희귀 보상

### 2.3 기본 전투 시스템
- [x] 전투 시작/종료 처리
- [x] FightOrFleeView (전투/도주 선택)
- [x] DungeonControlView (전투 컨트롤)
- [x] 턴제 전투 루프 구현 - `_execute_combat()`
- [x] 랜덤 스킬 발동 (덱에서 1/10 확률) - `SkillDeckService`
- [x] 도주 시스템 (50% 성공률) - `_attempt_flee()`
- [x] 전투 결과 처리 (승리/패배) - `_process_combat_result()`

### 2.4 데미지 계산 시스템
- [x] 물리 데미지 공식: `Attack - 적Defense × 0.5`
- [x] 마법 데미지 공식: `AP_Attack - 적AP_Defense × 0.4`
- [x] 치명타 계산 (Rate 확인 → 150% 데미지)
- [x] 명중률 계산 (Accuracy - Evasion)
- [x] 랜덤 변동 (±10%)
- [x] 방어력 무시 계산 (최대 70%)

> 구현: `service/combat/damage_calculator.py`

### 2.5 스킬 덱 시스템
- [x] 10슬롯 덱 기본 구조 - `UserSkillDeck` 모델
- [x] 덱 편집 UI - `DTO/skill_deck_view.py`
- [x] 스킬 중복 장착 허용
- [x] 발동 확률 계산 (슬롯수/10)
- [x] 덱 저장/불러오기 - `SkillDeckService`
- [x] **전투 중 덱 변경 불가** (규칙) - `is_in_combat()` 체크
- [x] Bag 시스템 (테트리스 주머니 방식) - 10개 슬롯 전부 1회씩 사용 후 셔플
  - 구현 완료: `User.next_skill()` 및 `Monster.next_skill()` 메서드에서 이미 동작 중
  - 위치: `models/users.py:90-107`, `models/monster.py:86-103`

> 커맨드: `/덱` - `cogs/dungeon_command.py`

### 2.6 기본 스킬 구현
- [x] 스킬 컴포넌트 시스템 (@register_skill_with_tag)
- [x] Attack 컴포넌트 - DamageCalculator 연동
- [x] Heal 컴포넌트
- [x] Buff 컴포넌트
- [x] Debuff 컴포넌트
- [x] 무속성 스킬 13개 구현 (ID 1001-1013)
- [x] 기본 회복 스킬 5개 구현 (ID 2001-2005)
- [x] 기본 버프 스킬 5개 구현 (ID 3001-3005)

> 시드 스크립트: `scripts/seed_skills.py`

---

## ✅ Phase 3: 전투 확장 (Completed)

> 전투의 깊이를 더하는 시스템

### 3.1 속성 시스템 ✅
- [x] 6개 속성 정의 (화염/냉기/번개/수/신성/암흑) - `config.AttributeType`
- [x] 속성 상성표 구현 - `config.ATTRIBUTE_ADVANTAGE`
- [x] 속성 데미지 배율 (+50%/-50%) - `config.get_attribute_multiplier()`
- [x] DB 마이그레이션 - `skill.attribute`, `monster.attribute` 컬럼 추가
- [x] 속성 저항 시스템 (최대 75%) - `ElementResistanceComponent`, `damage_pipeline.py`
- [x] 속성 면역 처리 - `ElementImmunityComponent`, `damage_pipeline.py`

### 3.2 속성별 스킬 구현 ✅
- [x] 화염 스킬 9개 (1101-1109)
- [x] 냉기 스킬 9개 (1201-1209)
- [x] 번개 스킬 9개 (1301-1309)
- [x] 수속성 스킬 10개 (1401-1410)
- [x] 신성 스킬 10개 (1501-1510)
- [x] 암흑 스킬 10개 (1601-1610)
- [x] CSV 시딩 완료 (214개 스킬)

### 3.3 키워드 시스템 ✅
- [x] 키워드 분류 체계 (속성/효과/역할) - CSV `키워드` 필드
- [x] 속성 키워드 7종 (화염/냉기/번개/수속성/신성/암흑/물리)
- [x] 공격 효과 키워드 18종 (잠식/침수/둔화/동결/기절/출혈/콤보/파쇄/중독/저주/흡혈/감염/화상/소각/연소/감전/마비/과부하/표식)
- [x] 보조 효과 키워드 7종 (재생/보호막/환류/축복/정화/결계/공명)
- [x] 키워드 밀도 자동 계산 (덱 내 동일 키워드 수) - UI 구현 완료
  - 구현: `service/synergy_service.py`
  - UI: `/내정보`, `/덱`, `/설명` 명령어
  - 시너지 시스템과 통합 (Phase 1 + Phase 2 완료)
  - 검색: `/설명 [키워드]`, `/설명 [시너지명]` 지원

### 3.4 상태이상 시스템 ✅
- [x] DOT 처리 (화상/중독/출혈/잠식) - `buff.py`: BurnEffect, PoisonEffect, BleedEffect, ErodeEffect
- [x] CC 처리 (둔화/동결/마비/기절) - `buff.py`: SlowEffect, FreezeEffect, ParalyzeEffect, StunEffect
- [x] 디버프 처리 (저주/표식/침수) - `buff.py`: CurseEffect, MarkEffect, SubmergeEffect
- [x] 스택형 상태이상 (화상/중독/출혈/잠식/콤보 등) - `StatusEffect.stacks`, `max_stacks`
- [x] 상태이상 아이콘/이모지 - `get_status_icons()`
- [x] 전투 루프 통합 - `process_status_ticks()`, `can_entity_act()`, `decay_all_durations()`
- [x] 상태이상 저항/면역 - `StatusImmunityComponent`, `helpers.py` 면역 체크
- [x] 피니셔 효과 (파쇄/소각/연소/과부하) - ConsumeComponent, ComboComponent

### 3.5 키워드 콤보 체인 ✅
- [x] 콤보 체인 엔진 - `skill_component.ComboComponent`
- [x] 화염 체인 (화상→소각→연소) - 스킬 8705, 8706
- [x] 냉기 체인 (둔화→동결→파쇄) - 스킬 8707, 8708
- [x] 번개 체인 (감전→마비→과부하) - 스킬 8709, 8710
- [x] 암흑 체인 (중독→저주→흡혈→감염) - 스킬 8711, 8712, 8713
- [x] 수속성 체인 (잠식→침수→감전/동결) - 스킬 8714, 8715
- [x] 물리 체인 (콤보→기절→파쇄/출혈) - 스킬 8716, 8717, 8718, 8719
- [x] 보조 체인 (축복 강화) - 스킬 8720
- [x] ConsumeComponent - 스택 비례 데미지 (기존 8001-8704)
- [x] ComboComponent - 조건부 보너스 효과 (신규 8705-8720)
- [x] 콤보 보너스 적용 - `damage_multiplier`, `force_critical`

### 3.6 버프/디버프 시스템 ✅
- [x] Buff 기본 구조 - `buff.Buff`, `TurnConfig`
- [x] 버프 스택 관리 - `AttackBuff`, `DefenseBuff`, `SpeedBuff`
- [x] 버프 지속시간 관리 - `duration`, `decrement_duration()`, `is_expired()`
- [x] 디버프 적용 - `DebuffComponent` 버그 수정
- [x] StatusEffect 기반 구조 - 14종 상태이상 구현
- [x] 버프 제거 스킬 - `CleanseComponent`

### 3.7 전투 형태 확장 ✅
- [x] 1:1 전투 (기본) - 현재 작동 중
- [x] 1:N 전투 (다구리) - **구현 완료** ✅
  - [x] `_spawn_monster_group()` 함수 추가
  - [x] `_execute_combat()` 다중 몬스터 지원 (CombatContext 래퍼 패턴)
  - [x] 다중 몬스터 순차 공격
  - [x] 전체 공격 스킬 처리 (AOE)
  - [x] 타겟팅 시스템 (LOWEST_HP, HIGHEST_HP, RANDOM, FIRST)
  - [x] 전투 임베드 다중 몬스터 HP 표시
- [ ] 어그로 시스템 - 향후 파티전 도입 시

### 3.8 전투 제한 규칙 ✅
- [x] **전투 중 아이템 사용 불가** - `item_use_service.py`
- [x] **전투 중 스킬 변경 불가** - `skill_deck_service.py`
- [x] 세션 기반 전투 상태 체크 - `get_session().in_combat`
- [ ] 도주 불가 상황 (엘리트/보스/타워) - 부분 구현 (보스는 도주 가능)

> **구현 파일:**
> - `config.py` - 속성 시스템
> - `service/dungeon/buff.py` - 버프/상태이상 (715줄)
> - `service/dungeon/skill_component.py` - 스킬 컴포넌트 (816줄)
> - `service/combat/damage_calculator.py` - 속성 배율 적용
> - `service/dungeon/dungeon_service.py` - 전투 루프 통합
> - `models/skill.py`, `models/monster.py` - attribute 필드
> - `data/skills.csv` - 214개 스킬 (16개 combo 스킬 추가)
> - `scripts/add_attribute_field.py` - DB 마이그레이션

---

## 🟢 Phase 4: 콘텐츠 확장 (Content)

> 게임의 볼륨을 늘리는 콘텐츠

### 4.1 던전 환경 효과 ✅
- [x] 화상 지대 (불타는 광산) - 매 라운드 최대 HP의 2% 데미지
- [x] 동결 확률 (얼어붙은 호수) - 매 행동마다 15% 확률로 1턴 동결
- [x] 감전 연쇄 (폭풍의 봉우리) - 데미지 연쇄 확률 증가
- [x] 익사 타이머 (수몰된 신전) - 3라운드마다 최대 HP의 5% 데미지
- [x] 차원 불안정 (혼돈의 균열) - 매 행동마다 20% 확률로 랜덤 상태이상
- [x] 시간 왜곡 (시공의 틈새) - 모든 속도가 불안정하게 변동
- [x] 공허의 잠식 (공허의 심연) - 모든 버프 지속시간 2배 감소
- [x] 수압 효과 (깊은 심해) - 모든 방어력 -10%
- [x] 각성의 기운 (각성의 제단) - 모든 공격력 +15%
- [x] 고대의 저주 (잊혀진 문명) - 매 행동마다 3% 즉사 확률
- [x] 필드 효과 시스템 구현 - `service/dungeon/field_effects.py`
- [x] 전투 시작 시 30% 확률로 랜덤 필드 효과 발동
- [x] UI에 필드 효과 표시 (Footer + 전투 로그)
- [x] 라운드/턴 기반 효과 처리

### 4.2 인벤토리 시스템 ✅
- [x] 인벤토리 조회 UI - `views/inventory/`
- [x] 페이지네이션 (10개 아이템/페이지)
- [x] 아이템 정렬 (등급/이름/수량) - `SortType`, `_apply_sort()`
- [x] 아이템 검색 - `SearchModal`, `_apply_search_filter()`
- [x] 아이템 삭제/판매 - `InventoryService.delete_inventory_item()`

> 구현: `views/inventory/list_view.py`, `views/inventory/components.py`, `service/item/inventory_service.py`

### 4.3 장비 시스템 ✅
- [x] 9개 장비 슬롯 (무기/투구/갑옷/장갑/신발/목걸이/반지×2/보조무기)
- [x] 장비 착용/해제 - `EquipmentService.equip_item()`, `unequip_item()`
- [x] 장비 교체 UI
- [x] 레벨 제한 체크 - `LevelRequirementError`
- [x] 장비 스탯 합산 - `calculate_equipment_stats()` (장비 + 강화 + 세트)
- [x] **장비 능력치 요구 시스템** - `docs/Items.md`
  - [x] DB 필드 추가 (`require_str/int/dex/vit/luk`)
  - [x] 착용 시 능력치 요구 체크 (`StatRequirementError`)
  - [x] 장비 정보 UI에 요구 능력치 표시
  - [x] 기존 장비 데이터에 요구치 설정

> 구현: `models/user_equipment.py` (9 slots), `service/item/equipment_service.py`

### 4.4 세트 아이템 시스템 ✅
- [x] 세트 효과 정의 (2/3/4/5/6/8세트) - `models/set_item.py`
- [x] 세트 착용 감지 - `SetDetectionService.detect_active_sets()`
- [x] 세트 보너스 적용 - `get_set_bonus_stats()`
- [x] 세트 효과 UI 표시 - `get_set_summary()`

> 구현: `models/set_item.py`, `service/item/set_detection_service.py`

### 4.5 아이템 강화 시스템 ✅
- [x] 강화 UI - `views/enhancement_view.py`
- [x] 강화 단계 (+0 ~ +15)
- [x] 강화 성공률 (단계별 차등: 100%→80%→60%→40%→20%)
- [x] 강화 실패 처리 (유지/-1/-2/reset/파괴)
- [x] 강화 비용 (골드) - 등급별/레벨별 계산
- [x] 축복/저주 시스템 - 축복(+10% 성공률, 실패 시 유지), 저주(-10%, 파괴 2배)

> 구현: `views/enhancement_view.py`, `service/item/enhancement_service.py`

### 4.6 소비 아이템 시스템 ✅
- [x] HP 포션 (등급별) - `ConsumeItem` 모델
- [x] 버프 포션 - buff_type, buff_amount, buff_duration
- [x] 상태이상 해제 아이템 - debuff_cleanse 필드, `apply_to_embed()` 표시
- [x] 투척 아이템 (전투용) - throwable_damage 필드
- [x] 탐험 보조 아이템 - 몬스터 기피제, 보물 지도, 드롭률 버프, 귀환 스크롤

> 구현: `models/consume_item.py`, `service/item/item_use_service.py`

### 4.7 드롭 시스템 ✅
- [x] 몬스터별 드롭 테이블 - `models/droptable.py`
- [x] 등급별 드롭 확률 - `DROP.DROP_RATE_D/C/B/A/S/SS/SSS/MYTHIC`
- [x] 타입별 배율 (일반/엘리트/보스) - `ELITE_DROP_MULTIPLIER`, `BOSS_DROP_MULTIPLIER`
- [x] 행운 스탯 반영 - `LUCK_DROP_BONUS_PER_POINT`
- [x] 드롭 결과 UI - `views/drop_result_view.py`

> 구현: `service/dungeon/drop_handler.py`, `models/droptable.py`, `config/drops.py`

### 4.8 능력치 시스템 ✅
- [x] 레벨업 시 포인트 획득 (레벨당 3포인트)
- [x] 스탯 포인트 분배 UI - `views/stat_distribution_view.py`
- [x] **5대 능력치 시스템으로 전환** (STR/INT/DEX/VIT/LUK → 전투 스탯 변환) - `docs/Stats.md`
  - [x] DB 스키마 변경 (`bonus_str/int/dex/vit/luk`)
  - [x] 능력치 → 전투 스탯 변환 로직 (`stat_conversion.py`, `get_stat()` 수정)
  - [x] 스탯 분배 UI 변경 (5대 능력치 + 변환 미리보기)
  - [x] HP 자연회복 %방식 전환 (최대HP × (1% + VIT×0.04%))
- [x] 스탯 시너지 효과 (Tier 1/2/3, 총 18종) - `docs/Stats.md`
  - [x] 시너지 조건 판정 시스템 (`config/stat_synergies.py`)
  - [x] 시너지 효과 전투 스탯 적용 (`synergy_service.py`)
  - [x] 시너지 발동 UI 표시 (`user_info_view.py`)
- [x] 스탯 리셋 기능 (`service/player/stat_service.py`)
- [x] 기존 유저 마이그레이션 (`scripts/migrate_stat_rework.py`)

> 기획: `docs/Stats.md`
> 구현: `views/stat_distribution_view.py`, `models/users.py`, `service/player/stat_conversion.py`, `service/player/synergy_service.py`

### 4.9 경험치/레벨 시스템 ✅
- [x] 경험치 획득 공식 - `RewardService`, `add_experience()`
- [x] 레벨업 처리 - `UserService.add_experience()` 통합
- [x] 레벨별 필요 경험치 테이블 (1-100) - `config/leveling.py`
- [x] 고레벨 성장 공식 (51+) - `UserService.calculate_base_stats()`
- [x] 레벨업 보상 (스탯 포인트 +3, HP 비율 유지 재계산)

> 구현: `service/player/user_service.py`, `config/leveling.py`, `config/user_stats.py`

---

## 🔵 Phase 5: 소셜/멀티플레이 (Social)

> 다른 플레이어와 상호작용

### 5.1 음성 채널 자동 파티
- [ ] 음성 채널 접속 감지
- [ ] 자동 파티 형성
- [ ] 파티 설정 옵션
- [ ] 파티 UI

### 5.2 전투 난입 시스템
- [x] 난입 알림 (전투 알림 메시지에 버튼 포함)
- [x] 난입 조건 체크 (10라운드 이내, 최대 3인 파티)
- [x] 난입 효과 (다음 라운드 참여, 어그로 분산)
- [x] 난입 보상 분배 (기여도 비례, 캐리 방지 페널티)
- [x] 난입 쿨타임 (5분)
- [x] 멀티플레이어 UI (플레이어 1행, 몬스터 2행)
- [x] 난입자 전투 UI 실시간 업데이트
- [x] 몬스터/플레이어 공격 대상 랜덤 선택
- [x] 필드 효과 난입자 적용
- [x] 리더 사망 시 처리 (전투 계속, 승리 후 탐험 종료)

### 5.4 관전 시스템
- [x] 실시간 전투 관전
- [x] 관전자 UI

### 5.5 옥션 시스템
- [x] 경매 등록 (입찰/즉시구매)
- [x] 구매 주문 (역경매)
- [x] 수수료 시스템
- [x] 가격 히스토리
- [x] 사기 방지 (에스크로)
- [x] 검색/필터

### 5.6 실시간 협동 퀘스트
- [ ] 긴급 보스 출현 (음성 채널 전용)
- [ ] 협동 보상 분배

### 5.8 랭킹 시스템
- [x] 레벨 랭킹
- [x] 골드 랭킹
- [ ] 주간 경험치 랭킹 (보류)
- [ ] 보스 처치 랭킹 (보류)
- [ ] 자산 랭킹 (보류)

---

## 🟣 Phase 6: 엔드게임 콘텐츠 (Endgame)

> 고레벨 플레이어를 위한 콘텐츠

### 6.1 주간 타워
- [x] 100층 타워 구조
- [x] 층별 몬스터 배치
- [x] 보스층 (10/20/30.../100)
- [x] **타워 내 아이템 사용 불가**
- [x] **층 사이 스킬 변경 허용**
- [x] 타워 시즌 시스템
- [x] 타워 보상 (층별)
- [ ] 타워 상점

### 6.2 레이드 던전 (3인)
- [ ] 파티 매칭
- [ ] 레이드 페이즈 시스템
- [ ] 8개 레이드 던전 구현
  - [ ] 세계수의 뿌리 (Lv.30+)
  - [ ] 마왕성 (Lv.40+)
  - [ ] 창세의 균열 (Lv.50)
  - [ ] 차원의 심장 (Lv.60+)
  - [ ] 용신의 무덤 (Lv.70+)
  - [ ] 죽음의 왕좌 (Lv.80+)
  - [ ] 태양신의 궁전 (Lv.90+)
  - [ ] 신들의 황혼 (Lv.100)

### 6.3 궁극기 시스템
- [x] 궁극기 슬롯 소모 규칙
- [x] 궁극기 5개+ 구현

### 6.4 키워드 밀도 시너지 시스템
- [ ] 속성 키워드 밀도 시너지 (3/5/7/10개)
- [ ] 효과 키워드 밀도 시너지 (3/5개)
- [ ] 마스터리 시너지 (10개 단일 속성 키워드)
- [ ] 키워드 조합 시너지 (원소 조화, 빛과 어둠, 글래스 캐논, 철벽 방어, 버서커, 서바이버, 상태이상 마스터, 셋업-피니셔 특화, 궁극기 특화)
- [ ] 시너지 스택 규칙 (마스터리 배타, 다종 중첩 허용)

### 6.5 스킬 숙련도 시스템
- [ ] 숙련도 모델 (UserSkillProficiency)
- [ ] 숙련도 등급 6단계 (미숙→익숙→숙련→정통→달인→초월)
- [ ] 사용 횟수 누적 카운트 (Bag 시스템 연동)
- [ ] 주 효과 보너스 적용 (최대 +20%)
- [ ] 부가 효과 보너스 적용 (상태이상 확률/지속시간/추가 가산)
- [ ] Lv.4+ 콤보 보너스 (+10%/+20%)
- [ ] Lv.6 키워드별 초월 효과 해금 (공격 효과 18종 + 보조 효과 7종)

### 6.6 패시브 스킬 시스템
- [x] 전투 패시브 (공격/방어/속도/치명타/상태이상) - `PassiveBuffComponent`, `passive_regen`, `passive_turn_scaling`
- [ ] 파밍 패시브 (경험치/드롭/골드)
- [ ] 탐험 패시브 (이동속도/함정감지/숨겨진방)
- [ ] 소셜 패시브 (파티 버프)
- [x] 특수 패시브 (부활/피흡) - `OnDeathReviveComponent`, `DamageReflectionComponent`
- [x] 조건부 패시브 (HP 조건 등) - `ConditionalPassiveComponent`
- [x] 방어 패시브 (면역/저항/반사/상태면역) - `defensive_passive_components.py`
- [x] 오라 패시브 (아군 버프/적 디버프) - `aura_passive_components.py`
- [x] 디버프 감소 패시브 - `DebuffReductionComponent`
- [x] 데미지 파이프라인 (면역→저항→보호막→반사) - `damage_pipeline.py`

### 6.7 N:M 파티 전투
- [x] 파티 전투 UI 레이아웃 (중앙 정렬, 1-3명 지원)
- [ ] 파티 전투 턴 순서
- [ ] 파티원 타겟팅
- [ ] 전체 힐/버프
- [ ] 파티 보상 분배

### 6.8 고급 던전 (Lv.51-100)
- [ ] 시공의 틈새 (Lv.51-55)
- [ ] 공허의 심연 (Lv.55-60)
- [ ] 깊은 심해 (Lv.61-65)
- [ ] 각성의 제단 (Lv.65-70)
- [ ] 잊혀진 문명의 폐허 (Lv.71-75)
- [ ] 시련의 탑 100층 (Lv.75-80)
- [ ] 붕괴하는 차원 (Lv.81-85)
- [ ] 초월자의 영역 (Lv.85-90)
- [ ] 신들의 전장 (Lv.91-95)
- [ ] 창세의 정원 (Lv.95-100)

---

## ⚪ Phase 7: 향후 확장 (Future)

> 장기 로드맵

### 7.1 길드 시스템
- [ ] 길드 생성/관리
- [ ] 길드 저장소
- [ ] 길드 스킬 연구
- [ ] 길드 전쟁
- [ ] 길드 랭킹
- [ ] 길드 옥션

### 7.2 PvP 시스템
- [ ] 1:1 대전
- [ ] 랭크 매칭
- [ ] PvP 시즌
- [ ] PvP 보상

### 7.3 업적 시스템
- [ ] 업적 카테고리 (전투/경제/수집/탐험/소셜)
- [ ] 업적 보상 (칭호/아이템/골드)
- [ ] 숨겨진 업적

### 7.4 계절 이벤트
- [ ] 이벤트 던전
- [ ] 이벤트 아이템
- [ ] 이벤트 퀘스트
- [ ] 누적 보상

### 7.5 신규 플레이어 지원
- [ ] 튜토리얼 퀘스트
- [ ] 신규 보호 (Lv.10까지 패널티 없음)
- [ ] 신규 부스트 (경험치 보너스)

---

## 📋 UI/UX 구현 목록

### Discord View Components
- [x] DungeonSelectView (던전 선택)
- [x] DungeonControlView (던전 컨트롤)
- [x] FightOrFleeView (전투/도주)
- [x] SkillDeckView (스킬 덱 편집) - `/덱` 커맨드
- [ ] InventoryView (인벤토리)
- [ ] EquipmentView (장비 관리)
- [ ] ShopView (상점)
- [ ] EnhanceView (강화)
- [ ] PartyView (파티 관리)
- [ ] AuctionView (옥션)
- [ ] TowerView (주간 타워)
- [ ] RaidLobbyView (레이드 대기)
- [ ] SettingsView (설정)

### Embed 디자인
- [ ] 캐릭터 정보 Embed
- [ ] 던전 정보 Embed
- [ ] 몬스터 정보 Embed
- [ ] 아이템 정보 Embed
- [ ] 전투 결과 Embed
- [ ] 보상 Embed
- [ ] 랭킹 Embed

### 이모지/리소스
- [x] ItemEmoji 관리자
- [ ] 속성 이모지 정의
- [ ] 상태이상 이모지 정의
- [ ] 등급별 색상 정의

---

## 🔧 기술적 작업

### 성능 최적화
- [ ] DB 쿼리 최적화
- [ ] 캐시 전략 개선
- [ ] 비동기 처리 최적화

### 코드 품질
- [x] 타입 힌트 추가 (진행 중)
- [x] 단위 테스트 작성 - `tests/unit/test_damage_calculator.py`
- [ ] 통합 테스트 작성
- [x] 에러 핸들링 개선 - `exceptions.py`

### 인프라
- [ ] 로깅 시스템 강화
- [ ] 모니터링 설정
- [ ] 백업 시스템

---

## 📝 참고 사항

### 핵심 게임 규칙
1. **전투 중 아이템 사용 불가**
2. **전투 중 스킬 변경 불가**
3. **주간 타워: 아이템 일절 불가, 스킬은 층 사이에만 변경 가능**
4. **패시브도 10개 스킬 슬롯 안에 장착**
5. **레벨과 등급은 독립적 (저레벨 고등급 가능)**

### 의존성 체인
```
사용자 시스템 → 세션 관리 → 던전 탐험 → 전투 시스템
                                    ↓
                              스킬 덱 시스템 (Bag)
                                    ↓
                              데미지 계산
                                    ↓
                              키워드/상태이상 → 콤보 체인
                                    ↓
                              키워드 밀도 시너지
                                    ↓
                              스킬 숙련도
```

### 예상 개발 기간
| Phase | 예상 기간 |
|-------|----------|
| Phase 1 | 2-3주 |
| Phase 2 | 3-4주 |
| Phase 3 | 4-5주 |
| Phase 4 | 6-8주 |
| Phase 5 | 4-6주 |
| Phase 6 | 8-12주 |
| Phase 7 | 지속적 |

---

*최종 업데이트: 2026-02-09 (Phase 3 완료, Phase 4 80% 완료, 패시브 Phase 2 완료 - 데미지 파이프라인/방어패시브/오라/부활/턴성장/디버프감소)*
