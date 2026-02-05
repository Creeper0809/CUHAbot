"""
pytest 설정 및 공통 픽스처 정의
"""
import asyncio
import sys
from pathlib import Path
from typing import Generator, AsyncGenerator
from unittest.mock import MagicMock, AsyncMock

import pytest

# 프로젝트 루트를 Python 경로에 추가
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# =============================================================================
# pytest 설정
# =============================================================================


def pytest_configure(config):
    """pytest 설정"""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "e2e: marks tests as end-to-end tests"
    )


# =============================================================================
# 이벤트 루프 설정
# =============================================================================


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """세션 범위의 이벤트 루프"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# =============================================================================
# 데이터베이스 픽스처
# =============================================================================


@pytest.fixture(scope="function")
async def test_db() -> AsyncGenerator[None, None]:
    """
    테스트용 인메모리 SQLite 데이터베이스
    각 테스트 함수마다 새로운 DB 생성
    """
    from tortoise import Tortoise

    await Tortoise.init(
        db_url="sqlite://:memory:",
        modules={"models": ["models"]}
    )
    await Tortoise.generate_schemas()

    yield

    await Tortoise.close_connections()


@pytest.fixture(scope="module")
async def module_test_db() -> AsyncGenerator[None, None]:
    """
    모듈 범위의 테스트 데이터베이스
    통합 테스트에서 사용
    """
    from tortoise import Tortoise

    await Tortoise.init(
        db_url="sqlite://:memory:",
        modules={"models": ["models"]}
    )
    await Tortoise.generate_schemas()

    yield

    await Tortoise.close_connections()


# =============================================================================
# Mock 픽스처
# =============================================================================


@pytest.fixture
def mock_discord_user() -> MagicMock:
    """Mock Discord User 객체"""
    user = MagicMock()
    user.id = 123456789
    user.name = "TestUser"
    user.display_name = "Test User"
    user.mention = "<@123456789>"
    user.send = AsyncMock()
    return user


@pytest.fixture
def mock_discord_interaction() -> MagicMock:
    """Mock Discord Interaction 객체"""
    interaction = MagicMock()
    interaction.user = MagicMock()
    interaction.user.id = 123456789
    interaction.user.name = "TestUser"
    interaction.user.send = AsyncMock()
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()
    interaction.response.defer = AsyncMock()
    interaction.followup = MagicMock()
    interaction.followup.send = AsyncMock()
    interaction.channel = MagicMock()
    interaction.guild = MagicMock()
    return interaction


@pytest.fixture
def mock_discord_message() -> MagicMock:
    """Mock Discord Message 객체"""
    message = MagicMock()
    message.id = 987654321
    message.edit = AsyncMock()
    message.delete = AsyncMock()
    return message


# =============================================================================
# 게임 엔티티 팩토리 픽스처
# =============================================================================


@pytest.fixture
def user_factory():
    """테스트용 User 객체 생성 팩토리"""
    from models.users import User

    def _create_user(
        discord_id: int = 123456789,
        username: str = "TestUser",
        level: int = 1,
        hp: int = 300,
        now_hp: int | None = None,
        attack: int = 10,
        speed: int = 10,
    ) -> User:
        user = User(
            discord_id=discord_id,
            username=username,
            level=level,
            hp=hp,
            attack=attack,
        )
        user.now_hp = now_hp if now_hp is not None else hp
        user.speed = speed
        # 인스턴스별 런타임 필드 초기화
        user.status = []
        user.equipped_skill = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
        user.skill_queue = []
        return user

    return _create_user


@pytest.fixture
def monster_factory():
    """테스트용 Monster 객체 생성 팩토리"""
    from models.monster import Monster

    def _create_monster(
        name: str = "테스트 몬스터",
        description: str = "테스트용 몬스터입니다.",
        hp: int = 100,
        now_hp: int | None = None,
        attack: int = 10,
        speed: int = 10,
    ) -> Monster:
        monster = Monster(
            name=name,
            description=description,
            hp=hp,
            attack=attack,
        )
        monster.now_hp = now_hp if now_hp is not None else hp
        monster.speed = speed
        # 인스턴스별 런타임 필드 초기화
        monster.status = []
        monster.use_skill = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
        monster.skill_queue = []
        return monster

    return _create_monster


@pytest.fixture
def test_user(user_factory):
    """기본 테스트 유저"""
    return user_factory()


@pytest.fixture
def test_monster(monster_factory):
    """기본 테스트 몬스터"""
    return monster_factory()


# =============================================================================
# 세션 픽스처
# =============================================================================


@pytest.fixture
def mock_dungeon_session(test_user, test_monster, mock_discord_message):
    """Mock DungeonSession 객체"""
    from service.session import DungeonSession
    from models import Dungeon

    dungeon = MagicMock(spec=Dungeon)
    dungeon.id = 1
    dungeon.name = "테스트 던전"
    dungeon.description = "테스트용 던전입니다."

    session = DungeonSession(
        user=test_user,
        dungeon=dungeon,
        channel_message=mock_discord_message,
    )
    session.dm_message = mock_discord_message
    session.monster = test_monster

    return session


# =============================================================================
# 캐시 픽스처
# =============================================================================


@pytest.fixture
def mock_static_cache():
    """Mock 정적 캐시"""
    from models.repos import static_cache

    # 기존 캐시 백업
    original_dungeon_cache = static_cache.dungeon_cache.copy()
    original_monster_cache = static_cache.monster_cache_by_id.copy()
    original_item_cache = static_cache.item_cache.copy()
    original_skill_cache = static_cache.skill_cache_by_id.copy()
    original_spawn_info = static_cache.spawn_info.copy()

    # 테스트용 빈 캐시로 초기화
    static_cache.dungeon_cache.clear()
    static_cache.monster_cache_by_id.clear()
    static_cache.item_cache.clear()
    static_cache.skill_cache_by_id.clear()
    static_cache.spawn_info.clear()

    yield static_cache

    # 원래 캐시 복원
    static_cache.dungeon_cache.update(original_dungeon_cache)
    static_cache.monster_cache_by_id.update(original_monster_cache)
    static_cache.item_cache.update(original_item_cache)
    static_cache.skill_cache_by_id.update(original_skill_cache)
    static_cache.spawn_info.update(original_spawn_info)


# =============================================================================
# 유틸리티 함수
# =============================================================================


def assert_approx_equal(actual: float, expected: float, tolerance: float = 0.1):
    """근사값 비교 (확률 테스트용)"""
    assert abs(actual - expected) <= tolerance, (
        f"Expected {expected} ± {tolerance}, got {actual}"
    )
