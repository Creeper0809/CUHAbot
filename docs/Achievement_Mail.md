# 업적 & 우편 시스템 기획

## 개요

게임에 **업적 시스템**과 **우편 시스템**을 추가합니다.

- **업적 (Achievement)**: 장기 목표를 자동으로 추적하고, 달성 시 우편으로 보상 발송
- **우편 (Mail)**: 업적 보상, 시스템 메시지, 이벤트 보상 등을 수령하는 우편함

**핵심 철학:**
- **옵저버 패턴**으로 이벤트 기반 구현 (제로 커플링)
- 업적은 백그라운드에서 **자동 추적** (플레이어 개입 불필요)
- 보상은 **우편으로 발송** (플레이어가 선택적으로 수령)

---

## 시스템 1: 업적 (Achievement)

### 개념

플레이어의 **장기 목표**를 자동으로 추적합니다.
달성 시 알림과 함께 **우편으로 보상이 발송**됩니다.

### 플로우

```
(플레이 중 자동으로 진행)

슬라임 1마리 처치 → 업적 진행도 +1
슬라임 10마리 처치 → 🏆 업적 달성!

━━━━━━━━━━━━━━━━━━━━━━
🏆 업적 달성!
━━━━━━━━━━━━━━━━━━━━━━

⚔️ 슬라임 헌터 I
슬라임 10마리 처치 달성!

보상이 우편으로 발송되었습니다.
/우편 명령어로 확인하세요.

[확인]
━━━━━━━━━━━━━━━━━━━━━━

/우편 → 보상 수령
```

### 업적 카테고리

#### 1. 전투 업적 (Combat)
| 업적 이름 | I | II | III | 보상 (I/II/III) |
|----------|---|----|----|----------------|
| 몬스터 사냥꾼 | 100마리 | 1,000마리 | 10,000마리 | 골드 5k/50k/500k |
| 슬라임 헌터 | 10마리 | 100마리 | 1,000마리 | 골드 5k/50k/500k |
| 보스 헌터 | 10마리 | 50마리 | 100마리 | 골드 10k/100k/1000k |
| 속성 마스터 (화염) | 100마리 | 500마리 | 2,000마리 | 골드 5k/50k/500k |
| 속성 마스터 (얼음) | 100마리 | 500마리 | 2,000마리 | 골드 5k/50k/500k |
| 속성 마스터 (번개) | 100마리 | 500마리 | 2,000마리 | 골드 5k/50k/500k |
| 속성 마스터 (물) | 100마리 | 500마리 | 2,000마리 | 골드 5k/50k/500k |
| 속성 마스터 (신성) | 100마리 | 500마리 | 2,000마리 | 골드 5k/50k/500k |
| 속성 마스터 (어둠) | 100마리 | 500마리 | 2,000마리 | 골드 5k/50k/500k |

#### 2. 탐험 업적 (Exploration)
| 업적 이름 | I | II | III | 보상 (I/II/III) |
|----------|---|----|----|----------------|
| 던전 탐험가 | 10회 | 100회 | 1,000회 | 골드 3k/30k/300k |
| 타워 등반자 | 10층 | 20층 | 30층 | 골드 10k/100k/1000k |
| 깊은 곳으로 | 모든 던전 1회 | - | - | 골드 50k |

#### 3. 전투 마스터 업적 (Combat Mastery)
| 업적 이름 | I | II | III | 보상 (I/II/III) |
|----------|---|----|----|----------------|
| 연승 행진 | 10연승 | 50연승 | 100연승 | 골드 5k/50k/500k |
| 무상 | 10회 | 50회 | 100회 | 골드 7k/70k/700k |
| 속전속결 | 10회 | 50회 | 100회 | 골드 7k/70k/700k |

#### 4. 수집 업적 (Collection)
| 업적 이름 | I | II | III | 보상 (I/II/III) |
|----------|---|----|----|----------------|
| 수집가 | 100개 | 1,000개 | 10,000개 | 골드 5k/50k/500k |
| 포션 마스터 | 50개 사용 | 500개 사용 | 5,000개 사용 | 골드 5k/50k/500k |

#### 5. 재화 업적 (Wealth)
| 업적 이름 | I | II | III | 보상 (I/II/III) |
|----------|---|----|----|----------------|
| 부자의 길 | 10,000 획득 | 100,000 획득 | 1,000,000 획득 | 골드 5k/50k/500k |
| 대부호 | 50,000 보유 | 500,000 보유 | 5,000,000 보유 | 골드 10k/100k/1000k |

#### 6. 성장 업적 (Growth)
| 업적 이름 | I | II | III | IV |
|----------|---|----|----|---|
| 수련의 길 | Lv 10 | Lv 30 | Lv 50 | Lv 100 |
| 보상 | 골드 5k | 골드 50k | 골드 500k | 골드 5000k |

### 업적 티어 및 칭호

**티어 III 달성 시 칭호 획득:**
- "슬라임 헌터 마스터" 🏆
- "타워 정복자" 🏆
- "억만장자" 🏆
- "전투의 신" 🏆
- etc.

**칭호 효과 (향후 확장):**
- 스탯 보너스
- 특수 효과
- 장착 시 표시

---

## 시스템 2: 우편 (Mail)

### 개념

게임 내 **비동기 보상 및 메시지 전달** 시스템입니다.
업적 보상, 시스템 메시지, 이벤트 보상 등을 우편으로 수령합니다.

### 플로우

```
업적 달성 → 우편 발송 → /우편 → 확인 → 보상 수령

━━━━━━━━━━━━━━━━━━━━━━
📬 우편함 (3건)
━━━━━━━━━━━━━━━━━━━━━━

📩 새 우편: 업적 보상
  제목: 🏆 업적 달성: 슬라임 헌터 I
  발신: 시스템
  날짜: 2024-02-09
  [읽기]

📩 새 우편: 업적 보상
  제목: 🏆 업적 달성: 던전 탐험가 I
  발신: 시스템
  날짜: 2024-02-08
  [읽기]

📭 읽은 우편: 시스템 공지
  제목: 업데이트 안내
  발신: 운영팀
  날짜: 2024-02-07
  [다시 읽기]

━━━━━━━━━━━━━━━━━━━━━━
[모두 수령] [삭제]

(우편 읽기)

━━━━━━━━━━━━━━━━━━━━━━
📩 우편
━━━━━━━━━━━━━━━━━━━━━━

제목: 🏆 업적 달성: 슬라임 헌터 I
발신: 시스템
날짜: 2024-02-09 15:30

축하합니다! 업적을 달성하셨습니다.

⚔️ 슬라임 헌터 I
슬라임 10마리 처치 달성!

첨부된 보상:
  💰 골드: 5,000
  ✨ 경험치: 1,000

━━━━━━━━━━━━━━━━━━━━━━
[보상 수령] [삭제]
```

### 우편 타입

#### 1. 업적 보상 우편
- 발신: "시스템"
- 제목: "🏆 업적 달성: {업적 이름}"
- 내용: 업적 설명 + 보상 목록
- 첨부: 골드, 경험치, 아이템 등

#### 2. 시스템 메시지 우편
- 발신: "운영팀"
- 제목: 공지/안내 제목
- 내용: 공지 내용
- 첨부: 없음 또는 보상

#### 3. 이벤트 보상 우편 (향후)
- 발신: "이벤트"
- 제목: "🎉 이벤트 보상"
- 내용: 이벤트 참여 감사 메시지
- 첨부: 이벤트 보상

#### 4. 관리자 발송 우편 (향후)
- 발신: "운영팀"
- 제목: 관리자가 설정
- 내용: 관리자가 작성
- 첨부: 보상 (버그 보상, 보상 등)

### 우편 제한

- **보관 기간**: 30일 (이후 자동 삭제)
- **최대 보관**: 100건 (초과 시 오래된 것부터 자동 삭제)
- **보상 수령 기한**: 30일 (이후 소멸)

---

## 데이터베이스 스키마

### Achievement 모델
```python
class Achievement(Model):
    """업적 마스터 데이터"""
    id = IntField(pk=True)
    name = CharField(max_length=100)             # 업적 이름
    description = TextField()                    # 설명
    category = CharEnumField(AchievementCategory)  # combat/exploration/collection/wealth/growth

    # 티어 (I/II/III)
    tier = IntField()                            # 1/2/3

    # 목표 조건 (JSON)
    objective_config = JSONField()
    # 예: {"type": "kill_total", "count": 100}
    # 예: {"type": "kill_monster", "monster_id": 1001, "count": 1000}
    # 예: {"type": "kill_attribute", "attribute": "fire", "count": 100}
    # 예: {"type": "kill_boss", "count": 10}
    # 예: {"type": "dungeon_explore", "count": 10}
    # 예: {"type": "gold_earned", "count": 100000}
    # 예: {"type": "gold_owned", "count": 50000}
    # 예: {"type": "level", "level": 10}
    # 예: {"type": "win_streak", "count": 10}
    # 예: {"type": "win_flawless", "count": 10}
    # 예: {"type": "win_fast", "turns": 3, "count": 10}

    # 보상 (JSON)
    reward_config = JSONField()
    # 예: {"exp": 1000, "gold": 5000, "title": "슬라임 헌터"}

    # 선행 업적 (티어 순서)
    prerequisite_achievement_id = IntField(null=True)

    # 칭호 (티어 III만)
    title_name = CharField(max_length=50, null=True)  # "슬라임 헌터 마스터"

    class Meta:
        table = "achievement"
```

### UserAchievement 모델
```python
class UserAchievement(Model):
    """유저 업적 진행 상태"""
    id = IntField(pk=True)
    user = ForeignKeyField("models.User", related_name="achievements")
    achievement = ForeignKeyField("models.Achievement")

    progress_current = IntField(default=0)       # 현재 진행도
    progress_required = IntField()               # 목표 진행도

    is_completed = BooleanField(default=False)   # 완료 여부
    completed_at = DatetimeField(null=True)      # 완료 시각

    class Meta:
        table = "user_achievement"
        unique_together = ("user", "achievement")
```

### Mail 모델
```python
class Mail(Model):
    """우편"""
    id = IntField(pk=True)
    user = ForeignKeyField("models.User", related_name="mails")

    # 우편 정보
    mail_type = CharEnumField(MailType)          # achievement/system/event/admin
    sender = CharField(max_length=50)            # "시스템", "운영팀" 등
    title = CharField(max_length=200)            # 제목
    content = TextField()                        # 내용

    # 첨부 보상 (JSON)
    reward_config = JSONField(null=True)
    # 예: {"exp": 1000, "gold": 5000, "items": [{"id": 3001, "quantity": 1}]}

    # 상태
    is_read = BooleanField(default=False)        # 읽음 여부
    is_claimed = BooleanField(default=False)     # 보상 수령 여부

    # 시간
    created_at = DatetimeField(auto_now_add=True)  # 발송 시각
    expires_at = DatetimeField()                 # 만료 시각 (created_at + 30일)

    class Meta:
        table = "mail"
        indexes = (
            (("user", "is_read"), False),        # 미읽음 조회 최적화
            (("user", "created_at"), False),     # 최신순 조회 최적화
        )
```

---

## 옵저버 패턴 구현

### Event Bus

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
    COMBAT_WON = "combat_won"
    GOLD_OBTAINED = "gold_obtained"
    GOLD_CHANGED = "gold_changed"           # 보유 골드 변경
    LEVEL_UP = "level_up"
    ITEM_USED = "item_used"
    WIN_STREAK_UPDATED = "win_streak"       # 연승 갱신

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

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._subscribers = {}
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

### Achievement Progress Tracker

```python
# service/achievement/achievement_tracker.py
class AchievementProgressTracker:
    """업적 진행 추적 (옵저버)"""

    def __init__(self, event_bus: EventBus, mail_service: MailService):
        self.event_bus = event_bus
        self.mail_service = mail_service
        self._register_listeners()

    def _register_listeners(self):
        """이벤트 리스너 등록"""
        self.event_bus.subscribe(GameEventType.MONSTER_KILLED, self.on_monster_killed)
        self.event_bus.subscribe(GameEventType.DUNGEON_EXPLORED, self.on_dungeon_explored)
        self.event_bus.subscribe(GameEventType.GOLD_OBTAINED, self.on_gold_obtained)
        self.event_bus.subscribe(GameEventType.GOLD_CHANGED, self.on_gold_changed)
        self.event_bus.subscribe(GameEventType.LEVEL_UP, self.on_level_up)
        self.event_bus.subscribe(GameEventType.COMBAT_WON, self.on_combat_won)
        self.event_bus.subscribe(GameEventType.ITEM_USED, self.on_item_used)

    async def on_monster_killed(self, event: GameEvent):
        """몬스터 처치 이벤트 핸들러"""
        user_id = event.user_id
        monster_id = event.data["monster_id"]
        attribute = event.data.get("monster_attribute")
        is_boss = event.data.get("is_boss", False)

        # 전체 몬스터 처치
        await self._update_achievement(
            user_id=user_id,
            achievement_type="kill_total",
            increment=1
        )

        # 특정 몬스터 처치
        await self._update_achievement(
            user_id=user_id,
            achievement_type="kill_monster",
            monster_id=monster_id,
            increment=1
        )

        # 속성별 처치
        if attribute:
            await self._update_achievement(
                user_id=user_id,
                achievement_type="kill_attribute",
                attribute=attribute,
                increment=1
            )

        # 보스 처치
        if is_boss:
            await self._update_achievement(
                user_id=user_id,
                achievement_type="kill_boss",
                increment=1
            )

    async def _update_achievement(
        self,
        user_id: int,
        achievement_type: str,
        increment: int = 1,
        **filters
    ):
        """업적 진행도 업데이트"""
        # 해당 타입의 미완료 업적 조회
        query = Achievement.filter(objective_config__type=achievement_type)

        # 추가 필터 (monster_id, attribute 등)
        for key, value in filters.items():
            query = query.filter(**{f"objective_config__{key}": value})

        achievements = await query.all()

        for achievement in achievements:
            # 선행 업적 확인 (티어 II/III는 이전 티어 완료 필요)
            if achievement.prerequisite_achievement_id:
                prerequisite = await UserAchievement.get_or_none(
                    user_id=user_id,
                    achievement_id=achievement.prerequisite_achievement_id,
                    is_completed=True
                )
                if not prerequisite:
                    continue  # 선행 업적 미완료

            # 유저 업적 조회 또는 생성
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

                # 우편 발송
                await self._send_achievement_mail(user_id, achievement)

            await user_achievement.save()

    async def _send_achievement_mail(self, user_id: int, achievement: Achievement):
        """업적 달성 시 우편 발송"""
        title = f"🏆 업적 달성: {achievement.name}"
        content = f"""축하합니다! 업적을 달성하셨습니다.

⚔️ {achievement.name}
{achievement.description}

보상을 수령해주세요!"""

        await self.mail_service.send_mail(
            user_id=user_id,
            mail_type=MailType.ACHIEVEMENT,
            sender="시스템",
            title=title,
            content=content,
            reward_config=achievement.reward_config
        )

        # 인게임 알림 (현재 세션이 있다면)
        await self._notify_achievement_completion(user_id, achievement)
```

### Mail Service

```python
# service/mail/mail_service.py
class MailService:
    """우편 서비스"""

    async def send_mail(
        self,
        user_id: int,
        mail_type: MailType,
        sender: str,
        title: str,
        content: str,
        reward_config: dict = None
    ) -> Mail:
        """우편 발송"""
        expires_at = datetime.now() + timedelta(days=30)

        mail = await Mail.create(
            user_id=user_id,
            mail_type=mail_type,
            sender=sender,
            title=title,
            content=content,
            reward_config=reward_config,
            expires_at=expires_at
        )

        return mail

    async def get_user_mails(
        self,
        user_id: int,
        unread_only: bool = False,
        limit: int = 50,
        offset: int = 0
    ) -> List[Mail]:
        """유저 우편 목록 조회"""
        query = Mail.filter(user_id=user_id)

        if unread_only:
            query = query.filter(is_read=False)

        mails = await query.order_by("-created_at").offset(offset).limit(limit).all()
        return mails

    async def read_mail(self, mail_id: int, user_id: int) -> Mail:
        """우편 읽기"""
        mail = await Mail.get_or_none(id=mail_id, user_id=user_id)

        if not mail:
            raise MailNotFoundError(mail_id)

        if not mail.is_read:
            mail.is_read = True
            await mail.save()

        return mail

    async def claim_reward(self, mail_id: int, user_id: int):
        """우편 보상 수령"""
        mail = await Mail.get_or_none(id=mail_id, user_id=user_id)

        if not mail:
            raise MailNotFoundError(mail_id)

        if mail.is_claimed:
            raise AlreadyClaimedError("이미 수령한 보상입니다")

        if not mail.reward_config:
            raise NoRewardError("첨부된 보상이 없습니다")

        # 만료 체크
        if datetime.now() > mail.expires_at:
            raise ExpiredMailError("만료된 우편입니다")

        # 보상 지급
        reward = mail.reward_config
        user = await User.get(id=user_id)

        if "exp" in reward:
            # 경험치 지급 로직
            pass

        if "gold" in reward:
            user.gold += reward["gold"]

        if "items" in reward:
            # 아이템 지급 로직
            pass

        await user.save()

        # 수령 완료 처리
        mail.is_claimed = True
        await mail.save()

        return reward

    async def delete_mail(self, mail_id: int, user_id: int):
        """우편 삭제"""
        mail = await Mail.get_or_none(id=mail_id, user_id=user_id)

        if not mail:
            raise MailNotFoundError(mail_id)

        if mail.reward_config and not mail.is_claimed:
            raise CannotDeleteError("보상을 먼저 수령해주세요")

        await mail.delete()

    async def claim_all_rewards(self, user_id: int):
        """모든 우편 보상 일괄 수령"""
        mails = await Mail.filter(
            user_id=user_id,
            is_claimed=False,
            reward_config__isnull=False
        ).all()

        total_reward = {"exp": 0, "gold": 0, "items": []}

        for mail in mails:
            if datetime.now() > mail.expires_at:
                continue

            reward = mail.reward_config
            total_reward["exp"] += reward.get("exp", 0)
            total_reward["gold"] += reward.get("gold", 0)
            total_reward["items"].extend(reward.get("items", []))

            mail.is_claimed = True
            await mail.save()

        # 일괄 지급
        if total_reward["exp"] > 0 or total_reward["gold"] > 0:
            user = await User.get(id=user_id)
            # 경험치 지급
            user.gold += total_reward["gold"]
            await user.save()

        return total_reward

    async def cleanup_expired_mails(self):
        """만료된 우편 자동 삭제 (크론잡)"""
        now = datetime.now()
        deleted = await Mail.filter(expires_at__lt=now).delete()
        logger.info(f"Deleted {deleted} expired mails")
```

### 기존 시스템에 이벤트 발행 추가

```python
# service/dungeon/combat_service.py
class CombatService:
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus

    async def process_monster_death(self, user_id: int, monster: Monster, session: DungeonSession):
        # 기존 로직
        ...

        # 이벤트 발행
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

    async def process_combat_victory(self, user_id: int, session: DungeonSession):
        # 기존 로직
        ...

        # 연승 카운터 업데이트
        user = await User.get(id=user_id)
        user.win_streak += 1

        # 무상 승리 체크
        is_flawless = session.user_current_hp == session.user_max_hp

        # 속전속결 체크
        is_fast = session.turn_count <= 3

        await self.event_bus.publish(GameEvent(
            type=GameEventType.COMBAT_WON,
            user_id=user_id,
            data={
                "is_flawless": is_flawless,
                "is_fast": is_fast,
                "turns": session.turn_count,
                "win_streak": user.win_streak
            }
        ))

        await self.event_bus.publish(GameEvent(
            type=GameEventType.WIN_STREAK_UPDATED,
            user_id=user_id,
            data={"win_streak": user.win_streak}
        ))
```

---

## UI/UX

### 1. 업적 달성 알림

```
(몬스터 처치 중)

━━━━━━━━━━━━━━━━━━━━━━
🏆 업적 달성!
━━━━━━━━━━━━━━━━━━━━━━

⚔️ 슬라임 헌터 I
슬라임 10마리 처치 달성!

보상이 우편으로 발송되었습니다.
/우편 명령어로 확인하세요.

[확인]
```

### 2. 업적 목록 (/업적)

```
/업적

━━━━━━━━━━━━━━━━━━━━━━
🏆 업적 목록
━━━━━━━━━━━━━━━━━━━━━━

📁 전투 업적

  ⚔️ 몬스터 사냥꾼
  ├─ I: 100마리 처치 [67/100]
  ├─ II: 1,000마리 처치 🔒 (I 완료 필요)
  └─ III: 10,000마리 처치 🔒 (II 완료 필요)

  ⚔️ 슬라임 헌터
  ├─ I: 10마리 처치 ✅ (2024-01-15)
  ├─ II: 100마리 처치 ✅ (2024-02-03)
  └─ III: 1,000마리 처치 [347/1000]
      보상: 💰 500,000 | 🏆 칭호 "슬라임 헌터 마스터"

  ⚔️ 보스 헌터
  ├─ I: 10마리 처치 [3/10]
  ├─ II: 50마리 처치 🔒
  └─ III: 100마리 처치 🔒

📁 탐험 업적

  🏃 던전 탐험가
  ├─ I: 10회 탐험 ✅
  ├─ II: 100회 탐험 [23/100]
  └─ III: 1,000회 탐험 🔒

📁 재화 업적

  💰 부자의 길 (총 획득 골드)
  ├─ I: 10,000 골드 획득 ✅
  ├─ II: 100,000 골드 획득 [34,521/100,000]
  └─ III: 1,000,000 골드 획득 🔒

  💎 대부호 (현재 보유 골드)
  ├─ I: 50,000 골드 보유 [12,345/50,000]
  ├─ II: 500,000 골드 보유 🔒
  └─ III: 5,000,000 골드 보유 🔒

━━━━━━━━━━━━━━━━━━━━━━
진행 중: 15개 | 완료: 8개 | 전체: 45개
페이지: 1 / 3

[◀ 이전] [다음 ▶] [카테고리 필터]
```

### 3. 우편함 (/우편)

```
/우편

━━━━━━━━━━━━━━━━━━━━━━
📬 우편함 (5건)
━━━━━━━━━━━━━━━━━━━━━━

📩 새 우편: 업적 보상
  제목: 🏆 업적 달성: 슬라임 헌터 II
  발신: 시스템
  날짜: 2024-02-09 15:30
  보상: 💰 50,000 | ✨ 10,000
  [읽기]

📩 새 우편: 업적 보상
  제목: 🏆 업적 달성: 던전 탐험가 I
  발신: 시스템
  날짜: 2024-02-08 10:15
  보상: 💰 3,000 | ✨ 1,000
  [읽기]

📭 읽은 우편: 시스템 공지
  제목: 업데이트 안내
  발신: 운영팀
  날짜: 2024-02-07 14:00
  [다시 읽기] [삭제]

📭 읽은 우편: 업적 보상 (수령 완료)
  제목: 🏆 업적 달성: 슬라임 헌터 I
  발신: 시스템
  날짜: 2024-02-01 09:20
  [다시 읽기] [삭제]

━━━━━━━━━━━━━━━━━━━━━━
[모두 수령] [읽은 우편 삭제]
```

### 4. 우편 읽기

```
(우편 선택)

━━━━━━━━━━━━━━━━━━━━━━
📩 우편
━━━━━━━━━━━━━━━━━━━━━━

제목: 🏆 업적 달성: 슬라임 헌터 II
발신: 시스템
날짜: 2024-02-09 15:30
만료: 2024-03-11 15:30 (30일 후)

━━━━━━━━━━━━━━━━━━━━━━

축하합니다! 업적을 달성하셨습니다.

⚔️ 슬라임 헌터 II
슬라임 100마리 처치 달성!

보상을 수령해주세요!

━━━━━━━━━━━━━━━━━━━━━━
첨부된 보상:
  💰 골드: 50,000
  ✨ 경험치: 10,000

━━━━━━━━━━━━━━━━━━━━━━
[보상 수령] [삭제] [돌아가기]
```

### 5. 보상 수령

```
(보상 수령 버튼 클릭)

━━━━━━━━━━━━━━━━━━━━━━
✅ 보상 수령 완료!
━━━━━━━━━━━━━━━━━━━━━━

받은 보상:
  💰 골드: +50,000
  ✨ 경험치: +10,000

현재 보유:
  💰 골드: 123,456
  Lv 15 (경험치 3,450 / 5,000)

[확인]
```

---

## 구현 우선순위

### Phase 1: 이벤트 시스템 구축
- [ ] EventBus 구현
- [ ] GameEventType 정의
- [ ] 기존 시스템에 이벤트 발행 추가
  - [ ] CombatService: MONSTER_KILLED, COMBAT_WON
  - [ ] ItemService: ITEM_OBTAINED, ITEM_USED
  - [ ] ExploreService: DUNGEON_EXPLORED
  - [ ] RewardService: GOLD_OBTAINED
  - [ ] UserService: LEVEL_UP, GOLD_CHANGED

### Phase 2: 우편 시스템
- [ ] Mail 모델 생성
- [ ] MailService 구현
- [ ] /우편 명령어 UI
- [ ] 우편 읽기/보상 수령/삭제 기능
- [ ] 만료 우편 자동 삭제 크론잡

### Phase 3: 업적 시스템
- [ ] Achievement, UserAchievement 모델 생성
- [ ] AchievementProgressTracker 구현
- [ ] 업적 달성 시 우편 발송
- [ ] /업적 명령어 UI
- [ ] 업적 데이터 시딩 (40~50개)

### Phase 4: 칭호 시스템 (향후)
- [ ] 업적 III 달성 시 칭호 획득
- [ ] 칭호 장착 시스템
- [ ] /칭호 명령어
- [ ] 칭호 효과 (스탯 보너스)

---

## 테스트 계획

### 유닛 테스트

```python
class TestEventBus:
    def test_subscribe_and_publish(self):
        """구독 후 이벤트 발행 시 콜백 호출"""

    def test_multiple_subscribers(self):
        """다수 구독자 모두 호출"""

class TestAchievementProgressTracker:
    async def test_achievement_progress(self):
        """이벤트 발생 시 업적 진행"""

    async def test_achievement_completion_mail(self):
        """업적 완료 시 우편 발송"""

    async def test_achievement_tier_unlock(self):
        """티어 I 완료 시 티어 II 해금"""

class TestMailService:
    async def test_send_mail(self):
        """우편 발송"""

    async def test_claim_reward(self):
        """보상 수령"""

    async def test_expired_mail_cleanup(self):
        """만료 우편 삭제"""
```

### 통합 테스트

```python
class TestAchievementIntegration:
    async def test_full_achievement_flow(self):
        """업적 진행 → 완료 → 우편 발송 → 보상 수령"""

    async def test_achievement_tier_chain(self):
        """티어 순차 해금 및 보상 수령"""
```

---

## 설정 (config.py 추가)

```python
# 업적 설정
ACHIEVEMENT_CONFIG = {
    "notification_enabled": True,        # 달성 알림 활성화
}

# 우편 설정
MAIL_CONFIG = {
    "expire_days": 30,                   # 우편 보관 기간 (일)
    "max_mails": 100,                    # 최대 우편 보관 개수
    "auto_delete_expired": True,         # 만료 우편 자동 삭제
}
```

---

## 초기 데이터 (Seed Data)

### 업적 예시 (40~50개)

**전투 업적 (15개):**
- 몬스터 사냥꾼 I/II/III
- 슬라임 헌터 I/II/III
- 보스 헌터 I/II/III
- 속성 마스터 (화염/얼음/번개/물/신성/어둠) I/II/III (18개)

**탐험 업적 (6개):**
- 던전 탐험가 I/II/III
- 타워 등반자 I/II/III

**전투 마스터 업적 (9개):**
- 연승 행진 I/II/III
- 무상 I/II/III
- 속전속결 I/II/III

**수집 업적 (6개):**
- 수집가 I/II/III
- 포션 마스터 I/II/III

**재화 업적 (6개):**
- 부자의 길 I/II/III
- 대부호 I/II/III

**성장 업적 (4개):**
- 수련의 길 I/II/III/IV

**총 46개 업적**
