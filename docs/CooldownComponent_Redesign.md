# 쿨타임/마나 컴포넌트 재설계 (Bag 시스템 특화)

## 기존 컴포넌트 분석 및 폐기

### ❌ 완전 폐기
```python
# cooldown_components.py
CooldownReductionComponent      # 쿨타임 없음
ManaCostReductionComponent      # 마나 없음
SkillUsageLimitComponent        # 제한 없음 (Bag 시스템이 자연스럽게 제한)
```

### ✅ 유지 (이미 작동)
```python
BuffDurationExtensionComponent  # 버프 지속시간 연장 (이미 버프 시스템 있음)
```

---

## 🎨 새로운 컴포넌트 설계 (Bag 시스템 특화)

### 카테고리 1: 스킬 드로우 조작 (Bag Manipulation)

#### 1-1. SkillRefreshComponent (스킬 재장전)
**컨셉**: 스킬 사용 후 일정 확률로 가방에 다시 넣음

```python
@register_skill_with_tag("skill_refresh")
class SkillRefreshComponent(SkillComponent):
    """
    스킬 사용 후 재장전 효과

    Config:
        refresh_chance: 재장전 확률 (0.0 ~ 1.0)
        specific_skill_ids: 특정 스킬 ID만 재장전 (빈 리스트면 전체)
    """
    def __init__(self):
        super().__init__()
        self.refresh_chance = 0.0
        self.specific_skill_ids = []

    def on_skill_used(self, user, skill_id):
        """스킬 사용 직후 호출"""
        if self.specific_skill_ids and skill_id not in self.specific_skill_ids:
            return ""

        if random.random() < self.refresh_chance:
            # 스킬을 다시 가방에 넣음
            if hasattr(user, 'skill_queue'):
                user.skill_queue.insert(0, skill_id)  # 맨 앞에 넣어서 다음에 나올 확률 높임
            return f"   🔄 스킬 재장전! 「{skill_id}」 다시 사용 가능"
        return ""

# 장비 예시:
# "무한의 주머니" (일반)
# - refresh_chance: 0.3 (30% 확률로 스킬 재사용)
# - "사용한 스킬이 30% 확률로 다시 가방에 들어갑니다"

# "특화 암기" (희귀)
# - refresh_chance: 0.5
# - specific_skill_ids: [1101, 1102]  # 화염 스킬만
# - "화염 스킬이 50% 확률로 재장전됩니다"
```

#### 1-2. SkillRerollComponent (스킬 리롤)
**컨셉**: 턴당 1회 스킬을 다시 뽑을 수 있음

```python
@register_skill_with_tag("skill_reroll")
class SkillRerollComponent(SkillComponent):
    """
    스킬 리롤 효과

    Config:
        rerolls_per_turn: 턴당 리롤 횟수
        skip_skill_types: 리롤 시 제외할 스킬 타입 (예: ["heal"])
    """
    def __init__(self):
        super().__init__()
        self.rerolls_per_turn = 1
        self.skip_skill_types = []
        self._rerolls_used_this_turn = 0

    def on_turn_start(self, user, target):
        """턴 시작 시 리롤 카운터 리셋"""
        self._rerolls_used_this_turn = 0
        return ""

    def try_reroll(self, user):
        """리롤 시도"""
        if self._rerolls_used_this_turn >= self.rerolls_per_turn:
            return None, "리롤 횟수를 모두 사용했습니다"

        # 현재 스킬을 다시 가방에 넣고 새로운 스킬 뽑기
        new_skill = user.next_skill()
        self._rerolls_used_this_turn += 1
        return new_skill, f"🎲 스킬 리롤! (남은 횟수: {self.rerolls_per_turn - self._rerolls_used_this_turn})"

# 장비 예시:
# "운명의 주사위" (희귀)
# - rerolls_per_turn: 1
# - "매 턴 1회 스킬을 다시 뽑을 수 있습니다"

# "행운의 부적" (영웅)
# - rerolls_per_turn: 2
# - skip_skill_types: ["passive"]
# - "매 턴 2회 스킬을 리롤할 수 있습니다 (패시브 제외)"
```

#### 1-3. DoubleDrawComponent (스킬 2개 뽑기)
**컨셉**: 스킬을 2개 뽑아서 선택

```python
@register_skill_with_tag("double_draw")
class DoubleDrawComponent(SkillComponent):
    """
    스킬 2개 중 선택

    Config:
        proc_chance: 발동 확률 (1.0 = 100% 항상)
        auto_select_better: 자동으로 더 강한 스킬 선택 (False면 랜덤)
    """
    def __init__(self):
        super().__init__()
        self.proc_chance = 1.0
        self.auto_select_better = False

    def on_draw_skill(self, user):
        """스킬 뽑을 때 호출"""
        if random.random() > self.proc_chance:
            return None, ""

        # 2개 뽑기
        skill1 = user.next_skill()
        skill2 = user.next_skill()

        if not skill1 or not skill2:
            return skill1 or skill2, ""

        if self.auto_select_better:
            # 공격 스킬 우선, 없으면 첫 번째
            if hasattr(skill1, 'components'):
                for comp in skill1.components:
                    if getattr(comp, '_tag', '') == 'attack':
                        return skill1, f"🎴 2장 중 공격 스킬 선택!"
            return skill2, f"🎴 2장 중 선택!"
        else:
            # 랜덤 선택
            chosen = random.choice([skill1, skill2])
            return chosen, f"🎴 2장 중 1장 선택!"

# 장비 예시:
# "이중 홀스터" (희귀)
# - proc_chance: 1.0
# - auto_select_better: False
# - "스킬을 2개 뽑아서 랜덤으로 사용합니다"

# "전술가의 덱" (영웅)
# - proc_chance: 1.0
# - auto_select_better: True
# - "스킬을 2개 뽑아서 더 강한 것을 자동 선택합니다"
```

---

### 카테고리 2: 자원 변환 (Resource Conversion)

#### 2-1. HPCostEmpowerComponent (HP 소모 강화)
**컨셉**: 마나 대신 HP를 소모해서 스킬 강화

```python
@register_skill_with_tag("hp_cost_empower")
class HPCostEmpowerComponent(SkillComponent):
    """
    HP 소모로 스킬 강화

    Config:
        hp_cost_percent: HP 소모 비율 (5.0 = 5%)
        damage_boost_percent: 데미지 증가 비율 (30.0 = 30% 증가)
        min_hp_threshold: 최소 HP (이하로는 발동 안함, 10.0 = 10%)
    """
    def __init__(self):
        super().__init__()
        self.hp_cost_percent = 5.0
        self.damage_boost_percent = 30.0
        self.min_hp_threshold = 10.0

    def on_damage_calculation(self, event: DamageCalculationEvent):
        """데미지 계산 시 HP 소모하고 증폭"""
        attacker = event.attacker
        max_hp = attacker.hp
        current_hp_percent = (attacker.now_hp / max_hp) * 100

        if current_hp_percent <= self.min_hp_threshold:
            return  # HP 너무 낮으면 발동 안함

        # HP 소모
        hp_cost = int(max_hp * self.hp_cost_percent / 100)
        attacker.now_hp = max(1, attacker.now_hp - hp_cost)

        # 데미지 증폭
        boost_mult = 1.0 + (self.damage_boost_percent / 100)
        event.apply_multiplier(boost_mult, f"🩸 생명력 희생: 데미지 +{int(self.damage_boost_percent)}%")

# 장비 예시:
# "피의 계약서" (희귀)
# - hp_cost_percent: 5.0
# - damage_boost_percent: 30.0
# - min_hp_threshold: 10.0
# - "HP 5% 소모, 데미지 30% 증가 (HP 10% 이하면 발동 안함)"

# "광기의 검" (영웅)
# - hp_cost_percent: 10.0
# - damage_boost_percent: 60.0
# - min_hp_threshold: 5.0
# - "HP 10% 소모, 데미지 60% 증가 (HP 5% 이하면 발동 안함)"
```

#### 2-2. DefenseToAttackComponent (방어력 → 공격력 전환)
**컨셉**: 방어력을 희생해서 공격력 증가

```python
@register_skill_with_tag("defense_to_attack")
class DefenseToAttackComponent(SkillComponent):
    """
    방어력을 공격력으로 전환

    Config:
        conversion_ratio: 전환 비율 (0.5 = 방어력 50% → 공격력 추가)
        duration: 지속 턴 수 (0 = 영구)
    """
    def __init__(self):
        super().__init__()
        self.conversion_ratio = 0.5
        self.duration = 0
        self._converted_attack = 0
        self._converted_defense = 0

    def on_combat_start(self, user, target):
        """전투 시작 시 전환"""
        defense = user.defense
        converted_def = int(defense * self.conversion_ratio)
        converted_atk = converted_def

        user.defense -= converted_def
        user.attack += converted_atk

        self._converted_attack = converted_atk
        self._converted_defense = converted_def

        return f"⚔️🛡️ 방어력 {converted_def} → 공격력 {converted_atk} 전환!"

    def on_combat_end(self, user):
        """전투 종료 시 복구"""
        user.attack -= self._converted_attack
        user.defense += self._converted_defense

# 장비 예시:
# "광전사의 투구" (희귀)
# - conversion_ratio: 0.3
# - "방어력 30%를 공격력으로 전환합니다"

# "자살 특공대 갑옷" (영웅)
# - conversion_ratio: 0.8
# - "방어력 80%를 공격력으로 전환합니다"
```

---

### 카테고리 3: 스킬 체인 & 콤보

#### 3-1. ConsecutiveSkillBonusComponent (연속 스킬 보너스)
**컨셉**: 같은 타입의 스킬을 연속으로 사용하면 보너스

```python
@register_skill_with_tag("consecutive_skill_bonus")
class ConsecutiveSkillBonusComponent(SkillComponent):
    """
    연속 스킬 보너스

    Config:
        target_skill_type: 대상 스킬 타입 ("attack", "heal", "fire" 등)
        bonus_per_stack: 스택당 보너스 (10.0 = 10% 증가)
        max_stacks: 최대 스택 수
    """
    def __init__(self):
        super().__init__()
        self.target_skill_type = "attack"
        self.bonus_per_stack = 10.0
        self.max_stacks = 5
        self._current_stacks = 0
        self._last_skill_id = None

    def on_skill_used(self, user, skill):
        """스킬 사용 시 스택 추적"""
        skill_type = self._get_skill_type(skill)

        if skill_type == self.target_skill_type:
            if skill.id == self._last_skill_id:
                # 같은 스킬 연속 사용
                self._current_stacks = min(self._current_stacks + 1, self.max_stacks)
            else:
                # 다른 스킬 사용
                self._current_stacks = 1
            self._last_skill_id = skill.id
        else:
            # 다른 타입 스킬 사용 → 리셋
            self._current_stacks = 0
            self._last_skill_id = None

        if self._current_stacks > 0:
            return f"🔗 연속 {self._current_stacks}회! (데미지 +{int(self.bonus_per_stack * self._current_stacks)}%)"
        return ""

    def on_damage_calculation(self, event: DamageCalculationEvent):
        """데미지 계산 시 보너스 적용"""
        if self._current_stacks > 0:
            bonus = 1.0 + (self.bonus_per_stack * self._current_stacks / 100)
            event.apply_multiplier(bonus)

# 장비 예시:
# "화염 마스터의 로브" (희귀)
# - target_skill_type: "fire"
# - bonus_per_stack: 15.0
# - max_stacks: 3
# - "화염 스킬 연속 사용 시 스택당 15% 증가 (최대 3스택)"

# "광전사의 사슬" (영웅)
# - target_skill_type: "attack"
# - bonus_per_stack: 10.0
# - max_stacks: 5
# - "공격 스킬 연속 사용 시 스택당 10% 증가 (최대 5스택)"
```

#### 3-2. SkillVarietyBonusComponent (다양성 보너스)
**컨셉**: 다양한 타입의 스킬을 사용하면 보너스

```python
@register_skill_with_tag("skill_variety_bonus")
class SkillVarietyBonusComponent(SkillComponent):
    """
    스킬 다양성 보너스

    Config:
        bonus_per_unique: 고유 스킬당 보너스 (5.0 = 5%)
        max_unique_count: 최대 카운트
        reset_on_repeat: 중복 사용 시 리셋 여부
    """
    def __init__(self):
        super().__init__()
        self.bonus_per_unique = 5.0
        self.max_unique_count = 5
        self.reset_on_repeat = True
        self._used_skills = set()

    def on_skill_used(self, user, skill):
        """스킬 사용 추적"""
        if skill.id in self._used_skills and self.reset_on_repeat:
            # 중복 사용 → 리셋
            self._used_skills.clear()
            return "❌ 중복 사용! 다양성 보너스 리셋"

        self._used_skills.add(skill.id)
        unique_count = min(len(self._used_skills), self.max_unique_count)
        bonus = int(self.bonus_per_unique * unique_count)
        return f"🌈 다양성 보너스 {unique_count}종! (데미지 +{bonus}%)"

    def on_damage_calculation(self, event: DamageCalculationEvent):
        """보너스 적용"""
        unique_count = min(len(self._used_skills), self.max_unique_count)
        if unique_count > 0:
            bonus = 1.0 + (self.bonus_per_unique * unique_count / 100)
            event.apply_multiplier(bonus)

# 장비 예시:
# "만능 벨트" (희귀)
# - bonus_per_unique: 5.0
# - max_unique_count: 4
# - reset_on_repeat: True
# - "서로 다른 스킬 사용 시 5%씩 증가 (최대 20%, 중복 시 리셋)"

# "카멜레온 망토" (영웅)
# - bonus_per_unique: 8.0
# - max_unique_count: 5
# - reset_on_repeat: False
# - "서로 다른 스킬 사용 시 8%씩 증가 (최대 40%, 리셋 없음)"
```

---

### 카테고리 4: 턴 기반 효과

#### 4-1. TurnCountEmpowerComponent (턴 카운트 강화)
**컨셉**: 특정 턴마다 스킬 강화

```python
@register_skill_with_tag("turn_count_empower")
class TurnCountEmpowerComponent(SkillComponent):
    """
    특정 턴마다 강화

    Config:
        trigger_interval: 발동 간격 (3 = 3턴마다)
        damage_multiplier: 데미지 배율 (2.0 = 200%)
    """
    def __init__(self):
        super().__init__()
        self.trigger_interval = 3
        self.damage_multiplier = 2.0
        self._turn_count = 0

    def on_turn_start(self, user, target):
        """턴 카운트"""
        self._turn_count += 1
        if self._turn_count % self.trigger_interval == 0:
            return f"⏰ {self.trigger_interval}턴째! 다음 스킬 {int(self.damage_multiplier * 100)}% 데미지!"
        return ""

    def on_damage_calculation(self, event: DamageCalculationEvent):
        """강화 턴에만 적용"""
        if self._turn_count % self.trigger_interval == 0:
            event.apply_multiplier(self.damage_multiplier, "⏰ 타이밍 공격!")

# 장비 예시:
# "시계태엽 건틀릿" (희귀)
# - trigger_interval: 3
# - damage_multiplier: 2.0
# - "3턴마다 데미지 200%"

# "혜성 반지" (영웅)
# - trigger_interval: 5
# - damage_multiplier: 3.0
# - "5턴마다 데미지 300%"
```

#### 4-2. AccumulationComponent (누적 강화)
**컨셉**: 턴이 지날수록 강해짐

```python
@register_skill_with_tag("accumulation")
class AccumulationComponent(SkillComponent):
    """
    누적 강화

    Config:
        growth_per_turn: 턴당 성장 비율 (2.0 = 2%씩 증가)
        max_growth: 최대 성장 (50.0 = 50%까지)
    """
    def __init__(self):
        super().__init__()
        self.growth_per_turn = 2.0
        self.max_growth = 50.0
        self._accumulated = 0.0

    def on_turn_start(self, user, target):
        """누적"""
        self._accumulated = min(self._accumulated + self.growth_per_turn, self.max_growth)
        return f"📈 누적 강화: +{int(self._accumulated)}%"

    def on_damage_calculation(self, event: DamageCalculationEvent):
        """누적 데미지 적용"""
        if self._accumulated > 0:
            bonus = 1.0 + (self._accumulated / 100)
            event.apply_multiplier(bonus)

# 장비 예시:
# "시간의 검" (희귀)
# - growth_per_turn: 3.0
# - max_growth: 30.0
# - "매 턴 3%씩 강해집니다 (최대 30%)"

# "무한 성장의 반지" (영웅)
# - growth_per_turn: 5.0
# - max_growth: 100.0
# - "매 턴 5%씩 강해집니다 (최대 100%)"
```

---

## 📋 장비 적용 예시

### 희귀 장비
```csv
ID,이름,등급,효과,config
2001,무한의 주머니,희귀,사용한 스킬이 30% 확률로 다시 가방에 들어갑니다,"{\"components\":[{\"tag\":\"skill_refresh\",\"refresh_chance\":0.3}]}"
2002,운명의 주사위,희귀,매 턴 1회 스킬을 다시 뽑을 수 있습니다,"{\"components\":[{\"tag\":\"skill_reroll\",\"rerolls_per_turn\":1}]}"
2003,피의 계약서,희귀,HP 5% 소모하여 데미지 30% 증가,"{\"components\":[{\"tag\":\"hp_cost_empower\",\"hp_cost_percent\":5.0,\"damage_boost_percent\":30.0}]}"
2004,화염 마스터의 로브,희귀,화염 스킬 연속 사용 시 15%씩 증가 (최대 3스택),"{\"components\":[{\"tag\":\"consecutive_skill_bonus\",\"target_skill_type\":\"fire\",\"bonus_per_stack\":15.0,\"max_stacks\":3}]}"
```

### 영웅 장비
```csv
ID,이름,등급,효과,config
2101,전술가의 덱,영웅,스킬을 2개 뽑아서 더 강한 것을 자동 선택합니다,"{\"components\":[{\"tag\":\"double_draw\",\"proc_chance\":1.0,\"auto_select_better\":true}]}"
2102,광기의 검,영웅,HP 10% 소모하여 데미지 60% 증가,"{\"components\":[{\"tag\":\"hp_cost_empower\",\"hp_cost_percent\":10.0,\"damage_boost_percent\":60.0}]}"
2103,카멜레온 망토,영웅,서로 다른 스킬 사용 시 8%씩 증가 (최대 40%),"{\"components\":[{\"tag\":\"skill_variety_bonus\",\"bonus_per_unique\":8.0,\"max_unique_count\":5}]}"
2104,무한 성장의 반지,영웅,매 턴 5%씩 강해집니다 (최대 100%),"{\"components\":[{\"tag\":\"accumulation\",\"growth_per_turn\":5.0,\"max_growth\":100.0}]}"
```

### 조합 장비 (복합 효과)
```csv
ID,이름,등급,효과,config
2201,도박사의 유물,전설,스킬 2개 중 선택 + 30% 재장전,"{\"components\":[{\"tag\":\"double_draw\",\"proc_chance\":1.0},{\"tag\":\"skill_refresh\",\"refresh_chance\":0.3}]}"
2202,광전사의 유산,전설,HP 소모 강화 + 누적 성장,"{\"components\":[{\"tag\":\"hp_cost_empower\",\"hp_cost_percent\":8.0,\"damage_boost_percent\":50.0},{\"tag\":\"accumulation\",\"growth_per_turn\":3.0,\"max_growth\":60.0}]}"
```

---

## 🗑️ 제거할 파일 및 코드

### 1. 완전 삭제
```bash
# 파일 삭제
rm service/dungeon/components/cooldown_components.py

# __init__.py에서 임포트 제거
# service/dungeon/components/__init__.py
- from service.dungeon.components.cooldown_components import (
-     CooldownReductionComponent, ManaCostReductionComponent,
-     BuffDurationExtensionComponent, SkillUsageLimitComponent,
- )
```

### 2. CSV 데이터 정리
```bash
# 기존 장비 중 쿨타임/마나 관련 효과 제거
# data/items_equipment.csv에서 해당 컴포넌트 사용하는 아이템 재설계
```

---

## 🚀 구현 로드맵

### Phase 1: 새 컴포넌트 구현 (2-3일)
1. ✅ `service/dungeon/components/bag_manipulation_components.py` 생성
   - SkillRefreshComponent
   - SkillRerollComponent
   - DoubleDrawComponent

2. ✅ `service/dungeon/components/resource_conversion_components.py` 생성
   - HPCostEmpowerComponent
   - DefenseToAttackComponent

3. ✅ `service/dungeon/components/skill_chain_components.py` 생성
   - ConsecutiveSkillBonusComponent
   - SkillVarietyBonusComponent

4. ✅ `service/dungeon/components/turn_based_components.py` 생성
   - TurnCountEmpowerComponent
   - AccumulationComponent

### Phase 2: 통합 및 테스트 (1-2일)
1. ✅ `__init__.py`에 새 컴포넌트 등록
2. ✅ 이벤트 시스템 연결 (on_damage_calculation, on_skill_used 등)
3. ✅ 유닛 테스트 작성

### Phase 3: 데이터 마이그레이션 (1일)
1. ✅ 기존 쿨타임/마나 장비 재설계
2. ✅ 새 장비 추가
3. ✅ CSV 업데이트

### Phase 4: 구형 컴포넌트 제거 (1일)
1. ❌ `cooldown_components.py` 삭제
2. ✅ 관련 테스트 제거
3. ✅ 문서 업데이트

---

## 🎮 게임 플레이 예시

### 시나리오 1: 도박사 빌드
```
장비: 무한의 주머니 + 운명의 주사위

전투:
턴 1: 화염구 사용 → 30% 재장전 성공! 다시 가방에 들어감
턴 2: 치유 뽑음 → 리롤 사용 → 화염구 다시 뽑음!
턴 3: 화염구 사용 → 재장전 실패
턴 4: 번개 사용

전략: 강력한 스킬을 반복 사용
```

### 시나리오 2: 광전사 빌드
```
장비: 광기의 검 + 무한 성장의 반지

전투:
턴 1: HP 1000 → 900 (10% 소모), 데미지 160% (60% + 누적 5%)
턴 2: HP 900 → 810, 데미지 170% (60% + 누적 10%)
턴 3: HP 810 → 729, 데미지 175% (60% + 누적 15%)
...
턴 10: 데미지 210% (60% + 누적 50%)

전략: 장기전에서 압도적 화력
```

### 시나리오 3: 연쇄 공격 빌드
```
장비: 화염 마스터의 로브 + 화염 스킬 5개 장착

전투:
턴 1: 불꽃 (데미지 100%)
턴 2: 화염구 (데미지 115%, 1스택)
턴 3: 화염 폭발 (데미지 130%, 2스택)
턴 4: 불꽃 (데미지 145%, 3스택 max)
턴 5: 화염구 (데미지 145%, 3스택 유지)

전략: 단일 속성 집중 → 최대 45% 보너스
```

---

## ✅ 결론

**쿨타임/마나 제거 → Bag 시스템 특화 컴포넌트로 대체**

**장점:**
- ✅ 게임 시스템과 완벽 조화
- ✅ 더 다양하고 재미있는 전략
- ✅ 복잡도 감소 (쿨타임/마나 추적 불필요)
- ✅ 장비 조합의 깊이 증가

**다음 단계:**
Phase 1부터 구현 시작할까요?
