# 던전 의뢰 & 업적 시스템 기획

## 개요

게임에 **두 가지 목표 시스템**을 추가합니다:

1. **던전 의뢰 (Quest)** - 단기 목표, 던전 입장 전 선택, 던전 종료 시 자동 정산
2. **업적 (Achievement)** - 장기 목표, 자동 추적, 마일스톤 달성 시 보상

**핵심 철학:**
- 의뢰와 업적 모두 **옵저버 패턴**으로 구현 (이벤트 기반)
- 기존 시스템과 **제로 커플링**
- 플레이어의 게임 플로우를 **방해하지 않음**

---

## 시스템 1: 던전 의뢰 (Quest)

### 개념

**던전 입장 전**, 해당 던전 관련 의뢰를 **선택적으로** 받을 수 있습니다.
의뢰는 던전 탐험 중 자동으로 추적되며, **던전 종료 시 자동 정산**됩니다.

### 플로우

```
[1] 던전 선택: "잊혀진 숲"
      ↓
[2] 의뢰 게시판 표시
    ━━━━━━━━━━━━━━━━━━━━━━
    📋 잊혀진 숲 길드 의뢰
    ━━━━━━━━━━━━━━━━━━━━━━

    ⚔️ 슬라임 소탕
      목표: 슬라임 5마리 처치
      보상: 💰 1,000 | ✨ 200

    ⚔️ 보스 토벌
      목표: 보스 몬스터 1마리 처치
      보상: 💰 3,000 | ✨ 500

    🎁 포션 수집
      목표: 체력 포션 2개 획득
      보상: 💰 800 | ✨ 150

    ━━━━━━━━━━━━━━━━━━━━━━
    의뢰 선택 (최대 3개, 0개도 가능):
    [슬라임] [보스] [포션] [선택 안 함]
      ↓
[3] 던전 입장
      ↓
[4] 던전 탐험 중
    📋 활성 의뢰: 슬라임 소탕 [3/5]
      ↓
[5] 던전 종료 (클리어 또는 포기)
      ↓
[6] 자동 정산
    ━━━━━━━━━━━━━━━━━━━━━━
    ✅ 의뢰 완료!
    ━━━━━━━━━━━━━━━━━━━━━━

    ✅ 슬라임 소탕 (5/5)
       💰 +1,000 | ✨ +200

    ❌ 포션 수집 (1/2) - 미달성

    ━━━━━━━━━━━━━━━━━━━━━━
    총 보상: 💰 +1,000 | ✨ +200
```

### 의뢰 타입

#### 1. 킬 의뢰 (Kill Quest)
**목표:** 특정 몬스터 N마리 처치

**종류:**
- 특정 몬스터 (예: 슬라임 5마리)
- 속성 조건 (예: 화염 속성 몬스터 3마리)
- 보스 토벌 (예: 보스 1마리)
- 임의 몬스터 (예: 아무 몬스터 10마리)

**목표 수:** 3~10마리 (달성 가능한 수준)

#### 2. 수집 의뢰 (Collection Quest)
**목표:** 특정 아이템 N개 수집

**종류:**
- 소비 아이템 (예: 체력 포션 2개)
- 특정 등급 이상 (예: 레어 등급 아이템 1개)

**목표 수:** 1~3개

#### 3. 탐험 의뢰 (Exploration Quest)
**목표:** N회 탐험 또는 N층 도달

**종류:**
- 층 도달 (예: 5층 도달)
- 연속 전투 승리 (예: 3연승)

#### 4. 전투 조건 의뢰 (Combat Condition Quest)
**목표:** 특정 조건으로 전투 승리

**종류:**
- 무상 승리 (예: 체력 100% 상태로 전투 1회 승리)
- 속전속결 (예: 3턴 이내 전투 1회 승리)

### 의뢰 난이도

| 난이도 | 목표 난이도 | 경험치 | 골드 |
|-------|-----------|-------|------|
| 쉬움 | 달성 쉬움 (슬라임 3마리) | 100~300 | 500~1,000 |
| 보통 | 달성 보통 (보스 1마리) | 300~700 | 1,500~3,000 |
| 어려움 | 달성 어려움 (무상 승리) | 700~1,500 | 3,000~7,000 |

### 의뢰 생성 규칙

**던전별 의뢰 풀:**
각 던전마다 **5~8개의 의뢰**가 존재하고, 입장 시마다 **3~4개를 랜덤**으로 제시합니다.

**생성 조건:**
- 해당 던전에서 나오는 몬스터만 대상
- 해당 던전에서 나오는 아이템만 대상
- 달성 가능한 목표 수치

**예시 - 잊혀진 숲 의뢰 풀:**
```json
[
  {"type": "kill", "monster_id": 1001, "count": 5, "reward": {"exp": 200, "gold": 1000}},
  {"type": "kill", "attribute": "none", "count": 10, "reward": {"exp": 300, "gold": 1500}},
  {"type": "kill", "is_boss": true, "count": 1, "reward": {"exp": 500, "gold": 3000}},
  {"type": "collect", "item_id": 2001, "count": 2, "reward": {"exp": 150, "gold": 800}},
  {"type": "explore", "floor": 5, "reward": {"exp": 300, "gold": 1500}},
  {"type": "combat", "condition": "flawless", "count": 1, "reward": {"exp": 700, "gold": 3500}}
]
```

### 의뢰 제한

- **동시 진행:** 최대 3개
- **선택:** 0~3개 자유 선택
- **유효 기간:** 해당 던전 탐험 중에만 유효
- **반복:** 같은 의뢰를 다음 던전에서 다시 받을 수 있음

---

## 시스템 2: 업적 (Achievement)

### 개념

플레이어의 **장기 목표**를 자동으로 추적하고, 마일스톤 달성 시 보상을 지급합니다.
의뢰와 달리 **수락/선택 불필요**, 항상 백그라운드에서 추적됩니다.

### 플로우

```
(플레이 중 자동으로 진행)

슬라임 1마리 처치 → 업적 진행도 +1
슬라임 10마리 처치 → 🏆 업적 달성! "슬라임 헌터 I"
                       💰 +5,000 | ✨ +1,000

슬라임 100마리 처치 → 🏆 업적 달성! "슬라임 헌터 II"
                       💰 +50,000 | ✨ +10,000

/업적 명령어로 조회:
━━━━━━━━━━━━━━━━━━━━━━
🏆 업적 목록
━━━━━━━━━━━━━━━━━━━━━━

⚔️ 슬라임 헌터
├─ I: 10마리 처치 ✅ (완료)
├─ II: 100마리 처치 ✅ (완료)
└─ III: 1000마리 처치 [347/1000]

⚔️ 몬스터 사냥꾼
├─ I: 100마리 처치 [67/100]
├─ II: 1000마리 처치 [67/1000]
└─ III: 10000마리 처치 [67/10000]

🏃 던전 탐험가
├─ I: 10회 탐험 ✅
├─ II: 100회 탐험 [23/100]
└─ III: 1000회 탐험 [23/1000]

💰 부자의 길
├─ I: 10,000 골드 획득 ✅
├─ II: 100,000 골드 획득 [34,521/100,000]
└─ III: 1,000,000 골드 획득 [34,521/1,000,000]
```

### 업적 카테고리

#### 1. 전투 업적
- **몬스터 사냥꾼** - 총 몬스터 처치 수 (100/1000/10000)
- **슬라임 헌터** - 슬라임 처치 (10/100/1000)
- **보스 헌터** - 보스 처치 (10/50/100)
- **속성 마스터** - 각 속성 몬스터 처치 (화염/얼음/번개 각 100마리)

#### 2. 탐험 업적
- **던전 탐험가** - 던전 탐험 횟수 (10/100/1000)
- **타워 등반자** - 주간 타워 최고 층수 (10/20/30층)
- **깊은 곳으로** - 모든 던전 한 번씩 클리어

#### 3. 전투 마스터 업적
- **연승 행진** - 연속 승리 (10/50/100연승)
- **무상** - 체력 100% 승리 (10/50/100회)
- **속전속결** - 3턴 이내 승리 (10/50/100회)

#### 4. 수집 업적
- **수집가** - 총 아이템 수집 (100/1000/10000개)
- **포션 마스터** - 포션 사용 (50/500/5000개)

#### 5. 재화 업적
- **부자의 길** - 총 획득 골드 (10,000/100,000/1,000,000)
- **대부호** - 보유 골드 (50,000/500,000/5,000,000)

#### 6. 성장 업적
- **수련의 길** - 레벨 달성 (10/30/50/100)

### 업적 티어

각 업적은 **3단계 티어**로 구성:

| 티어 | 난이도 | 경험치 | 골드 | 칭호 |
|-----|-------|-------|------|------|
| I | 쉬움 | 1,000 | 5,000 | - |
| II | 보통 | 10,000 | 50,000 | - |
| III | 어려움 | 50,000 | 500,000 | ⭐ 칭호 획득 |

**칭호 예시:**
- "슬라임 헌터 마스터" (슬라임 1000마리)
- "타워 정복자" (타워 30층)
- "억만장자" (골드 1,000,000)

---

## 데이터베이스 스키마

### Quest 모델 (던전 의뢰)
```python
class Quest(Model):
    """의뢰 마스터 데이터"""
    id = IntField(pk=True)
    dungeon_id = IntField()                  # 해당 던전 ID
    name = CharField(max_length=100)         # 의뢰 이름
    description = TextField()                # 설명
    quest_type = CharEnumField(QuestType)    # kill/collect/explore/combat

    # 목표 조건 (JSON)
    objective_config = JSONField()
    # 예: {"type": "kill", "monster_id": 1001, "count": 5}
    # 예: {"type": "collect", "item_id": 2001, "count": 2}
    # 예: {"type": "combat", "condition": "flawless", "count": 1}

    # 보상 (JSON)
    reward_config = JSONField()
    # 예: {"exp": 200, "gold": 1000}

    # 난이도
    difficulty = CharEnumField(Difficulty)   # easy/normal/hard

    # 가중치 (랜덤 선택 시)
    spawn_weight = IntField(default=100)
```

### UserActiveQuest 모델 (진행 중인 의뢰)
```python
class UserActiveQuest(Model):
    """유저가 현재 던전에서 진행 중인 의뢰"""
    id = IntField(pk=True)
    user = ForeignKeyField("models.User")
    quest = ForeignKeyField("models.Quest")

    progress_current = IntField(default=0)   # 현재 진행도
    progress_required = IntField()           # 목표 진행도

    started_at = DatetimeField(auto_now_add=True)
    dungeon_session_id = CharField(max_length=50)  # 세션 ID (던전 종료 시 정산)

    class Meta:
        # 같은 던전 세션에서 같은 의뢰 중복 불가
        unique_together = ("user", "quest", "dungeon_session_id")
```

### Achievement 모델 (업적)
```python
class Achievement(Model):
    """업적 마스터 데이터"""
    id = IntField(pk=True)
    name = CharField(max_length=100)         # 업적 이름
    description = TextField()                # 설명
    category = CharEnumField(AchievementCategory)  # combat/exploration/collection/wealth/growth

    # 티어 (I/II/III)
    tier = IntField()                        # 1/2/3

    # 목표 조건 (JSON)
    objective_config = JSONField()
    # 예: {"type": "kill_total", "count": 100}
    # 예: {"type": "kill_monster", "monster_id": 1001, "count": 1000}
    # 예: {"type": "gold_earned", "count": 100000}

    # 보상 (JSON)
    reward_config = JSONField()
    # 예: {"exp": 1000, "gold": 5000, "title": "슬라임 헌터"}

    # 선행 업적 (티어 순서)
    prerequisite_achievement_id = IntField(null=True)
```

### UserAchievement 모델 (유저 업적 진행)
```python
class UserAchievement(Model):
    """유저 업적 진행 상태"""
    id = IntField(pk=True)
    user = ForeignKeyField("models.User")
    achievement = ForeignKeyField("models.Achievement")

    progress_current = IntField(default=0)
    progress_required = IntField()

    is_completed = BooleanField(default=False)
    completed_at = DatetimeField(null=True)
    reward_claimed = BooleanField(default=False)  # 보상 수령 여부

    class Meta:
        unique_together = ("user", "achievement")
```

---

## 옵저버 패턴 구현

### Event Bus (이벤트 버스)

```python
# service/event/event_bus.py
from typing import Callable, Dict, List
from dataclasses import dataclass
from enum import Enum
from datetime import datetime

class GameEventType(Enum):
    """게임 이벤트 타입"""
    MONSTER_KILLED = "monster_killed"
    ITEM_OBTAINED = "item_obtained"
    DUNGEON_EXPLORED = "dungeon_explored"
    FLOOR_CLEARED = "floor_cleared"
    COMBAT_WON = "combat_won"
    GOLD_OBTAINED = "gold_obtained"
    LEVEL_UP = "level_up"

@dataclass
class GameEvent:
    """게임 이벤트"""
    type: GameEventType
    user_id: int
    data: dict
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()

class EventBus:
    """이벤트 버스 (싱글톤)"""
    _instance = None
    _subscribers: Dict[GameEventType, List[Callable]] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._subscribers = {}
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

### Quest Progress Tracker (의뢰 추적기)

```python
# service/quest/quest_tracker.py
class QuestProgressTracker:
    """의뢰 진행 추적 (옵저버)"""

    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self._register_listeners()

    def _register_listeners(self):
        """이벤트 리스너 등록"""
        self.event_bus.subscribe(GameEventType.MONSTER_KILLED, self.on_monster_killed)
        self.event_bus.subscribe(GameEventType.ITEM_OBTAINED, self.on_item_obtained)
        self.event_bus.subscribe(GameEventType.COMBAT_WON, self.on_combat_won)

    async def on_monster_killed(self, event: GameEvent):
        """몬스터 처치 이벤트 핸들러"""
        user_id = event.user_id
        monster_id = event.data["monster_id"]

        # 해당 유저의 활성 킬 의뢰 조회
        active_quests = await UserActiveQuest.filter(
            user_id=user_id,
            quest__quest_type=QuestType.KILL
        ).select_related("quest")

        for user_quest in active_quests:
            if self._matches_objective(user_quest.quest, event.data):
                await self._increment_progress(user_quest)

    async def _matches_objective(self, quest: Quest, event_data: dict) -> bool:
        """목표 조건 매칭"""
        config = quest.objective_config

        if config.get("monster_id"):
            return event_data["monster_id"] == config["monster_id"]

        if config.get("attribute"):
            return event_data["monster_attribute"] == config["attribute"]

        if config.get("is_boss"):
            return event_data["is_boss"] == config["is_boss"]

        # 임의 몬스터
        return True

    async def _increment_progress(self, user_quest: UserActiveQuest):
        """진행도 증가"""
        user_quest.progress_current += 1
        await user_quest.save()
```

### Achievement Progress Tracker (업적 추적기)

```python
# service/achievement/achievement_tracker.py
class AchievementProgressTracker:
    """업적 진행 추적 (옵저버)"""

    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self._register_listeners()

    def _register_listeners(self):
        """이벤트 리스너 등록"""
        self.event_bus.subscribe(GameEventType.MONSTER_KILLED, self.on_monster_killed)
        self.event_bus.subscribe(GameEventType.GOLD_OBTAINED, self.on_gold_obtained)
        self.event_bus.subscribe(GameEventType.LEVEL_UP, self.on_level_up)

    async def on_monster_killed(self, event: GameEvent):
        """몬스터 처치 이벤트 핸들러"""
        user_id = event.user_id

        # 전투 업적 진행
        await self._update_achievement(
            user_id=user_id,
            achievement_type="kill_total",
            increment=1
        )

        # 특정 몬스터 업적
        monster_id = event.data["monster_id"]
        await self._update_achievement(
            user_id=user_id,
            achievement_type="kill_monster",
            monster_id=monster_id,
            increment=1
        )

        # 보스 업적
        if event.data.get("is_boss"):
            await self._update_achievement(
                user_id=user_id,
                achievement_type="kill_boss",
                increment=1
            )

    async def _update_achievement(self, user_id: int, achievement_type: str, increment: int = 1, **filters):
        """업적 진행도 업데이트"""
        # 해당 타입의 미완료 업적 조회
        achievements = await Achievement.filter(
            objective_config__type=achievement_type,
            **filters
        )

        for achievement in achievements:
            user_achievement, created = await UserAchievement.get_or_create(
                user_id=user_id,
                achievement=achievement,
                defaults={
                    "progress_required": achievement.objective_config["count"]
                }
            )

            if user_achievement.is_completed:
                continue

            # 진행도 증가
            user_achievement.progress_current += increment

            # 완료 체크
            if user_achievement.progress_current >= user_achievement.progress_required:
                user_achievement.is_completed = True
                user_achievement.completed_at = datetime.now()

                # 보상 지급
                await self._grant_reward(user_id, achievement)

                # 알림
                await self._notify_completion(user_id, achievement)

            await user_achievement.save()
```

### 기존 시스템에 이벤트 발행 추가

```python
# service/dungeon/combat_service.py (기존 코드 수정)
class CombatService:
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus

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
                "is_boss": monster.is_boss,
                "dungeon_id": session.dungeon_id
            }
        ))
```

---

## UI/UX

### 1. 던전 입장 전 의뢰 선택

```
/던전 명령어 → 던전 선택: "잊혀진 숲"

━━━━━━━━━━━━━━━━━━━━━━
📋 잊혀진 숲 길드 의뢰
━━━━━━━━━━━━━━━━━━━━━━

⚔️ 슬라임 소탕 [쉬움]
  목표: 슬라임 5마리 처치
  보상: 💰 1,000 | ✨ 200

⚔️ 보스 토벌 [보통]
  목표: 보스 몬스터 1마리 처치
  보상: 💰 3,000 | ✨ 500

🎁 포션 수집 [쉬움]
  목표: 체력 포션 2개 획득
  보상: 💰 800 | ✨ 150

⚡ 속전속결 [어려움]
  목표: 3턴 이내 전투 승리 1회
  보상: 💰 5,000 | ✨ 1,000

━━━━━━━━━━━━━━━━━━━━━━
의뢰 선택 (최대 3개):

[슬라임 소탕] [보스 토벌] [포션 수집] [속전속결]
[선택 안 함]

선택된 의뢰:
✅ 슬라임 소탕
✅ 보스 토벌

[던전 입장]
```

### 2. 던전 중 진행도 표시

```
━━━━━━━━━━━━━━━━━━━━━━
⚔️ 몬스터 조우!
━━━━━━━━━━━━━━━━━━━━━━

슬라임이 나타났다!

[전투] [도망]

━━━━━━━━━━━━━━━━━━━━━━
(전투 승리 후)

✅ 슬라임을 처치했다!

📋 의뢰 진행:
  슬라임 소탕: 4 → 5 / 5 ✅ 완료!
```

### 3. 던전 종료 시 정산

```
━━━━━━━━━━━━━━━━━━━━━━
✅ 던전 클리어!
━━━━━━━━━━━━━━━━━━━━━━

기본 보상:
  💰 골드: +3,000
  ✨ 경험치: +1,500
  🎁 아이템: 체력 포션 x2

━━━━━━━━━━━━━━━━━━━━━━
📋 의뢰 정산
━━━━━━━━━━━━━━━━━━━━━━

✅ 슬라임 소탕 (5/5)
   💰 +1,000 | ✨ +200

✅ 보스 토벌 (1/1)
   💰 +3,000 | ✨ +500

━━━━━━━━━━━━━━━━━━━━━━
총 보상:
  💰 골드: +7,000
  ✨ 경험치: +2,200
```

### 4. 업적 달성 알림

```
(몬스터 처치 중)

━━━━━━━━━━━━━━━━━━━━━━
🏆 업적 달성!
━━━━━━━━━━━━━━━━━━━━━━

⚔️ 슬라임 헌터 I
슬라임 10마리 처치

보상:
  💰 골드: +5,000
  ✨ 경험치: +1,000

[확인]
```

### 5. 업적 목록 (/업적)

```
/업적

━━━━━━━━━━━━━━━━━━━━━━
🏆 업적 목록
━━━━━━━━━━━━━━━━━━━━━━

📁 전투 업적

  ⚔️ 몬스터 사냥꾼
  ├─ I: 100마리 처치 [67/100]
  ├─ II: 1,000마리 처치 [67/1000] 🔒
  └─ III: 10,000마리 처치 [67/10000] 🔒

  ⚔️ 슬라임 헌터
  ├─ I: 10마리 처치 ✅ (2024-01-15)
  ├─ II: 100마리 처치 ✅ (2024-02-03)
  └─ III: 1,000마리 처치 [347/1000]

  ⚔️ 보스 헌터
  ├─ I: 10마리 처치 [3/10]
  ├─ II: 50마리 처치 [3/50] 🔒
  └─ III: 100마리 처치 [3/100] 🔒

📁 탐험 업적

  🏃 던전 탐험가
  ├─ I: 10회 탐험 ✅
  ├─ II: 100회 탐험 [23/100]
  └─ III: 1,000회 탐험 [23/1000] 🔒

📁 재화 업적

  💰 부자의 길
  ├─ I: 10,000 골드 획득 ✅
  ├─ II: 100,000 골드 획득 [34,521/100,000]
  └─ III: 1,000,000 골드 획득 [34,521/1,000,000] 🔒

━━━━━━━━━━━━━━━━━━━━━━
페이지: 1 / 3

[◀ 이전] [다음 ▶]
```

---

## 구현 우선순위

### Phase 1: 이벤트 시스템 구축
- [ ] EventBus 구현
- [ ] GameEventType 정의
- [ ] 기존 시스템에 이벤트 발행 추가
  - [ ] CombatService: MONSTER_KILLED
  - [ ] ItemService: ITEM_OBTAINED
  - [ ] ExploreService: DUNGEON_EXPLORED
  - [ ] RewardService: GOLD_OBTAINED
  - [ ] UserService: LEVEL_UP

### Phase 2: 던전 의뢰 시스템
- [ ] Quest, UserActiveQuest 모델 생성
- [ ] QuestProgressTracker 구현
- [ ] 던전 입장 전 의뢰 선택 UI
- [ ] 던전 중 진행도 표시
- [ ] 던전 종료 시 자동 정산
- [ ] 의뢰 데이터 시딩 (각 던전별 5~8개)

### Phase 3: 업적 시스템
- [ ] Achievement, UserAchievement 모델 생성
- [ ] AchievementProgressTracker 구현
- [ ] 업적 달성 알림
- [ ] /업적 명령어 UI
- [ ] 업적 데이터 시딩 (30~50개)

### Phase 4: 칭호 시스템 (향후)
- [ ] 업적 III 달성 시 칭호 획득
- [ ] 칭호 장착 시스템
- [ ] /칭호 명령어

---

## 테스트 계획

### 유닛 테스트

```python
class TestEventBus:
    def test_subscribe_and_publish(self):
        """구독 후 이벤트 발행 시 콜백 호출"""

    def test_multiple_subscribers(self):
        """다수 구독자 모두 호출"""

class TestQuestProgressTracker:
    async def test_kill_quest_progress(self):
        """몬스터 처치 시 킬 의뢰 진행"""

    async def test_quest_completion(self):
        """목표 달성 시 완료 처리"""

class TestAchievementProgressTracker:
    async def test_achievement_progress(self):
        """이벤트 발생 시 업적 진행"""

    async def test_achievement_tier_unlock(self):
        """티어 I 완료 시 티어 II 해금"""
```

### 통합 테스트

```python
class TestQuestIntegration:
    async def test_full_quest_flow(self):
        """의뢰 선택 → 진행 → 완료 → 정산"""

    async def test_multiple_quests_progress(self):
        """여러 의뢰 동시 진행"""

class TestAchievementIntegration:
    async def test_achievement_unlock_chain(self):
        """티어 순차 해금"""
```

---

## 설정 (config.py 추가)

```python
# 의뢰 설정
QUEST_CONFIG = {
    "max_active_quests": 3,              # 최대 동시 진행 의뢰
    "quest_pool_size": (3, 4),           # 제시 의뢰 개수 (최소, 최대)
    "notification_enabled": True,        # 진행 알림 활성화
}

# 업적 설정
ACHIEVEMENT_CONFIG = {
    "notification_enabled": True,        # 달성 알림 활성화
    "auto_claim_reward": True,           # 자동 보상 수령
}
```

---

## 초기 데이터 (Seed Data)

### 던전 의뢰 예시

**잊혀진 숲 의뢰 풀:**
1. 슬라임 소탕 (쉬움) - 슬라임 5마리
2. 화염 토벌 (보통) - 화염 몬스터 3마리
3. 보스 토벌 (보통) - 보스 1마리
4. 포션 수집 (쉬움) - 체력 포션 2개
5. 층 도달 (쉬움) - 5층 도달
6. 무상 승리 (어려움) - 체력 100% 승리 1회
7. 속전속결 (어려움) - 3턴 이내 승리 1회
8. 연속 승리 (보통) - 5연승

### 업적 예시

**전투 업적:**
- 몬스터 사냥꾼 I/II/III (100/1000/10000)
- 슬라임 헌터 I/II/III (10/100/1000)
- 보스 헌터 I/II/III (10/50/100)

**탐험 업적:**
- 던전 탐험가 I/II/III (10/100/1000)
- 타워 등반자 I/II/III (10층/20층/30층)

**전투 마스터 업적:**
- 연승 행진 I/II/III (10/50/100연승)
- 무상 I/II/III (10/50/100회)
- 속전속결 I/II/III (10/50/100회)

**재화 업적:**
- 부자의 길 I/II/III (10,000/100,000/1,000,000 획득)
- 대부호 I/II/III (50,000/500,000/5,000,000 보유)

**성장 업적:**
- 수련의 길 I/II/III/IV (Lv 10/30/50/100)
