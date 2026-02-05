"""
exceptions.py 유닛 테스트
"""
import pytest

from exceptions import (
    CUHABotError,
    UserNotFoundError,
    UserAlreadyExistsError,
    UserNotRegisteredError,
    DungeonNotFoundError,
    MonsterNotFoundError,
    ItemNotFoundError,
    SkillNotFoundError,
    CombatRestrictionError,
    DeckSlotLimitError,
    InsufficientGoldError,
    InvalidStateError,
)


class TestCUHABotError:
    """기본 예외 클래스 테스트"""

    def test_default_message(self):
        """기본 메시지 테스트"""
        error = CUHABotError()
        assert error.message == "알 수 없는 오류가 발생했습니다"
        assert str(error) == "알 수 없는 오류가 발생했습니다"

    def test_custom_message(self):
        """커스텀 메시지 테스트"""
        error = CUHABotError("커스텀 에러 메시지")
        assert error.message == "커스텀 에러 메시지"
        assert str(error) == "커스텀 에러 메시지"

    def test_inheritance(self):
        """상속 관계 테스트"""
        error = CUHABotError()
        assert isinstance(error, Exception)


class TestUserNotFoundError:
    """사용자 미발견 예외 테스트"""

    def test_user_id_stored(self):
        """user_id 저장 테스트"""
        error = UserNotFoundError(123456789)
        assert error.user_id == 123456789

    def test_message_format(self):
        """메시지 포맷 테스트"""
        error = UserNotFoundError(123456789)
        assert "123456789" in str(error)
        assert "찾을 수 없습니다" in str(error)

    def test_inheritance(self):
        """상속 관계 테스트"""
        error = UserNotFoundError(123)
        assert isinstance(error, CUHABotError)


class TestUserAlreadyExistsError:
    """중복 사용자 예외 테스트"""

    def test_user_id_stored(self):
        """user_id 저장 테스트"""
        error = UserAlreadyExistsError(123456789)
        assert error.user_id == 123456789

    def test_message_format(self):
        """메시지 포맷 테스트"""
        error = UserAlreadyExistsError(123456789)
        assert "이미 등록된" in str(error)


class TestUserNotRegisteredError:
    """미등록 사용자 예외 테스트"""

    def test_user_id_stored(self):
        """user_id 저장 테스트"""
        error = UserNotRegisteredError(123456789)
        assert error.user_id == 123456789

    def test_message_contains_help(self):
        """도움말 메시지 포함 테스트"""
        error = UserNotRegisteredError(123456789)
        assert "/등록" in str(error)


class TestDungeonNotFoundError:
    """던전 미발견 예외 테스트"""

    def test_dungeon_id_stored(self):
        """dungeon_id 저장 테스트"""
        error = DungeonNotFoundError(1)
        assert error.dungeon_id == 1

    def test_message_format(self):
        """메시지 포맷 테스트"""
        error = DungeonNotFoundError(99)
        assert "99" in str(error)
        assert "던전" in str(error)


class TestMonsterNotFoundError:
    """몬스터 미발견 예외 테스트"""

    def test_monster_id_stored(self):
        """monster_id 저장 테스트"""
        error = MonsterNotFoundError(1)
        assert error.monster_id == 1


class TestItemNotFoundError:
    """아이템 미발견 예외 테스트"""

    def test_item_id_stored(self):
        """item_id 저장 테스트"""
        error = ItemNotFoundError(100)
        assert error.item_id == 100


class TestSkillNotFoundError:
    """스킬 미발견 예외 테스트"""

    def test_skill_id_stored(self):
        """skill_id 저장 테스트"""
        error = SkillNotFoundError(1)
        assert error.skill_id == 1


class TestCombatRestrictionError:
    """전투 제한 예외 테스트"""

    def test_action_stored(self):
        """action 저장 테스트"""
        error = CombatRestrictionError("아이템 사용")
        assert error.action == "아이템 사용"

    def test_message_format(self):
        """메시지 포맷 테스트"""
        error = CombatRestrictionError("스킬 변경")
        assert "전투 중에는" in str(error)
        assert "스킬 변경" in str(error)


class TestDeckSlotLimitError:
    """덱 슬롯 초과 예외 테스트"""

    def test_default_max_slots(self):
        """기본 최대 슬롯 테스트"""
        error = DeckSlotLimitError()
        assert error.max_slots == 10

    def test_custom_max_slots(self):
        """커스텀 최대 슬롯 테스트"""
        error = DeckSlotLimitError(max_slots=15)
        assert error.max_slots == 15

    def test_message_format(self):
        """메시지 포맷 테스트"""
        error = DeckSlotLimitError()
        assert "10" in str(error)
        assert "최대" in str(error)


class TestInsufficientGoldError:
    """골드 부족 예외 테스트"""

    def test_values_stored(self):
        """값 저장 테스트"""
        error = InsufficientGoldError(required=1000, current=500)
        assert error.required == 1000
        assert error.current == 500
        assert error.resource_name == "골드"

    def test_message_format(self):
        """메시지 포맷 테스트"""
        error = InsufficientGoldError(required=1000, current=500)
        assert "1000" in str(error)
        assert "500" in str(error)
        assert "부족" in str(error)


class TestInvalidStateError:
    """잘못된 상태 예외 테스트"""

    def test_states_stored(self):
        """상태값 저장 테스트"""
        error = InvalidStateError(expected_state="IDLE", current_state="COMBAT")
        assert error.expected_state == "IDLE"
        assert error.current_state == "COMBAT"

    def test_message_format(self):
        """메시지 포맷 테스트"""
        error = InvalidStateError(expected_state="IDLE", current_state="COMBAT")
        assert "IDLE" in str(error)
        assert "COMBAT" in str(error)


class TestExceptionHierarchy:
    """예외 계층 구조 테스트"""

    def test_all_inherit_from_cuhabot_error(self):
        """모든 예외가 CUHABotError를 상속하는지 테스트"""
        exceptions = [
            UserNotFoundError(1),
            UserAlreadyExistsError(1),
            UserNotRegisteredError(1),
            DungeonNotFoundError(1),
            MonsterNotFoundError(1),
            ItemNotFoundError(1),
            SkillNotFoundError(1),
            CombatRestrictionError("test"),
            DeckSlotLimitError(),
            InsufficientGoldError(100, 50),
            InvalidStateError("a", "b"),
        ]

        for exc in exceptions:
            assert isinstance(exc, CUHABotError), f"{type(exc).__name__}가 CUHABotError를 상속하지 않음"

    def test_can_catch_with_base_class(self):
        """기본 클래스로 잡을 수 있는지 테스트"""
        with pytest.raises(CUHABotError):
            raise UserNotFoundError(1)

        with pytest.raises(CUHABotError):
            raise CombatRestrictionError("test")
