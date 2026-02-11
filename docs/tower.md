주간 타워 시스템 구현 계획
Context
CUHABot의 새로운 엔드게임 콘텐츠로 주간 타워를 추가합니다. 주간 타워는 100층 구조의 도전 던전으로, 다음과 같은 특징이 있습니다:

100층 수직 진행: 각 층마다 1번의 전투
보스층: 10층마다 보스 등장 (10, 20, 30... 100층)
휴식공간: 10층마다 휴식공간 제공 (덱/장비 변경, 상점 이용, 다음 10층 정보 확인)
제약 조건: 아이템 사용 불가, 휴식공간에서만 스킬/장비 변경 가능, 도주 불가
진행도 저장: 최고 도달 층수 저장, 사망 시 1층부터 재시작
시즌 시스템: 매주 월요일 00:00 리셋
타워 랭킹: 최고 도달 층수 기준 순위 (기존 /랭킹 명령어에 탭으로 통합)
타워 상점: 휴식공간에서 이용 가능 (타워 전용 화폐 및 상품)
기존 던전 시스템의 DungeonSession, ContentType, WeeklyTowerConfig가 이미 부분적으로 구현되어 있어, 이를 활용하여 구현합니다.

Implementation Approach
아키텍처 원칙
1. 기존 시스템 재사용 (최소 수정 원칙)

DungeonSession, encounter_processor, combat_executor 그대로 활용
content_type = ContentType.WEEKLY_TOWER 설정으로 타워 모드 활성화
max_steps = 1 설정으로 1층 = 1전투 구현
2. SRP 준수 (서비스 분리)


service/tower/
├── tower_service.py          # 타워 진행 오케스트레이션
├── tower_restriction.py      # 제약 조건 검증
├── tower_reward_service.py   # 층별 보상 계산
├── tower_season_service.py   # 시즌 관리
└── tower_shop_service.py     # 타워 상점 (Phase 4)
3. 몬스터 배치 전략 (사용자 선택: 기존 던전 스폰 재사용)

타워를 특정 던전에 매핑 (예: 1-10층 = 던전1, 11-20층 = 던전2...)
해당 던전의 DungeonSpawn 테이블에서 일반 몬스터 추출
보스층: 해당 던전의 보스 몬스터 중 랜덤 선택 (is_boss_monster=True)
4. Guard Clause 패턴 (제약 적용)


# 각 서비스 진입점에 guard clause 추가
def enforce_item_usage_restriction(session: DungeonSession) -> None:
    if session and session.content_type == ContentType.WEEKLY_TOWER:
        raise WeeklyTowerRestrictionError("아이템을 사용할 수 없습니다")

def enforce_skill_change_restriction(session: DungeonSession) -> None:
    # 휴식공간(10층마다)에서만 변경 가능
    if session and session.content_type == ContentType.WEEKLY_TOWER:
        if session.status != SessionType.REST:
            raise WeeklyTowerRestrictionError("휴식공간에서만 스킬을 변경할 수 있습니다")
Critical Files
새로 생성할 파일 (8개)
models/user_tower_progress.py - 진행도 저장 모델
models/repos/tower_progress_repo.py - 진행도 저장소
service/tower/tower_service.py - 타워 핵심 로직
service/tower/tower_restriction.py - 제약 검증
service/tower/tower_reward_service.py - 보상 계산
service/tower/tower_season_service.py - 시즌 관리
cogs/tower_command.py - /주간타워 커맨드
views/tower_view.py - 타워 UI (층 클리어, 휴식공간)
views/tower_rest_area_view.py - 휴식공간 UI (덱/장비 변경, 상점, 다음 구간 정보)
수정할 파일 (7개, 최소 침습적 수정)
service/item/item_use_service.py (Line ~87)
Guard clause 1줄 추가
service/skill/skill_deck_service.py (save_deck 메서드)
Guard clause 1줄 추가
service/dungeon/encounter_processor.py (Line ~86, ~249)
타워 시 몬스터 강제 (2줄)
도주 제약 guard clause (1줄)
service/dungeon/dungeon_loop.py (Line ~56)
타워 시 max_steps = 1 설정 (2줄)
views/ranking_view.py
타워 랭킹 탭 추가 (탭 버튼 1개, embed 생성 메서드 1개)
service/ranking_service.py
get_tower_ranking() 메서드 추가
bot.py (on_ready)
타워 시즌 백그라운드 태스크 시작 (3줄)
Phase-by-Phase Implementation
Phase 1: Core Entry & Floor Progression (Week 1)
목표: 타워 입장, 층별 진행, 진행도 저장

Tasks:

모델 생성 (models/user_tower_progress.py)


class UserTowerProgress(models.Model):
    user = ForeignKeyField('models.User')
    season_id = IntField(default=1)
    highest_floor_reached = IntField(default=0)
    current_floor = IntField(default=0)
    rewards_claimed = JSONField(default=list)
    last_attempt_time = DatetimeField(null=True)
    season_start_time = DatetimeField(auto_now_add=True)
Repository (models/repos/tower_progress_repo.py)

get_or_create_progress(user, season_id)
update_highest_floor(user, floor)
save_progress(progress)
Tower Service (service/tower/tower_service.py)


async def initialize_tower_session(user, session) -> UserTowerProgress
async def get_floor_monster(tower_floor: int) -> Monster
def is_boss_floor(floor: int) -> bool
async def advance_floor(session, progress) -> bool
층별 던전 매핑: floor → dungeon_id (예: 1-10층 = dungeon1...)
일반 몬스터: 해당 던전의 DungeonSpawn에서 확률 기반 선택
보스 몬스터: 해당 던전의 보스 중 랜덤 선택
Command (cogs/tower_command.py)

/주간타워 명령어
레벨 체크 (최소 레벨 50 권장)
진행도 로드 및 안내 메시지
Integration: dungeon_loop.py (Line ~56)


# 타워: 1층 = 1전투
if session.content_type == ContentType.WEEKLY_TOWER:
    session.max_steps = 1
Integration: encounter_processor.py (Line ~86)


# 타워: 항상 몬스터 인카운터
if session.content_type == ContentType.WEEKLY_TOWER:
    encounter_type = EncounterType.MONSTER
Verification:

/주간타워 실행 → 1층 전투 → 승리 시 2층 진행 확인
사망 시 진행도 저장 확인 (DB 조회)
Phase 2: Boss Floors & Restrictions (Week 2)
목표: 보스층 처리, 제약 조건 완전 적용

Tasks:

Restriction Layer (service/tower/tower_restriction.py)


def enforce_item_usage_restriction(session)
def enforce_skill_change_restriction(session)
def enforce_flee_restriction(session)
Integration: item_use_service.py (Line ~87)


from service.tower.tower_restriction import enforce_item_usage_restriction
enforce_item_usage_restriction(session)  # 전투 체크 전에 추가
Integration: skill_deck_service.py (save_deck)


from service.tower.tower_restriction import enforce_skill_change_restriction
enforce_skill_change_restriction(session)  # 휴식공간 체크
3-1. Integration: equipment_service.py (equip/unequip)


from service.tower.tower_restriction import enforce_equipment_change_restriction
enforce_equipment_change_restriction(session)  # 휴식공간 체크
Integration: encounter_processor.py (Line ~249, flee 로직)


from service.tower.tower_restriction import enforce_flee_restriction
enforce_flee_restriction(session)  # 기존 보스 체크 전에 추가
Boss Floor Enhancement (tower_service.py)

get_floor_monster(): floor % 10 == 0일 때 보스 스폰 로직
해당 층의 던전에서 is_boss_monster=True 몬스터 필터링
보스가 없으면 fallback: 상위 던전의 보스 사용
UI: Boss Warning (views/tower_view.py)

보스층 도달 시 경고 임베드
"⚠️ 보스층 도달! (10층)" 메시지
Verification:

전투 중 /아이템사용 → WeeklyTowerRestrictionError 발생 확인
일반 층 사이에서 /덱변경 → 에러 발생 확인 ("휴식공간에서만 가능")
휴식공간 (10층 클리어 후)에서 /덱변경 → 성공 확인
10층 도달 → 보스 스폰 → 클리어 → 휴식공간 진입 확인
Phase 3: Floor Rewards & Persistence (Week 3)
목표: 층별 보상, 진행도 UI, 클리어 핸들링

Tasks:

Reward Service (service/tower/tower_reward_service.py)


BASE_EXP_PER_FLOOR = 100
BASE_GOLD_PER_FLOOR = 50
BOSS_FLOOR_MULTIPLIER = 2.0

def calculate_floor_reward(floor, is_boss) -> dict
async def apply_floor_reward(user, floor, is_boss) -> RewardResult
보상 공식: exp = floor * 100, gold = floor * 50
보스층 보너스: 2배
Floor Clear Handler (tower_service.py)


async def handle_floor_clear(session, progress):
    # 보상 적용
    reward = await tower_reward_service.apply_floor_reward(...)

    # 진행도 업데이트
    progress.current_floor += 1
    if progress.current_floor > progress.highest_floor_reached:
        progress.highest_floor_reached = progress.current_floor
    await save_progress(progress)

    # 100층 클리어 확인
    if progress.current_floor > 100:
        return await handle_tower_complete(session, progress)

    # 10층마다 휴식공간 진입
    if progress.current_floor % 10 == 0:
        return await enter_rest_area(session, progress)
        # 휴식공간 → 덱/장비 변경, 상점, 다음 구간 정보

    # 일반 층 클리어 → 계속/귀환 선택
    return await show_floor_clear_ui(session, progress)
2-1. Rest Area Handler (tower_service.py)


async def enter_rest_area(session, progress):
    # 세션 상태를 REST로 변경 (덱/장비 변경 허용)
    session.status = SessionType.REST

    # 휴식공간 UI 표시
    # - 현재 구간 완료 축하
    # - 다음 10층 정보 (예: "31-40층: 화염 구역, 불 속성 몬스터 출현")
    # - [스킬 변경] [장비 변경] [상점] [다음으로] 버튼
    await show_rest_area_ui(session, progress)
Floor Clear UI (views/tower_view.py)
일반 층 클리어 요약 임베드
[다음 층] / [귀환] 버튼
휴식공간 예고 (9층 클리어 시 "다음은 휴식공간!")
3-1. Rest Area UI (views/tower_rest_area_view.py)

휴식공간 임베드:
구간 완료 축하 (예: "10층 클리어! 휴식공간에 도착했습니다")
다음 구간 정보 (11-20층: 빙결 구역, 얼음 속성 몬스터)
버튼:
[스킬 변경] → 스킬 덱 UI 열기
[장비 변경] → 장비 UI 열기
[상점] → 타워 상점 UI 열기
[다음으로] → 휴식공간 떠나기, 다음 층 진행
[귀환] → 타워 나가기
Death Handling (tower_service.py)


async def handle_tower_death(session, progress):
    # 진행도는 유지 (highest_floor_reached)
    # current_floor는 0으로 리셋
    progress.current_floor = 0
    await save_progress(progress)
    # 안내 메시지: "최고 기록: XX층"
100층 클리어 보상

특별 칭호 부여 (있다면)
대량 보상 (경험치/골드)
이벤트 발행: TOWER_COMPLETED
Verification:

1층 클리어 → 보상 획득 → 2층 진행 확인
10층 클리어 → 보스 보너스 (2배 보상) 확인
50층에서 사망 → 진행도 저장 확인 → 재입장 시 1층부터 시작
100층 클리어 → 특별 메시지 확인
Phase 4: Season System, Tower Shop & Ranking Integration (Week 4)
목표: 시즌 리셋, 랭킹 통합, 타워 상점

Tasks:

Season Service (service/tower/tower_season_service.py)


def get_current_season() -> int
    # 2024-01-01 기준, 주차 계산

async def reset_season():
    # 모든 UserTowerProgress의 current_floor, highest_floor_reached 초기화
    # season_id 증가
    # 랭킹 스냅샷 저장 (선택)

async def start_season_reset_task():
    # 매주 월요일 00:00 실행
    # asyncio.create_task()로 백그라운드 실행
Integration: bot.py (on_ready)


from service.tower.tower_season_service import start_season_reset_task
await start_season_reset_task()
Ranking Integration - /랭킹 명령어에 타워 탭 추가

RankingService 확장 (service/ranking_service.py)


@staticmethod
async def get_tower_ranking(season_id: int, limit: int = 100) -> List[Dict]:
    """타워 랭킹 조회"""
    progresses = await UserTowerProgress.filter(
        season_id=season_id
    ).order_by('-highest_floor_reached').limit(limit).prefetch_related('user')

    return [
        {
            "rank": idx + 1,
            "username": p.user.username,
            "discord_id": p.user.discord_id,
            "highest_floor": p.highest_floor_reached,
        }
        for idx, p in enumerate(progresses)
    ]

@staticmethod
async def get_user_rankings(user_id: int) -> Dict:
    # 기존 메서드에 tower_rank 추가
    return {
        "level_rank": await get_user_rank_by_level(user_id),
        "gold_rank": await get_user_rank_by_gold(user_id),
        "tower_rank": await get_user_tower_rank(user_id, current_season),
    }
RankingView 확장 (views/ranking_view.py)


# __init__에 타워 탭 추가
self.add_item(TabButton("🗼 타워", "tower", is_active=False))

# 타워 랭킹 embed 메서드 추가
def _create_tower_embed(self) -> discord.Embed:
    rankings = self.tower_rankings
    # 레벨/골드 랭킹과 동일한 구조
    # 표시: 순위, 유저명, 최고 층수
Tower Shop - 10층마다 자동 표시

Shop Service (service/tower/tower_shop_service.py)


async def get_tower_shop_items(floor: int) -> list
    # 층수에 따라 상품 등급 조정
    # 10-30층: 일반 등급
    # 40-60층: 희귀 등급
    # 70-90층: 영웅 등급
    # 100층: 전설 등급

async def purchase_tower_item(user, progress, item_id) -> bool
    # 타워 코인 확인 및 차감
    # 아이템 지급
Shop UI (views/tower_view.py)


class TowerShopView(discord.ui.View):
    # 상점 아이템 목록 (Select 또는 Button)
    # 구매 버튼
    # 닫기 버튼
    # 10층 클리어 시 자동 호출
Tower Coin System:

층 클리어 시 코인 지급: 일반층 = 1코인, 보스층 = 5코인
UserTowerProgress.tower_coins 필드 사용
Season Announcement

리셋 시 서버 공지 채널에 메시지 전송
"🗼 주간 타워 시즌 X 시작!"
Verification:

시즌 계산 로직 테스트 (unittest)
수동 리셋 명령어 테스트: /타워리셋 (관리자 전용)
/랭킹 실행 → 🗼 타워 탭 확인 → 상위 10명 표시
10층 클리어 → 타워 상점 자동 표시 → 아이템 구매 테스트
Database Schema
UserTowerProgress

class UserTowerProgress(models.Model):
    id = IntField(pk=True)
    user = ForeignKeyField('models.User', related_name='tower_progress')
    season_id = IntField(default=1)
    highest_floor_reached = IntField(default=0)
    current_floor = IntField(default=0)
    rewards_claimed = JSONField(default=list)  # [10, 20, 30, ...]
    tower_coins = IntField(default=0)  # Phase 4
    last_attempt_time = DatetimeField(null=True)
    season_start_time = DatetimeField(auto_now_add=True)

    class Meta:
        table = "user_tower_progress"
        unique_together = (("user", "season_id"),)
Migration Script

python scripts/migrate_tower_system.py
테이블 생성
기존 유저에게 초기 레코드 생성 (season_id=1, floor=0)
Floor-to-Dungeon Mapping Strategy
층별 던전 매핑 (service/tower/tower_service.py):


FLOOR_DUNGEON_MAP = {
    (1, 10): 1,      # 1-10층: 던전 1 (초급)
    (11, 20): 2,     # 11-20층: 던전 2
    (21, 30): 3,     # 21-30층: 던전 3
    (31, 40): 4,     # 31-40층: 던전 4
    (41, 50): 5,     # 41-50층: 던전 5
    (51, 60): 6,     # 51-60층: 던전 6
    (61, 70): 7,     # 61-70층: 던전 7
    (71, 80): 8,     # 71-80층: 던전 8
    (81, 90): 9,     # 81-90층: 던전 9
    (91, 100): 10,   # 91-100층: 던전 10 (최종)
}

def get_dungeon_for_floor(floor: int) -> int:
    for (start, end), dungeon_id in FLOOR_DUNGEON_MAP.items():
        if start <= floor <= end:
            return dungeon_id
    return 10  # Fallback
일반 몬스터 스폰:


async def get_floor_monster(floor: int) -> Monster:
    dungeon_id = get_dungeon_for_floor(floor)

    if is_boss_floor(floor):
        # 보스 스폰
        boss_monsters = await Monster.filter(
            dungeon_spawn__dungeon_id=dungeon_id,
            is_boss_monster=True
        ).all()
        return random.choice(boss_monsters) if boss_monsters else fallback_boss
    else:
        # 일반 몬스터 스폰
        spawns = await DungeonSpawn.filter(dungeon_id=dungeon_id).all()
        monster = weighted_random_choice(spawns, key=lambda s: s.prob)
        return await Monster.get(id=monster.monster_id)
UI/UX Flow
타워 입장

/주간타워 실행
   ↓
[입장 안내 임베드]
━━━━━━━━━━━━━━━━━━━━━━
🗼 주간 타워
━━━━━━━━━━━━━━━━━━━━━━
현재 시즌: 시즌 3
최고 기록: 47층
현재 위치: 1층부터 시작

⚠️ 주의사항:
• 아이템 사용 불가
• 층 사이에만 스킬 변경 가능
• 도주 불가
• 사망 시 1층부터 재시작

[입장] [취소]
━━━━━━━━━━━━━━━━━━━━━━
층 클리어

✅ 15층 클리어!
━━━━━━━━━━━━━━━━━━━━━━
🎉 층별 보상
💎 경험치: +1,500
💰 골드: +750
🪙 타워 코인: +1

📊 현재 상태
❤️ HP: 2,450 / 3,200
📈 Lv.25

[다음 층 (16층)] [귀환]
━━━━━━━━━━━━━━━━━━━━━━
보스층 경고

⚠️ 보스층 도달! (20층)
━━━━━━━━━━━━━━━━━━━━━━
강력한 보스가 기다리고 있습니다.

🔥 보스 클리어 보너스: 2배 보상!

💡 팁: 층 사이에서 스킬을 변경할 수 있습니다.

[도전] [귀환]
━━━━━━━━━━━━━━━━━━━━━━
100층 클리어

🎊 축하합니다! 타워 정복! 🎊
━━━━━━━━━━━━━━━━━━━━━━
🗼 주간 타워 100층을 클리어했습니다!

🏆 완료 보상
💎 경험치: +50,000
💰 골드: +100,000
🪙 타워 코인: +50
👑 칭호: [타워 정복자]

[확인]
━━━━━━━━━━━━━━━━━━━━━━
Testing Strategy
Unit Tests
tests/unit/test_tower_restriction.py

아이템 제약 (타워 vs 일반 던전)
스킬 제약 (전투 중 vs 층 사이)
도주 제약
tests/unit/test_tower_service.py

보스층 판정 (is_boss_floor)
층→던전 매핑 (get_dungeon_for_floor)
보상 계산 (calculate_floor_reward)
Integration Tests
tests/integration/test_tower_flow.py
1층 → 10층 진행
보스층 스폰 확인
진행도 저장 확인
E2E Tests
tests/e2e/test_tower_journey.py
전체 입장 → 전투 → 층 클리어 → 귀환 흐름
제약 위반 시나리오 (아이템, 스킬, 도주)
Rollout Timeline
Week	Phase	Deliverables
1	Phase 1	타워 입장, 층별 진행, 진행도 저장
2	Phase 2	보스층, 제약 조건 완전 적용
3	Phase 3	층별 보상, UI 완성, 클리어 처리
4	Phase 4	시즌 시스템, 랭킹, 타워 상점
Total: 4주 (풀타임 기준)

Risk Mitigation
Risk	Mitigation
기존 던전 시스템 간섭	content_type 체크로 타워 로직 분기
제약 우회 가능성	다층 방어 (UI + Service + Command)
진행도 손실	매 층마다 DB 저장, 트랜잭션 보장
보스 난이도 불균형	초기 보스 풀 제한, 점진적 확대
시즌 리셋 실패	백업 + 롤백 스크립트, 수동 리셋 명령어
Reusable Patterns
기존 코드베이스에서 발견한 재사용 가능한 패턴:

Session Management: create_session(), end_session() - double-check locking 패턴
Repository Pattern: models/repos/ - 캐싱 + CRUD 추상화
Event Bus: service/event/event_bus.py - 업적/로그 연동
Guard Clause: if session and session.in_combat: raise - 제약 적용
Encounter Factory: EncounterFactory.roll_encounter_type() - 확률 기반 선택
Success Criteria
 /주간타워 명령어로 입장 가능
 1층부터 100층까지 정상 진행
 10층마다 보스 등장
 아이템 사용 불가 (에러 메시지 표시)
 층 사이에서만 스킬 변경 가능
 도주 불가 (에러 메시지 표시)
 사망 시 진행도 저장, 재입장 시 1층부터
 최고 기록 표시
 매주 월요일 00:00 자동 리셋
 /랭킹 명령어의 타워 탭으로 순위 확인
 타워 상점에서 코인으로 아이템 구매
Post-Implementation Tasks
밸런스 조정

층별 보상 배율 조정
보스 난이도 체크
타워 상점 가격 조정
추가 기능 (선택)

타워 일일 도전 (추가 보상)
타워 전용 업적
타워 클리어 기록 로그 (타임라인)
타워 층별 스킵 티켓 (타워 코인 소비)
문서화

docs/TODO.md 업데이트 (체크 완료)
docs/Tower.md 신규 작성 (타워 기획서)
API 문서 업데이트
최종 검증 절차
Phase 1 완료 후:

# 1. 타워 입장
/주간타워

# 2. 1층 전투 → 승리 → 2층 진행 확인
# 3. DB 확인
SELECT * FROM user_tower_progress WHERE user_id = <user_id>;
Phase 2 완료 후:

# 1. 10층 도달 → 보스 스폰 확인
# 2. 전투 중 /아이템사용 시도 → 에러 확인
# 3. 전투 중 /덱변경 시도 → 에러 확인
# 4. 층 사이 /덱변경 시도 → 성공 확인
Phase 3 완료 후:

# 1. 50층 클리어 → 보상 확인
# 2. 사망 → 진행도 저장 확인
# 3. 재입장 → 1층부터 시작 확인
# 4. 최고 기록 표시 확인 (50층)
Phase 4 완료 후:

# 1. 월요일 00:00 이후 자동 리셋 확인
# 2. /랭킹 → 🗼 타워 탭 → 상위 10명 표시
# 3. 10층 클리어 → 타워 상점 자동 열림 → 아이템 구매
# 4. 타워 코인 차감 확인