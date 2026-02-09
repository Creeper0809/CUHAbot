# 퀘스트 시스템 기획

## 개요

던전 탐험 중 NPC를 만나 퀘스트를 받고, 조건을 달성하면 보상을 받는 시스템입니다.
**옵저버 패턴**을 사용하여 퀘스트 진행 추적과 각 시스템 간의 커플링을 최소화합니다.

## 핵심 설계: 이벤트 기반 아키텍처

### 이벤트 시스템
```python
# 게임 내 발생하는 모든 이벤트
class GameEventType(Enum):
    MONSTER_KILLED = "monster_killed"
    ITEM_OBTAINED = "item_obtained"
    SKILL_OBTAINED = "skill_obtained"
    DUNGEON_EXPLORED = "dungeon_explored"
    FLOOR_CLEARED = "floor_cleared"
    COMBAT_WON = "combat_won"
    GOLD_OBTAINED = "gold_obtained"
    LEVEL_UP = "level_up"
    NPC_TALKED = "npc_talked"
    QUEST_ACCEPTED = "quest_accepted"
    QUEST_COMPLETED = "quest_completed"
```

### 옵저버 패턴
```
[Combat System] --발행--> [Game Event Bus] <--구독-- [Quest Progress Tracker]
[Item System]   --발행--> [Game Event Bus] <--구독-- [Quest Progress Tracker]
[Exploration]   --발행--> [Game Event Bus] <--구독-- [Quest Progress Tracker]
```

**장점:**
- 각 시스템은 퀘스트 존재 여부를 알 필요 없음
- 퀘스트 시스템 추가/제거가 기존 코드에 영향 없음
- 새로운 퀘스트 타입 추가 시 이벤트만 구독하면 됨

---

## 1. 퀘스트 타입

### 1.1 킬 퀘스트 (Kill Quest)
**목표:** 특정 몬스터를 N마리 처치

**던전 조건:**
- **던전별 퀘스트**: 특정 던전에서만 진행 가능 (예: "잊혀진 숲에서 슬라임 10마리 처치")
- **전역 퀘스트**: 모든 던전에서 진행 가능 (예: "아무 던전에서나 몬스터 100마리 처치")

**조건 타입:**
- 특정 몬스터 ID (예: 슬라임 ID=1001)
- 속성 조건 (예: 화염 속성 몬스터)
- 보스 여부 (예: 보스 몬스터만)

**예시:**
- "숲의 수호자" - 잊혀진 숲에서 슬라임 10마리 처치
- "불의 정화자" - 화염 던전에서 화염 속성 몬스터 5마리 처치
- "보스 헌터" - 아무 던전에서나 보스 몬스터 3마리 처치

**이벤트:** `MONSTER_KILLED`
```python
{
    "monster_id": 1001,
    "monster_name": "슬라임",
    "monster_attribute": Attribute.NONE,
    "is_boss": False,
    "dungeon_id": 1,  # 현재 던전 ID 추가
    "user_id": 123456
}
```

### 1.2 수집 퀘스트 (Collection Quest)
**목표:** 특정 소비 아이템을 N개 수집

**예시:**
- "약초 채집가" - 체력 포션 5개 수집
- "비약의 연금술사" - 마나 포션 10개 수집
- "물약 마스터" - 모든 종류의 포션 각 3개씩 수집

**이벤트:** `ITEM_OBTAINED`
```python
{
    "item_id": 2001,
    "item_name": "체력 포션",
    "item_type": ItemType.CONSUME,  # 소비 아이템만
    "item_grade": Grade.COMMON,
    "quantity": 1,
    "user_id": 123456
}
```

### 1.3 탐험 퀘스트 (Exploration Quest)
**목표:** 던전 탐험 또는 층 클리어

**예시:**
- "던전 탐험가" - 잊혀진 숲 10회 탐험
- "타워 도전자" - 주간 타워 5층 도달
- "깊은 곳으로" - 모든 던전 한 번씩 클리어

**이벤트:** `DUNGEON_EXPLORED`, `FLOOR_CLEARED`
```python
{
    "dungeon_id": 1,
    "dungeon_name": "잊혀진 숲",
    "floor": 5,
    "user_id": 123456
}
```

### 1.4 전투 퀘스트 (Combat Quest)
**목표:** 전투 관련 특정 조건 달성

**예시:**
- "연승 행진" - 10연승 달성
- "무상" - 체력 100% 상태로 전투 5회 승리
- "속전속결" - 3턴 이내 전투 승리 10회

**이벤트:** `COMBAT_WON`
```python
{
    "turns_taken": 3,
    "hp_remaining": 500,
    "max_hp": 500,
    "victory_count": 1,
    "user_id": 123456
}
```

### 1.5 재화 퀘스트 (Wealth Quest)
**목표:** 골드 획득

**예시:**
- "부의 축적" - 골드 10,000 획득
- "대부호" - 골드 100,000 보유

**이벤트:** `GOLD_OBTAINED`
```python
{
    "gold_amount": 500,
    "current_total": 5000,
    "user_id": 123456
}
```

### 1.6 성장 퀘스트 (Growth Quest)
**목표:** 레벨업

**예시:**
- "수련의 길" - 레벨 10 달성
- "고수의 경지" - 레벨 50 달성

**이벤트:** `LEVEL_UP`
```python
{
    "new_level": 10,
    "user_id": 123456
}
```

### 1.7 체인 퀘스트 (Chain Quest)
**목표:** 이전 퀘스트 완료 시 해금되는 연속 퀘스트

**예시:**
```
"슬라임 퇴치" (10마리)
  → "슬라임 킹 토벌" (킹 슬라임 1마리)
  → "숲의 평화" (잊혀진 숲 보스 처치)
```

**이벤트:** `QUEST_COMPLETED`
```python
{
    "quest_id": 1001,
    "quest_name": "슬라임 퇴치",
    "user_id": 123456
}
```

---

## 2. NPC 시스템

### 2.1 NPC 등장 방식

**조우 타입 (EncounterType에 추가):**
```python
class EncounterType(Enum):
    MONSTER = "monster"      # 기존
    TREASURE = "treasure"    # 기존
    NPC = "npc"              # 신규
    ELITE_MONSTER = "elite"  # 기존
```

**확률:**
- 일반 던전: 몬스터 60%, 보물 20%, NPC 15%, 엘리트 5%
- 주간 타워: NPC 없음 (순수 전투)

### 2.2 NPC 종류

#### A. 퀘스트 제공자 (Quest Giver)
- 새로운 퀘스트 제공
- 수락/거절 선택 가능
- 거절해도 나중에 다시 만날 수 있음

#### B. 퀘스트 완료 NPC (Quest Completer)
- 진행 중인 퀘스트의 목표 NPC
- 퀘스트 완료 시 보상 지급

#### C. 상인 NPC (Merchant)
- 퀘스트와 무관한 거래 NPC
- 특별한 아이템/스킬 판매 (향후 확장)

#### D. 정보 제공자 (Informant)
- 던전/몬스터 정보 제공
- 힌트 제공 (향후 확장)

### 2.3 대표 NPC 캐릭터

| NPC 이름 | 역할 | 특징 | 제공 퀘스트 |
|---------|------|------|-----------|
| 모험가 길드원 | 퀘스트 제공자 | 킬/탐험 퀘스트 | 몬스터 토벌 시리즈 |
| 떠돌이 상인 | 상인 + 퀘스트 | 아이템 거래 | 수집 퀘스트 |
| 숲의 정령 | 퀘스트 제공자 | 던전별 특화 퀘스트 | 숲 보호 시리즈 |
| 전투 교관 | 퀘스트 제공자 | 전투 조건 퀘스트 | 전투 마스터 시리즈 |
| 현자 | 정보 제공자 | 게임 메커니즘 설명 | 튜토리얼 퀘스트 |
| 수상한 행상인 | 상인 | 특별 아이템 거래 | - |

---

## 3. 보상 시스템

### 3.1 보상 종류

**기본 보상:**
- 경험치
- 골드
- 스탯 포인트

**특수 보상:**
- 특정 아이템/스킬 (퀘스트 전용)
- 칭호 (향후 확장)
- 던전 입장권 (향후 확장)

### 3.2 보상 등급

| 퀘스트 난이도 | 경험치 | 골드 | 특수 보상 |
|------------|-------|------|----------|
| 튜토리얼 | 100 | 500 | 초보자 장비 |
| 일반 | 500 | 2000 | 커먼~언커먼 |
| 어려움 | 2000 | 10000 | 레어 |
| 매우 어려움 | 5000 | 30000 | 에픽 |
| 체인 완료 | 10000 | 100000 | 유니크 |

---

## 4. 데이터베이스 스키마

### 4.1 Quest 모델
```python
class Quest(Model):
    """퀘스트 마스터 데이터"""
    id = IntField(pk=True)
    npc_id = IntField()                      # 제공 NPC
    name = CharField(max_length=100)         # 퀘스트 이름
    description = TextField()                # 설명
    quest_type = CharEnumField(QuestType)    # 타입

    # 목표 조건 (JSON)
    objective_config = JSONField()
    # 예: {"type": "kill", "monster_id": 1001, "count": 10, "dungeon_id": 1}  # 특정 던전, 특정 몬스터
    # 예: {"type": "kill", "attribute": "fire", "count": 5, "dungeon_id": 1}  # 특정 던전, 속성 기준
    # 예: {"type": "kill", "count": 10, "dungeon_id": null}  # 모든 던전에서 몬스터 N마리
    # 예: {"type": "collect", "item_id": 2001, "count": 5}  # 소비 아이템 수집
    # 예: {"type": "explore", "dungeon_id": 1, "count": 10}  # 특정 던전 탐험

    # 보상 (JSON)
    reward_config = JSONField()
    # 예: {"exp": 500, "gold": 2000, "items": [{"id": 3001, "quantity": 1}]}

    # 체인 퀘스트
    prerequisite_quest_id = IntField(null=True)  # 선행 퀘스트

    # 던전 제한
    restricted_dungeon_id = IntField(null=True)  # 특정 던전에서만 진행 가능 (null이면 전역)

    # 메타
    difficulty = CharEnumField(Difficulty)
    is_repeatable = BooleanField(default=False)
    min_level = IntField(default=1)
    max_level = IntField(null=True)
```

### 4.2 UserQuest 모델
```python
class UserQuest(Model):
    """유저 퀘스트 진행 상태"""
    id = IntField(pk=True)
    user = ForeignKeyField("models.User")
    quest = ForeignKeyField("models.Quest")

    status = CharEnumField(QuestStatus)      # pending/in_progress/completed
    progress_current = IntField(default=0)   # 현재 진행도
    progress_required = IntField()           # 목표 진행도

    accepted_at = DatetimeField(auto_now_add=True)
    completed_at = DatetimeField(null=True)

    class Meta:
        unique_together = ("user", "quest")
```

### 4.3 NPC 모델
```python
class NPC(Model):
    """NPC 마스터 데이터"""
    id = IntField(pk=True)
    name = CharField(max_length=50)
    description = TextField()
    npc_type = CharEnumField(NPCType)        # quest_giver/merchant/informant
    sprite_emoji = CharField(max_length=10)  # 이모지

    # 등장 설정
    dungeon_ids = JSONField()                # 등장 던전 [1, 2, 3]
    spawn_weight = IntField(default=100)     # 등장 가중치
```

---

## 5. 옵저버 패턴 구현

### 5.1 Game Event Bus (이벤트 버스)

```python
# service/event/event_bus.py
from typing import Callable, Dict, List
from dataclasses import dataclass
from enum import Enum

@dataclass
class GameEvent:
    """게임 이벤트"""
    type: GameEventType
    user_id: int
    data: dict
    timestamp: datetime

class EventBus:
    """이벤트 버스 (싱글톤)"""
    _instance = None
    _subscribers: Dict[GameEventType, List[Callable]] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def subscribe(self, event_type: GameEventType, callback: Callable):
        """이벤트 구독"""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(callback)

    def unsubscribe(self, event_type: GameEventType, callback: Callable):
        """구독 취소"""
        if event_type in self._subscribers:
            self._subscribers[event_type].remove(callback)

    async def publish(self, event: GameEvent):
        """이벤트 발행"""
        if event.type not in self._subscribers:
            return

        for callback in self._subscribers[event.type]:
            try:
                await callback(event)
            except Exception as e:
                logger.error(f"Event callback error: {e}", exc_info=True)
```

### 5.2 Quest Progress Tracker (퀘스트 진행 추적)

```python
# service/quest/quest_tracker.py
class QuestProgressTracker:
    """퀘스트 진행 추적 (옵저버)"""

    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self._register_listeners()

    def _register_listeners(self):
        """이벤트 리스너 등록"""
        self.event_bus.subscribe(GameEventType.MONSTER_KILLED, self.on_monster_killed)
        self.event_bus.subscribe(GameEventType.ITEM_OBTAINED, self.on_item_obtained)
        self.event_bus.subscribe(GameEventType.DUNGEON_EXPLORED, self.on_dungeon_explored)
        # ... 기타 이벤트

    async def on_monster_killed(self, event: GameEvent):
        """몬스터 처치 이벤트 핸들러"""
        user_id = event.user_id
        monster_id = event.data["monster_id"]

        # 해당 유저의 진행 중인 킬 퀘스트 조회
        active_quests = await self._get_active_kill_quests(user_id, monster_id)

        for quest in active_quests:
            await self._increment_progress(quest)

            if quest.is_completed():
                await self._notify_completion(quest)

    async def on_item_obtained(self, event: GameEvent):
        """아이템 획득 이벤트 핸들러"""
        # 수집 퀘스트 진행도 업데이트
        ...

    async def _increment_progress(self, quest: UserQuest):
        """진행도 증가"""
        quest.progress_current += 1
        await quest.save()

        # 완료 체크
        if quest.progress_current >= quest.progress_required:
            quest.status = QuestStatus.COMPLETED
            quest.completed_at = datetime.now()
            await quest.save()

            # 완료 이벤트 발행
            await self.event_bus.publish(GameEvent(
                type=GameEventType.QUEST_COMPLETED,
                user_id=quest.user_id,
                data={"quest_id": quest.quest_id}
            ))
```

### 5.3 기존 시스템에 이벤트 발행 추가

```python
# service/dungeon/combat_service.py (기존 코드 수정)
class CombatService:
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus  # 의존성 주입

    async def process_monster_death(self, user_id: int, monster: Monster):
        # 기존 로직 (보상 처리 등)
        ...

        # 이벤트 발행 추가
        await self.event_bus.publish(GameEvent(
            type=GameEventType.MONSTER_KILLED,
            user_id=user_id,
            data={
                "monster_id": monster.id,
                "monster_name": monster.name,
                "monster_attribute": monster.attribute,
                "is_boss": monster.is_boss
            }
        ))
```

**장점:**
- CombatService는 퀘스트 시스템을 전혀 모름
- 퀘스트 시스템 제거해도 CombatService 동작
- 새로운 구독자 추가 가능 (예: 업적 시스템, 통계 시스템)

---

## 6. UI/UX

### 6.1 NPC 조우
```
━━━━━━━━━━━━━━━━━━━━━━
⚔️ NPC 조우!
━━━━━━━━━━━━━━━━━━━━━━

모험가 길드원을 만났습니다.

"모험가여, 이 던전의 슬라임들이 문제를 일으키고 있소.
처치해주면 보상을 주겠소."

🎯 퀘스트: 슬라임 퇴치
━━━━━━━━━━━━━━━━━━━━━━
이 던전에서 슬라임을 10마리 처치하시오.

보상:
  💰 골드: 2,000
  ✨ 경험치: 500
  🎁 체력 포션 x3

[수락] [거절] [대화하기]
```

### 6.2 퀘스트 진행 알림
```
📋 퀘스트 진행: 슬라임 퇴치
슬라임 처치: 7 / 10
```

### 6.3 퀘스트 완료
```
━━━━━━━━━━━━━━━━━━━━━━
✅ 퀘스트 완료!
━━━━━━━━━━━━━━━━━━━━━━

🎯 슬라임 퇴치

보상을 받았습니다:
  💰 골드: +2,000
  ✨ 경험치: +500
  🎁 체력 포션 x3

모험가 길드원:
"수고했네! 자네 덕분에 던전이 안전해졌소."

[확인]
```

### 6.4 퀘스트 목록 (/퀘스트)
```
━━━━━━━━━━━━━━━━━━━━━━
📜 진행 중인 퀘스트
━━━━━━━━━━━━━━━━━━━━━━

🎯 슬라임 퇴치
  진행도: 7 / 10
  보상: 💰 2,000 | ✨ 500

🎯 던전 탐험가
  진행도: 3 / 10
  보상: 💰 5,000 | ✨ 1,000

━━━━━━━━━━━━━━━━━━━━━━
✅ 완료한 퀘스트 (클릭하여 보상 수령)
━━━━━━━━━━━━━━━━━━━━━━

✅ 약초 채집가
  보상: 💰 1,000 | ✨ 300 | 🎁 체력 포션 x5

[퀘스트 수령하기]
```

---

## 7. 구현 우선순위

### Phase 1: 기반 구축
- [ ] Event Bus 구현
- [ ] Quest, UserQuest, NPC 모델 생성
- [ ] Quest Progress Tracker 구현
- [ ] 기존 시스템에 이벤트 발행 추가

### Phase 2: 기본 퀘스트
- [ ] 킬 퀘스트 (몬스터 N마리 처치)
- [ ] 수집 퀘스트 (아이템 N개 수집)
- [ ] NPC 조우 로직 추가
- [ ] 퀘스트 수락/거절 UI

### Phase 3: 고급 퀘스트
- [ ] 탐험 퀘스트
- [ ] 전투 퀘스트 (조건부)
- [ ] 체인 퀘스트
- [ ] 퀘스트 목록 UI (/퀘스트)

### Phase 4: 확장
- [ ] 반복 퀘스트 (일일/주간)
- [ ] NPC 상점 연동
- [ ] 퀘스트 보상 다양화
- [ ] 칭호 시스템

---

## 8. 테스트 계획

### 유닛 테스트
```python
class TestEventBus:
    def test_subscribe_and_publish(self):
        """구독 후 이벤트 발행 시 콜백 호출"""

    def test_multiple_subscribers(self):
        """다수 구독자 모두 호출"""

    def test_unsubscribe(self):
        """구독 취소 후 호출 안됨"""

class TestQuestProgressTracker:
    async def test_kill_quest_progress(self):
        """몬스터 처치 시 킬 퀘스트 진행"""

    async def test_quest_completion(self):
        """목표 달성 시 완료 처리"""

    async def test_multiple_quests_progress(self):
        """여러 퀘스트 동시 진행"""
```

### 통합 테스트
```python
class TestQuestIntegration:
    async def test_full_quest_flow(self):
        """NPC 조우 → 수락 → 진행 → 완료 → 보상"""

    async def test_chain_quest_unlock(self):
        """선행 퀘스트 완료 시 다음 퀘스트 해금"""
```

---

## 9. 설정 (config.py 추가)

```python
# 퀘스트 설정
QUEST_CONFIG = {
    "npc_spawn_chance": 0.15,           # NPC 조우 확률 (15%)
    "max_active_quests": 10,            # 최대 동시 진행 퀘스트
    "quest_notification_enabled": True, # 진행 알림 활성화
}
```

---

## 10. 커플링 분석

### Before (옵저버 패턴 없음) ❌
```
CombatService ──의존──> QuestService
ItemService   ──의존──> QuestService
ExploreService──의존──> QuestService
```
**문제:**
- 모든 시스템이 QuestService를 알아야 함
- QuestService 변경 시 모든 시스템 수정 필요
- 테스트 시 QuestService 모킹 필수

### After (옵저버 패턴) ✅
```
CombatService ──발행──> EventBus <──구독── QuestProgressTracker
ItemService   ──발행──> EventBus <──구독── QuestProgressTracker
ExploreService──발행──> EventBus <──구독── QuestProgressTracker
                        EventBus <──구독── AchievementTracker (향후 추가)
                        EventBus <──구독── StatisticsTracker (향후 추가)
```
**장점:**
- 각 시스템은 EventBus만 알면 됨
- 퀘스트 시스템 추가/제거가 기존 시스템에 무영향
- 새로운 구독자 추가 용이 (업적, 통계 등)
- 테스트 시 이벤트만 발행하면 됨

---

## 11. 초기 퀘스트 목록 (Seed Data)

### 튜토리얼 퀘스트
1. **첫 발걸음** - 던전 입장 1회
2. **초보 사냥꾼** - 던전에서 몬스터 5마리 처치
3. **전투의 기본** - 전투 승리 3회

### 초급 퀘스트
4. **슬라임 퇴치** - 던전에서 슬라임 10마리 처치
5. **약초 채집가** - 체력 포션 5개 수집
6. **던전 탐험가** - 던전 10회 탐험
7. **부의 축적** - 골드 10,000 획득

### 중급 퀘스트
8. **연승 행진** - 10연승 달성
9. **속전속결** - 3턴 이내 전투 승리 5회
10. **물약 마스터** - 모든 포션 종류 각 3개씩 수집

### 고급 퀘스트
11. **보스 헌터** - 던전 보스 몬스터 5마리 처치
12. **타워 도전자** - 주간 타워 10층 달성
13. **대부호** - 골드 100,000 보유

### 체인 퀘스트: "숲의 수호자"
- **1단계:** 슬라임 10마리 처치
- **2단계:** 킹 슬라임 1마리 처치
- **3단계:** 잊혀진 숲 보스 처치
- **최종 보상:** 유니크 장비 "숲의 수호자의 반지" + 골드 50,000
