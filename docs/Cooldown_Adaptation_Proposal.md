# 쿨다운 시스템 적응 방안 (마나 제거)

## 현재 스킬 시스템 분석

### 작동 방식
1. **Bag/Shuffle 시스템**: 액티브 스킬들이 큐(`skill_queue`)에 담겨 셔플됨
2. **무제한 사용**: 스킬은 각 사이클마다 반복적으로 사용 가능
3. **마나 없음**: 스킬 사용에 자원 소모 없음
4. **쿨다운 없음**: 스킬 사용 제한 없음
5. **턴제 전투**: 행동 게이지 기반 (속도 스탯으로 결정)

### next_skill() 동작
```python
# models/users.py, models/monster.py
def next_skill(self):
    if not self.skill_queue:
        # 큐가 비었으면 액티브 스킬 수집
        active_ids = [sid for sid in self.equipped_skill
                      if sid != 0 and not is_passive_skill(sid)]
        self.skill_queue = active_ids[:]
        random.shuffle(self.skill_queue)  # 셔플

    skill_id = self.skill_queue.pop()  # 하나 꺼냄
    return get_skill_by_id(skill_id)
```

**문제점**: 쿨다운 컴포넌트(`CooldownReductionComponent`)가 있지만, 게임에 쿨다운 시스템이 없어서 적용 불가능

---

## 제안 1: 턴제 쿨다운 시스템 (가장 호환성 높음) ⭐ 추천

### 개념
- 각 스킬에 쿨다운 턴 수 설정 (예: 3턴)
- 스킬 사용 후 X턴 동안 다시 뽑을 수 없음
- 쿨다운이 끝나면 다시 덱 셔플에 포함됨

### 구현 방법

#### 1. 스킬 모델에 쿨다운 추가
```python
# models/skill_model.py
class SkillModel(Model):
    # ... 기존 필드
    cooldown: int = IntField(default=0)  # 쿨다운 턴 수
```

#### 2. User/Monster에 쿨다운 트래킹 추가
```python
# models/users.py, models/monster.py
class User(Model):
    # ... 기존 필드
    skill_cooldowns: dict[int, int] = {}  # {skill_id: remaining_turns}

    def next_skill(self):
        if not self.skill_queue:
            # 쿨다운 중이 아닌 액티브 스킬만 수집
            active_ids = [
                sid for sid in self.equipped_skill
                if sid != 0
                and not is_passive_skill(sid)
                and self.skill_cooldowns.get(sid, 0) == 0  # ✅ 쿨다운 체크
            ]
            if not active_ids:
                return None
            self.skill_queue = active_ids[:]
            random.shuffle(self.skill_queue)

        skill_id = self.skill_queue.pop()
        skill = get_skill_by_id(skill_id)

        # ✅ 스킬 사용 시 쿨다운 시작
        if skill and skill.skill_model.cooldown > 0:
            self.skill_cooldowns[skill_id] = skill.skill_model.cooldown

        return skill

    def reduce_cooldowns(self):
        """매 턴마다 모든 쿨다운 1씩 감소"""
        for skill_id in list(self.skill_cooldowns.keys()):
            if self.skill_cooldowns[skill_id] > 0:
                self.skill_cooldowns[skill_id] -= 1
            if self.skill_cooldowns[skill_id] == 0:
                del self.skill_cooldowns[skill_id]
```

#### 3. 전투 루프에 쿨다운 감소 통합
```python
# service/dungeon/combat_executor.py
def _execute_entity_action(user, actor, context):
    # ... 행동 실행

    # ✅ 행동 후 쿨다운 감소
    if hasattr(actor, 'reduce_cooldowns'):
        actor.reduce_cooldowns()

    return logs
```

#### 4. CooldownReductionComponent 통합
```python
# service/dungeon/components/cooldown_components.py
@register_skill_with_tag("cooldown_reduction")
class CooldownReductionComponent(SkillComponent):
    def __init__(self):
        super().__init__()
        self.reduction_percent = 0.0  # 20.0 = 20% 감소

    def on_turn(self, user, target):
        """스킬 사용 시 쿨다운 감소 적용"""
        if not hasattr(user, 'skill_cooldowns'):
            return ""

        # 모든 쿨다운 중인 스킬의 남은 턴 수 감소
        for skill_id in user.skill_cooldowns:
            if user.skill_cooldowns[skill_id] > 0:
                reduction = max(1, int(user.skill_cooldowns[skill_id] * self.reduction_percent / 100))
                user.skill_cooldowns[skill_id] = max(0, user.skill_cooldowns[skill_id] - reduction)

        if self.reduction_percent > 0:
            return f"   ⏱️ 쿨다운 {int(self.reduction_percent)}% 감소!"
        return ""
```

### 장단점
**✅ 장점:**
- 기존 bag 시스템과 완벽 호환
- 턴제 전투에 자연스럽게 통합
- 쿨다운 감소 컴포넌트 활용 가능
- 구현이 비교적 간단

**❌ 단점:**
- 모든 스킬이 쿨다운 중일 경우 처리 필요 (기본 공격으로 폴백)

### 예시 시나리오
```
덱: [화염구(CD 3턴), 치유(CD 2턴), 강타(CD 0턴), 방어(CD 1턴)]

턴 1: 화염구 사용 → 화염구 CD=3 시작
턴 2: 치유 사용 → 치유 CD=2 시작, 화염구 CD=2
턴 3: 방어 사용 → 방어 CD=1, 치유 CD=1, 화염구 CD=1
턴 4: 강타 사용 → 화염구/치유/방어 CD=0, 다시 셔플에 포함
```

---

## 제안 2: 사이클당 사용 횟수 제한

### 개념
- 마나 대신 "사이클당 사용 가능 횟수" 개념 도입
- 강력한 스킬은 한 사이클에 1-2회만 사용 가능
- 약한 스킬은 무제한 또는 높은 횟수

### 구현 방법

#### 1. 스킬 모델에 사용 제한 추가
```python
# models/skill_model.py
class SkillModel(Model):
    # ... 기존 필드
    max_uses_per_cycle: int = IntField(default=0)  # 0 = 무제한
```

#### 2. User/Monster에 사용 횟수 트래킹
```python
# models/users.py
class User(Model):
    skill_uses_this_cycle: dict[int, int] = {}  # {skill_id: uses_count}

    def next_skill(self):
        if not self.skill_queue:
            # 사용 가능 횟수가 남은 스킬만 수집
            active_ids = []
            for sid in self.equipped_skill:
                if sid == 0 or is_passive_skill(sid):
                    continue

                skill = get_skill_by_id(sid)
                max_uses = skill.skill_model.max_uses_per_cycle

                if max_uses == 0:  # 무제한
                    active_ids.append(sid)
                elif self.skill_uses_this_cycle.get(sid, 0) < max_uses:
                    active_ids.append(sid)

            if not active_ids:
                return None
            self.skill_queue = active_ids[:]
            random.shuffle(self.skill_queue)

            # ✅ 사이클 시작 시 카운터 초기화
            self.skill_uses_this_cycle.clear()

        skill_id = self.skill_queue.pop()
        skill = get_skill_by_id(skill_id)

        # ✅ 사용 횟수 증가
        self.skill_uses_this_cycle[skill_id] = self.skill_uses_this_cycle.get(skill_id, 0) + 1

        return skill
```

### 장단점
**✅ 장점:**
- 마나 없이 스킬 밸런스 조정 가능
- 강력한 스킬 남용 방지
- 전략적 선택 유도

**❌ 단점:**
- 사이클 개념이 명확하지 않을 수 있음
- 기존 쿨다운 컴포넌트와 호환 어려움

---

## 제안 3: 하이브리드 시스템 (쿨다운 + 사용 제한)

### 개념
- 제안 1과 제안 2를 결합
- 일부 스킬은 쿨다운 (긴 재사용 대기)
- 일부 스킬은 사용 횟수 제한 (폭발적 화력)

### 예시
```python
# 강력한 궁극기
skill_ultimate = Skill(
    cooldown=5,  # 5턴 대기
    max_uses_per_cycle=1,  # 사이클당 1회만
)

# 준궁극기
skill_powerful = Skill(
    cooldown=3,  # 3턴 대기
    max_uses_per_cycle=0,  # 무제한
)

# 일반 스킬
skill_normal = Skill(
    cooldown=1,  # 1턴 대기
    max_uses_per_cycle=0,
)

# 약한 스킬
skill_weak = Skill(
    cooldown=0,  # 쿨다운 없음
    max_uses_per_cycle=0,
)
```

---

## 마나 시스템 제거 방안

### 제거할 컴포넌트
```python
# ❌ 완전 제거
ManaCostReductionComponent  # 마나 비용 감소 → 의미 없음
```

### 변경할 컴포넌트
```python
# ✅ 쿨다운으로 대체
CooldownReductionComponent  # 쿨다운 감소 → 턴제 쿨다운 적용
BuffDurationExtensionComponent  # 버프 지속시간 연장 → 그대로 유지 가능
SkillUsageLimitComponent  # 스킬 사용 제한 → 사용 횟수 제한으로 변경
```

---

## 권장 로드맵

### Phase 1: 턴제 쿨다운 기반 구현 (1-2주)
1. ✅ `SkillModel`에 `cooldown` 필드 추가
2. ✅ `User`/`Monster`에 `skill_cooldowns` 딕셔너리 추가
3. ✅ `next_skill()` 메서드 수정 (쿨다운 체크)
4. ✅ `reduce_cooldowns()` 메서드 추가
5. ✅ 전투 루프에 쿨다운 감소 통합
6. ✅ `CooldownReductionComponent` 이벤트 통합
7. ✅ 테스트 작성 및 검증

### Phase 2: 사용 횟수 제한 추가 (선택, 1주)
1. ✅ `SkillModel`에 `max_uses_per_cycle` 추가
2. ✅ `User`에 `skill_uses_this_cycle` 추가
3. ✅ `next_skill()` 사용 횟수 체크 추가
4. ✅ `SkillUsageLimitComponent` 구현

### Phase 3: 마나 제거 및 정리 (1일)
1. ❌ `ManaCostReductionComponent` 제거
2. ✅ 관련 테스트 제거
3. ✅ CSV 데이터에서 마나 비용 제거

---

## 추천 방안

**⭐ 제안 1: 턴제 쿨다운 시스템** 을 권장합니다.

**이유:**
1. 기존 bag/shuffle 시스템과 완벽 호환
2. 턴제 전투에 자연스럽게 녹아듦
3. `CooldownReductionComponent` 활용 가능
4. 구현 난이도 낮음
5. 마나 없이도 스킬 밸런스 조정 가능

**다음 단계:**
- 제안 1 구현 스크립트 작성
- 스킬 CSV에 쿨다운 컬럼 추가
- 마이그레이션 스크립트 작성
- 테스트 케이스 작성

구현을 시작할까요?
