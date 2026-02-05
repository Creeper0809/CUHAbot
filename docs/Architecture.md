# 시스템 아키텍처 (System Architecture)

## 개요

CUHABot RPG 시스템의 전체 아키텍처를 정의합니다. Database.md의 스키마를 기반으로 구현 방향을 제시합니다.

---

## 전체 아키텍처 다이어그램

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Discord Client                               │
│                    (사용자 인터페이스 레이어)                          │
└────────────────────────────┬────────────────────────────────────────┘
                             │ Slash Commands / Interactions
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                           bot.py                                     │
│                      (Entry Point)                                   │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐   │
│  │   Cogs      │ │   DTO       │ │  Decorator  │ │  Resources  │   │
│  │ (Commands)  │ │  (Views)    │ │ (Middleware)│ │  (Static)   │   │
│  └──────┬──────┘ └──────┬──────┘ └──────┬──────┘ └──────┬──────┘   │
└─────────┼───────────────┼───────────────┼───────────────┼──────────┘
          │               │               │               │
          ▼               ▼               ▼               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        Service Layer                                 │
│  ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐       │
│  │ dungeon_service │ │  user_service   │ │   item_service  │       │
│  └────────┬────────┘ └────────┬────────┘ └────────┬────────┘       │
│           │                   │                   │                 │
│  ┌────────▼────────────────────────────────────────────────┐       │
│  │              service/dungeon/                            │       │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐    │       │
│  │  │ skill_       │ │    buff.py   │ │ turn_config  │    │       │
│  │  │ component.py │ │              │ │    .py       │    │       │
│  │  └──────────────┘ └──────────────┘ └──────────────┘    │       │
│  └─────────────────────────────────────────────────────────┘       │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       Repository Layer                               │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐   │
│  │dungeon_repo │ │ users_repo  │ │  item_repo  │ │ monster_repo│   │
│  └──────┬──────┘ └──────┬──────┘ └──────┬──────┘ └──────┬──────┘   │
│         │               │               │               │           │
│  ┌──────▼───────────────▼───────────────▼───────────────▼──────┐   │
│  │                    static_cache.py                           │   │
│  │              (In-Memory Cache for Static Data)               │   │
│  └──────────────────────────────────────────────────────────────┘   │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        Models (ORM Layer)                            │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐   │
│  │  dungeon.py │ │   users.py  │ │   item.py   │ │  monster.py │   │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘   │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐   │
│  │  skill.py   │ │   grade.py  │ │ equip_pos.py│ │   buff.py   │   │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘   │
└────────────────────────────┬────────────────────────────────────────┘
                             │ Tortoise ORM
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        MySQL Database                                │
│                    (Database.md 스키마)                              │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 레이어별 상세

### 1. Presentation Layer (Cogs)

Discord 명령어와 상호작용을 처리합니다.

```
cogs/
├── dungeon_command.py    # 던전 탐험 명령어
├── user_command.py       # 사용자 정보 명령어
├── item_command.py       # 아이템/인벤토리 명령어
├── shop_command.py       # 상점 명령어
├── skill_command.py      # 스킬 관리 명령어
├── party_command.py      # 파티/레이드 명령어
└── admin_command.py      # 관리자 명령어
```

#### 명령어 목록
| 명령어 | 설명 | Cog |
|--------|------|-----|
| `/던전` | 던전 선택 및 입장 | dungeon_command |
| `/탐험` | 현재 던전 탐험 | dungeon_command |
| `/전투` | 전투 수행 | dungeon_command |
| `/귀환` | 마을로 귀환 | dungeon_command |
| `/정보` | 캐릭터 정보 확인 | user_command |
| `/인벤토리` | 인벤토리 확인 | item_command |
| `/장착` | 장비 장착 | item_command |
| `/상점` | 상점 이용 | shop_command |
| `/강화` | 장비 강화 | item_command |
| `/스킬` | 스킬 관리 | skill_command |
| `/파티` | 파티 관리 | party_command |
| `/레이드` | 레이드 참가 | party_command |

---

### 2. DTO Layer (Discord Views)

Discord UI 컴포넌트를 관리합니다.

```
DTO/
├── dungeon_select_view.py     # 던전 선택 드롭다운
├── dungeon_control.py         # 탐험 컨트롤 버튼
├── fight_or_flee.py           # 전투/도주 선택
├── inventory_view.py          # 인벤토리 UI
├── shop_view.py               # 상점 UI
├── deck_edit_view.py          # 덱 편집 UI (NEW)
├── party_view.py              # 파티 관리 UI
└── combat_view.py             # 전투 UI (자동 전투 진행 표시)
```

---

### 3. Service Layer

비즈니스 로직을 처리합니다.

```
service/
├── session.py                 # 세션 관리 (던전 상태)
├── dungeon_service.py         # 던전 서비스 (상위 레벨)
├── user_service.py            # 사용자 서비스
├── combat_service.py          # 전투 서비스 (NEW)
├── item_service.py            # 아이템 서비스
├── shop_service.py            # 상점 서비스 (NEW)
├── party_service.py           # 파티 서비스 (NEW)
└── dungeon/
    ├── dungeon_service.py     # 던전 내부 로직
    ├── skill_component.py     # 스킬 컴포넌트 시스템
    ├── buff.py                # 버프/디버프 시스템
    ├── item_service.py        # 던전 내 아이템 로직
    ├── turn_config.py         # 턴 설정
    └── combat_calculator.py   # 전투 계산기 (NEW)
```

#### 주요 서비스 클래스

```python
# combat_service.py
class CombatService:
    """전투 관련 비즈니스 로직 (랜덤 스킬 발동 시스템)"""

    async def start_combat(self, session: DungeonSession, monster: Monster) -> CombatResult:
        """전투 시작 - 덱 로드 및 초기화"""
        session.load_skill_deck()  # 사용자의 10슬롯 덱 로드
        session.current_monster = monster
        session.calculate_synergies()  # 덱 시너지 계산
        return CombatResult(started=True)

    async def execute_turn(self, session: DungeonSession) -> TurnResult:
        """턴 실행 - 랜덤 스킬 발동"""
        # 1. 플레이어 덱에서 랜덤 스킬 선택
        player_skill = session.get_random_skill_from_deck()

        # 2. 스킬 발동
        player_result = await self.execute_skill(session, player_skill, session.current_monster)

        # 3. 몬스터 턴 (몬스터도 랜덤 스킬)
        monster_skill = session.current_monster.get_random_skill()
        monster_result = await self.execute_skill(session, monster_skill, session.user_stats)

        # 4. 턴 종료 처리 (DOT, 버프 감소 등)
        await self.process_turn_end(session)

        return TurnResult(player_result, monster_result)

    async def execute_skill(self, session, skill, target) -> SkillResult:
        """스킬 실행"""
        # 시너지 보너스 적용
        synergy_bonus = session.get_synergy_bonus(skill.element)

        damage = CombatCalculator.calculate_damage(
            attacker=session.user_stats,
            defender=target,
            skill=skill,
            synergy_bonus=synergy_bonus
        )
        return SkillResult(skill=skill, damage=damage, target=target)

# deck_service.py (NEW)
class DeckService:
    """덱 관리 서비스"""

    async def get_user_deck(self, user_id: str) -> List[Skill]:
        """사용자의 10슬롯 덱 조회"""
        deck_entries = await UserSkillDeck.filter(user_id=user_id).order_by('slot_index')
        return [StaticCache.get_skill(entry.skill_id) for entry in deck_entries]

    async def set_skill_to_slot(self, user_id: str, slot_index: int, skill_id: int) -> bool:
        """특정 슬롯에 스킬 설정"""
        if slot_index < 0 or slot_index > 9:
            raise InvalidSlotError()
        await UserSkillDeck.update_or_create(
            user_id=user_id, slot_index=slot_index,
            defaults={'skill_id': skill_id}
        )
        return True

    def calculate_deck_synergies(self, deck: List[Skill]) -> Dict[str, float]:
        """덱 시너지 계산"""
        element_counts = Counter(s.element for s in deck if s.element != 'none')
        synergies = {}

        for element, count in element_counts.items():
            if count >= 10:
                synergies[element] = 'mastery'
            elif count >= 7:
                synergies[element] = 0.35
            elif count >= 5:
                synergies[element] = 0.20
            elif count >= 3:
                synergies[element] = 0.10

        return synergies

# combat_calculator.py
class CombatCalculator:
    """데미지 및 전투 계산"""

    @staticmethod
    def calculate_damage(attacker, defender, skill, synergy_bonus: float = 0) -> int:
        """데미지 계산 (시너지 보너스 포함)"""
        if skill.damage_type == 'physical':
            base = (attacker.attack * skill.damage_percent / 100) - (defender.ad_defense * 0.5)
        else:
            base = (attacker.ap_attack * skill.damage_percent / 100) - (defender.ap_defense * 0.4)

        # 속성 상성
        elemental_bonus = CombatCalculator.calculate_elemental_bonus(skill.element, defender.element)

        # 시너지 보너스
        total_bonus = 1 + synergy_bonus

        final_damage = base * elemental_bonus * total_bonus * random.uniform(0.9, 1.1)
        return max(int(final_damage), 1)

    @staticmethod
    def calculate_elemental_bonus(attacker_element: str, defender_element: str) -> float:
        """속성 상성 계산"""
        ELEMENTAL_CHART = {
            ('fire', 'ice'): 1.5,
            ('ice', 'lightning'): 1.5,
            ('lightning', 'water'): 1.5,
            ('water', 'fire'): 1.5,
            ('holy', 'dark'): 1.5,
            ('dark', 'holy'): 1.5,
        }
        return ELEMENTAL_CHART.get((attacker_element, defender_element), 1.0)
```

---

### 4. Repository Layer

데이터 접근을 추상화합니다.

```
models/repos/
├── __init__.py
├── dungeon_repo.py      # 던전 데이터 접근
├── users_repo.py        # 사용자 데이터 접근
├── item_repo.py         # 아이템 데이터 접근
├── monster_repo.py      # 몬스터 데이터 접근
├── skill_repo.py        # 스킬 데이터 접근
├── static_cache.py      # 정적 데이터 캐시
└── inventory_repo.py    # 인벤토리 데이터 접근 (NEW)
```

#### 캐시 전략

```python
# static_cache.py
class StaticCache:
    """정적 데이터 인메모리 캐시"""

    _dungeons: Dict[int, Dungeon] = {}
    _monsters: Dict[int, Monster] = {}
    _items: Dict[int, Item] = {}
    _skills: Dict[int, Skill] = {}
    _grades: Dict[int, Grade] = {}
    _equip_positions: Dict[int, EquipPos] = {}

    @classmethod
    async def load_all(cls):
        """봇 시작 시 모든 정적 데이터 로드"""
        cls._dungeons = {d.id: d for d in await Dungeon.all()}
        cls._monsters = {m.id: m for m in await Monster.all()}
        cls._items = {i.id: i for i in await Item.all()}
        cls._skills = {s.id: s for s in await Skill.all()}
        cls._grades = {g.id: g for g in await Grade.all()}
        cls._equip_positions = {e.id: e for e in await EquipPos.all()}

    @classmethod
    def get_dungeon(cls, dungeon_id: int) -> Optional[Dungeon]:
        return cls._dungeons.get(dungeon_id)

    @classmethod
    def get_monsters_by_dungeon(cls, dungeon_id: int) -> List[Monster]:
        return [m for m in cls._monsters.values() if m.dungeon == dungeon_id]
```

---

### 5. Model Layer (ORM)

Tortoise ORM 모델 정의입니다.

```
models/
├── __init__.py           # 자동 생성 (generate_model.py)
├── base_item.py          # 아이템 기본 클래스
├── item.py               # 아이템 모델
├── equipment_item.py     # 장비 아이템
├── consume_item.py       # 소비 아이템
├── skill.py              # 스킬 모델
├── dungeon.py            # 던전 모델
├── dungeon_spawn.py      # 던전 스폰 테이블
├── monster.py            # 몬스터 모델
├── users.py              # 사용자 모델
├── user_spec.py          # 사용자 스펙 (NEW)
├── user_inventory.py     # 사용자 인벤토리 (NEW)
├── user_equipment.py     # 장착 장비 (NEW)
├── grade.py              # 등급 모델
├── equip_pos.py          # 장비 위치
├── buff.py               # 버프 모델 (NEW)
├── ability.py            # 어빌리티 모델 (NEW)
└── util/
    ├── __init__.py
    ├── generate_model.py
    └── item_embed.py
```

---

## 데이터베이스 스키마 (확장)

### 핵심 테이블 관계도

```
┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│    User     │──────│  UserSpec   │──────│  User_Inv   │
└─────────────┘      └─────────────┘      └──────┬──────┘
                                                  │
                     ┌────────────────────────────┼────────────────────────────┐
                     │                            │                            │
              ┌──────▼──────┐             ┌───────▼──────┐             ┌───────▼──────┐
              │    Item     │             │ User_eq_inv  │             │Enhanced_Equip│
              └──────┬──────┘             └──────────────┘             └──────────────┘
                     │
     ┌───────────────┼───────────────┬───────────────┐
     │               │               │               │
┌────▼────┐   ┌──────▼─────┐  ┌──────▼─────┐  ┌─────▼────────┐
│Equipment│   │Consumeable │  │   Skill    │  │Item_Ability  │
│  Item   │   │   Item     │  │   Item     │  │              │
└────┬────┘   └────────────┘  └──────┬─────┘  └──────┬───────┘
     │                               │               │
     │                               │               │
┌────▼────┐                   ┌──────▼─────┐  ┌─────▼────────┐
│EquipPos │                   │   Skill    │  │Ability_Table │
└─────────┘                   └────────────┘  └──────────────┘
```

### 새로운/수정된 테이블

#### User_Skill_Deck (사용자 스킬 덱) - 10슬롯 덱 시스템
```sql
CREATE TABLE User_Skill_Deck (
  id INT PRIMARY KEY AUTO_INCREMENT,
  user_id VARCHAR(50) NOT NULL,
  slot_index INT NOT NULL,  -- 0-9 (10슬롯)
  skill_id INT NOT NULL,
  FOREIGN KEY (user_id) REFERENCES UserSpec(id),
  FOREIGN KEY (skill_id) REFERENCES Skill(id),
  UNIQUE KEY unique_user_slot (user_id, slot_index)
);
-- 참고: 같은 스킬을 여러 슬롯에 장착 가능 (확률 증가)
```

#### User_Passive_Skill (사용자 패시브 스킬)
```sql
CREATE TABLE User_Passive_Skill (
  id INT PRIMARY KEY AUTO_INCREMENT,
  user_id VARCHAR(50) NOT NULL,
  slot_index INT NOT NULL,  -- 0-3 (최대 4슬롯)
  skill_id INT NOT NULL,
  FOREIGN KEY (user_id) REFERENCES UserSpec(id),
  FOREIGN KEY (skill_id) REFERENCES Skill(id),
  UNIQUE KEY unique_user_passive (user_id, slot_index)
);
```

#### User_Skill_Inventory (보유 스킬)
```sql
CREATE TABLE User_Skill_Inventory (
  id INT PRIMARY KEY AUTO_INCREMENT,
  user_id VARCHAR(50) NOT NULL,
  skill_id INT NOT NULL,
  acquired_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES UserSpec(id),
  FOREIGN KEY (skill_id) REFERENCES Skill(id),
  UNIQUE KEY unique_user_skill (user_id, skill_id)
);
```

#### Skill (스킬 테이블) - 덱빌딩 시스템용
```sql
CREATE TABLE Skill (
  id INT PRIMARY KEY AUTO_INCREMENT,
  name VARCHAR(50) NOT NULL,
  description TEXT,
  type ENUM('attack', 'heal', 'buff', 'debuff', 'ultimate', 'passive'),
  element ENUM('none', 'fire', 'ice', 'lightning', 'water', 'holy', 'dark'),
  damage_percent INT DEFAULT 100,  -- 데미지 배율 (%)
  grade_id INT,
  effect_json JSON,  -- 부가 효과 (상태이상, 힐량 등)
  skill_book_item_id INT,  -- 스킬북 아이템 ID
  FOREIGN KEY (grade_id) REFERENCES Grade(id),
  FOREIGN KEY (skill_book_item_id) REFERENCES item(id)
);
-- 참고: MP/쿨다운 없음 (랜덤 발동 시스템)
```

#### Buff (버프/디버프)
```sql
CREATE TABLE Buff (
  id INT PRIMARY KEY AUTO_INCREMENT,
  name VARCHAR(50) NOT NULL,
  type ENUM('buff', 'debuff'),
  stat VARCHAR(50),  -- 영향받는 스탯
  value FLOAT,  -- 수치 (%, 고정값)
  is_percent BOOLEAN DEFAULT TRUE,
  duration INT DEFAULT 3,
  stackable BOOLEAN DEFAULT FALSE,
  max_stack INT DEFAULT 1,
  icon VARCHAR(10)  -- 이모지
);
```

#### Combat_Log (전투 로그)
```sql
CREATE TABLE Combat_Log (
  id INT PRIMARY KEY AUTO_INCREMENT,
  session_id VARCHAR(100),
  turn INT,
  actor_type ENUM('player', 'monster'),
  actor_id VARCHAR(50),
  action_type VARCHAR(50),
  target_id VARCHAR(50),
  damage INT,
  heal INT,
  buff_applied VARCHAR(100),
  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

#### Party (파티)
```sql
CREATE TABLE Party (
  id INT PRIMARY KEY AUTO_INCREMENT,
  leader_id VARCHAR(50) NOT NULL,
  name VARCHAR(50),
  max_members INT DEFAULT 4,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (leader_id) REFERENCES UserSpec(id)
);

CREATE TABLE Party_Member (
  id INT PRIMARY KEY AUTO_INCREMENT,
  party_id INT NOT NULL,
  user_id VARCHAR(50) NOT NULL,
  joined_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (party_id) REFERENCES Party(id),
  FOREIGN KEY (user_id) REFERENCES UserSpec(id)
);
```

---

## 세션 관리

### DungeonSession 구조 (덱빌딩 시스템)

```python
@dataclass
class DungeonSession:
    """던전 탐험 세션 - 덱 기반 랜덤 스킬 시스템"""
    user_id: str
    dungeon_id: int

    # 상태
    current_floor: int = 1
    exploration_count: int = 0
    in_combat: bool = False
    turn_count: int = 0  # 전투 턴 수

    # 덱 시스템 (핵심)
    skill_deck: List[Skill] = field(default_factory=list)  # 10슬롯 덱
    active_deck: List[int] = field(default_factory=list)   # 활성 슬롯 인덱스 (궁극기 소모 반영)
    deck_synergies: Dict[str, float] = field(default_factory=dict)  # 시너지 보너스
    last_skill_index: int = -1  # 마지막 발동 스킬 (연속 발동 체크)
    no_attack_turns: int = 0    # 공격 미발동 턴 수 (운 보호)

    # 전투 상태
    current_monster: Optional[Monster] = None
    user_stats: UserCombatStats = None
    monster_stats: MonsterCombatStats = None
    combat_log: List[str] = field(default_factory=list)

    # 버프/디버프
    active_buffs: List[ActiveBuff] = field(default_factory=list)
    active_debuffs: List[ActiveDebuff] = field(default_factory=list)

    # Discord 참조
    message_id: int = None
    dm_message_id: int = None

    # 획득 아이템/경험치
    loot: List[Item] = field(default_factory=list)
    exp_gained: int = 0
    gold_gained: int = 0

    def load_skill_deck(self):
        """DB에서 사용자 덱 로드"""
        self.skill_deck = DeckService.get_user_deck(self.user_id)
        self.active_deck = list(range(10))  # 모든 슬롯 활성
        self.deck_synergies = DeckService.calculate_deck_synergies(self.skill_deck)

    def get_random_skill_from_deck(self) -> Skill:
        """덱에서 랜덤 스킬 선택"""
        import random

        # 운 보호: 3턴 연속 공격 미발동 시 공격 확정
        if self.no_attack_turns >= 3:
            attack_slots = [i for i in self.active_deck
                          if self.skill_deck[i].type == 'attack']
            if attack_slots:
                slot = random.choice(attack_slots)
                self.no_attack_turns = 0
                return self.skill_deck[slot]

        # 랜덤 선택
        slot = random.choice(self.active_deck)
        skill = self.skill_deck[slot]

        # 궁극기 발동 시 슬롯 비활성화
        if skill.type == 'ultimate':
            self.active_deck.remove(slot)

        # 연속 발동 체크 (같은 스킬 연속 시 위력 감소 적용은 별도)
        self.last_skill_index = slot

        # 공격 미발동 턴 추적
        if skill.type != 'attack':
            self.no_attack_turns += 1
        else:
            self.no_attack_turns = 0

        return skill

    def get_synergy_bonus(self, element: str) -> float:
        """시너지 보너스 반환"""
        return self.deck_synergies.get(element, 0)

@dataclass
class UserCombatStats:
    """전투 중 사용자 스탯"""
    max_hp: int
    current_hp: int
    attack: int
    ap_attack: int
    ad_defense: int
    ap_defense: int
    speed: int
    accuracy: float
    evasion: float
    critical_rate: float
    critical_damage: float
    lifesteal: float
    element: Optional[str] = None

@dataclass
class ActiveBuff:
    """활성화된 버프"""
    buff: Buff
    remaining_turns: int
    current_stack: int = 1
    source: str = "unknown"
```

### 세션 매니저

```python
class SessionManager:
    """세션 관리자"""
    _sessions: Dict[str, DungeonSession] = {}

    @classmethod
    def get_session(cls, user_id: str) -> Optional[DungeonSession]:
        return cls._sessions.get(user_id)

    @classmethod
    def create_session(cls, user_id: str, dungeon_id: int) -> DungeonSession:
        if user_id in cls._sessions:
            raise SessionAlreadyExistsError()
        session = DungeonSession(user_id=user_id, dungeon_id=dungeon_id)
        cls._sessions[user_id] = session
        return session

    @classmethod
    def end_session(cls, user_id: str) -> Optional[DungeonSession]:
        return cls._sessions.pop(user_id, None)

    @classmethod
    async def save_progress(cls, user_id: str) -> None:
        """세션 진행 상황을 DB에 저장 (크래시 복구용)"""
        session = cls._sessions.get(user_id)
        if session:
            await DungeonProgress.update_or_create(
                user_id=user_id,
                defaults={
                    'dungeon_id': session.dungeon_id,
                    'current_floor': session.current_floor,
                    'session_data': json.dumps(asdict(session))
                }
            )
```

---

## 스킬 컴포넌트 시스템

### 컴포넌트 등록

```python
# skill_component.py

SKILL_COMPONENTS: Dict[str, Type[SkillComponent]] = {}

def register_skill_with_tag(tag: str):
    """스킬 컴포넌트 등록 데코레이터"""
    def decorator(cls):
        SKILL_COMPONENTS[tag] = cls
        return cls
    return decorator

class SkillComponent(ABC):
    """스킬 컴포넌트 기본 클래스"""

    def __init__(self, config: dict):
        self.config = config

    @abstractmethod
    async def on_turn(self, session: DungeonSession, target) -> SkillResult:
        """턴에 실행되는 로직"""
        pass

    async def on_turn_start(self, session: DungeonSession) -> None:
        """턴 시작 시 실행"""
        pass

    async def on_turn_end(self, session: DungeonSession) -> None:
        """턴 종료 시 실행"""
        pass

    async def on_hit(self, session: DungeonSession, damage: int) -> int:
        """피격 시 실행 (데미지 수정 가능)"""
        return damage
```

### 주요 컴포넌트

```python
@register_skill_with_tag("attack")
class AttackComponent(SkillComponent):
    """공격 스킬 컴포넌트"""

    async def on_turn(self, session: DungeonSession, target) -> SkillResult:
        damage = CombatCalculator.calculate_damage(
            attacker=session.user_stats,
            defender=target,
            skill_ratio=self.config["damage_percent"] / 100,
            damage_type=self.config.get("damage_type", "physical"),
            element=self.config.get("element")
        )

        # 상태이상 적용
        status = self.config.get("status")
        if status and random.random() < status["chance"] / 100:
            await apply_status_effect(target, status["type"], status["duration"])

        return DamageResult(target=target, damage=damage, element=self.config.get("element"))

@register_skill_with_tag("heal")
class HealComponent(SkillComponent):
    """회복 스킬 컴포넌트"""

    async def on_turn(self, session: DungeonSession, target) -> SkillResult:
        heal_amount = int(target.max_hp * self.config["heal_percent"] / 100)

        # 힐 버프 적용
        heal_bonus = sum(b.value for b in session.active_buffs if b.buff.stat == "heal")
        heal_amount = int(heal_amount * (1 + heal_bonus / 100))

        actual_heal = min(heal_amount, target.max_hp - target.current_hp)
        target.current_hp += actual_heal

        return HealResult(target=target, heal=actual_heal)

@register_skill_with_tag("buff")
class BuffComponent(SkillComponent):
    """버프 스킬 컴포넌트"""

    async def on_turn(self, session: DungeonSession, target) -> SkillResult:
        buff = ActiveBuff(
            buff=Buff(
                name=self.config["buff_name"],
                stat=self.config["stat"],
                value=self.config["value"],
                is_percent=self.config.get("is_percent", True)
            ),
            remaining_turns=self.config["duration"],
            source="skill"
        )

        session.active_buffs.append(buff)
        return BuffResult(target=target, buff=buff)

@register_skill_with_tag("dot")
class DotComponent(SkillComponent):
    """지속 피해 컴포넌트"""

    async def on_turn_start(self, session: DungeonSession) -> List[DamageResult]:
        results = []

        for debuff in session.active_debuffs:
            if debuff.buff.type == "dot":
                damage = int(session.monster_stats.max_hp * debuff.buff.value / 100)
                damage *= debuff.current_stack
                session.monster_stats.current_hp -= damage
                results.append(DotDamageResult(
                    target=session.current_monster,
                    damage=damage,
                    source=debuff.buff.name
                ))

        return results
```

---

## 이벤트 시스템

### 게임 이벤트

```python
class GameEvent(Enum):
    # 전투 이벤트
    COMBAT_START = "combat_start"
    COMBAT_END = "combat_end"
    TURN_START = "turn_start"
    TURN_END = "turn_end"
    DAMAGE_DEALT = "damage_dealt"
    DAMAGE_RECEIVED = "damage_received"
    HEAL_RECEIVED = "heal_received"
    BUFF_APPLIED = "buff_applied"
    DEBUFF_APPLIED = "debuff_applied"
    STATUS_EFFECT_APPLIED = "status_effect_applied"

    # 던전 이벤트
    DUNGEON_ENTER = "dungeon_enter"
    DUNGEON_EXIT = "dungeon_exit"
    FLOOR_CLEAR = "floor_clear"
    BOSS_ENCOUNTER = "boss_encounter"
    LOOT_DROPPED = "loot_dropped"

    # 캐릭터 이벤트
    LEVEL_UP = "level_up"
    SKILL_LEARNED = "skill_learned"
    ITEM_EQUIPPED = "item_equipped"
    ITEM_ENHANCED = "item_enhanced"

class EventBus:
    """이벤트 버스"""
    _listeners: Dict[GameEvent, List[Callable]] = {}

    @classmethod
    def subscribe(cls, event: GameEvent, callback: Callable):
        if event not in cls._listeners:
            cls._listeners[event] = []
        cls._listeners[event].append(callback)

    @classmethod
    async def emit(cls, event: GameEvent, **kwargs):
        if event in cls._listeners:
            for callback in cls._listeners[event]:
                await callback(**kwargs)
```

---

## 에러 처리

### 커스텀 예외

```python
# exceptions.py

class CUHABotException(Exception):
    """기본 예외 클래스"""
    message: str = "알 수 없는 오류가 발생했습니다."

class SessionAlreadyExistsError(CUHABotException):
    message = "이미 진행 중인 던전이 있습니다."

class SessionNotFoundError(CUHABotException):
    message = "진행 중인 던전이 없습니다."

class NotInCombatError(CUHABotException):
    message = "전투 중이 아닙니다."

class InsufficientMPError(CUHABotException):
    message = "MP가 부족합니다."

class SkillOnCooldownError(CUHABotException):
    message = "스킬이 쿨다운 중입니다."

class LevelRequirementError(CUHABotException):
    message = "레벨이 부족합니다."

class InventoryFullError(CUHABotException):
    message = "인벤토리가 가득 찼습니다."

class ItemNotFoundError(CUHABotException):
    message = "아이템을 찾을 수 없습니다."

class NotEnoughGoldError(CUHABotException):
    message = "골드가 부족합니다."
```

### 에러 핸들러

```python
# error_handler.py

async def handle_game_error(interaction: discord.Interaction, error: Exception):
    """게임 에러 핸들러"""
    if isinstance(error, CUHABotException):
        embed = discord.Embed(
            title="❌ 오류",
            description=error.message,
            color=discord.Color.red()
        )
    else:
        embed = discord.Embed(
            title="❌ 시스템 오류",
            description="예기치 않은 오류가 발생했습니다. 잠시 후 다시 시도해주세요.",
            color=discord.Color.red()
        )
        logging.error(f"Unexpected error: {error}", exc_info=True)

    await interaction.response.send_message(embed=embed, ephemeral=True)
```

---

## 성능 최적화

### 캐싱 전략

1. **정적 데이터**: 봇 시작 시 메모리에 로드 (던전, 몬스터, 아이템, 스킬)
2. **사용자 데이터**: LRU 캐시 + DB (자주 접근하는 사용자)
3. **세션 데이터**: 메모리 (주기적으로 DB 백업)

### DB 최적화

```python
# 쿼리 최적화 예시
async def get_user_with_inventory(user_id: str):
    """사용자와 인벤토리를 한 번에 조회"""
    return await UserSpec.get(id=user_id).prefetch_related(
        'inventory',
        'inventory__item',
        'equipped_items',
        'equipped_items__item'
    )
```

### 배치 처리

```python
async def apply_loot_to_inventory(user_id: str, loot: List[Item]):
    """획득 아이템 일괄 처리"""
    async with transactions.in_transaction():
        for item in loot:
            existing = await User_Inv.get_or_none(
                discord_id=user_id,
                item_id=item.id
            )
            if existing:
                existing.quantity += 1
                await existing.save()
            else:
                await User_Inv.create(
                    discord_id=user_id,
                    item_id=item.id,
                    quantity=1
                )
```

---

## 배포 체크리스트

### 필수 환경 변수
```
DEV=FALSE
DISCORD_TOKEN=<production_token>
APPLICATION_ID=<production_app_id>
GUILD_ID=<guild_id>  # 또는 제거하여 글로벌 명령어 사용
DATABASE_URL=<production_db_host>
DATABASE_USER=<db_user>
DATABASE_PASSWORD=<db_password>
DATABASE_PORT=3306
DATABASE_TABLE=<db_name>
```

### 데이터베이스 마이그레이션
```bash
# 스키마 생성
python -c "from tortoise import Tortoise; import asyncio; asyncio.run(Tortoise.generate_schemas())"

# 정적 데이터 시딩
python scripts/seed_data.py
```

### 모니터링
- 로그 레벨: INFO (프로덕션), DEBUG (개발)
- 에러 추적: Sentry 또는 유사 서비스
- 성능 메트릭: Prometheus + Grafana
