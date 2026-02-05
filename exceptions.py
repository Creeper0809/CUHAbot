"""
CUHABot 커스텀 예외 클래스 정의

모든 예외는 CUHABotError를 상속받아 일관된 에러 처리를 제공합니다.
"""


class CUHABotError(Exception):
    """CUHABot 기본 예외 클래스"""

    def __init__(self, message: str = "알 수 없는 오류가 발생했습니다"):
        self.message = message
        super().__init__(self.message)


# =============================================================================
# 사용자 관련 예외
# =============================================================================


class UserNotFoundError(CUHABotError):
    """사용자를 찾을 수 없음"""

    def __init__(self, user_id: int):
        self.user_id = user_id
        super().__init__(f"사용자를 찾을 수 없습니다: {user_id}")


class UserAlreadyExistsError(CUHABotError):
    """이미 등록된 사용자"""

    def __init__(self, user_id: int):
        self.user_id = user_id
        super().__init__(f"이미 등록된 사용자입니다: {user_id}")


class UserNotRegisteredError(CUHABotError):
    """미등록 사용자"""

    def __init__(self, user_id: int):
        self.user_id = user_id
        super().__init__("먼저 등록해주세요. /등록 명령어를 사용하세요.")


# =============================================================================
# 던전 관련 예외
# =============================================================================


class DungeonNotFoundError(CUHABotError):
    """던전을 찾을 수 없음"""

    def __init__(self, dungeon_id: int):
        self.dungeon_id = dungeon_id
        super().__init__(f"던전을 찾을 수 없습니다: {dungeon_id}")


class DungeonSessionNotFoundError(CUHABotError):
    """던전 세션을 찾을 수 없음"""

    def __init__(self, user_id: int):
        self.user_id = user_id
        super().__init__("활성화된 던전 세션이 없습니다.")


class DungeonSessionAlreadyExistsError(CUHABotError):
    """이미 던전 세션이 존재함"""

    def __init__(self, user_id: int):
        self.user_id = user_id
        super().__init__("이미 던전 탐험 중입니다.")


# =============================================================================
# 몬스터 관련 예외
# =============================================================================


class MonsterNotFoundError(CUHABotError):
    """몬스터를 찾을 수 없음"""

    def __init__(self, monster_id: int):
        self.monster_id = monster_id
        super().__init__(f"몬스터를 찾을 수 없습니다: {monster_id}")


class MonsterSpawnNotFoundError(CUHABotError):
    """몬스터 스폰 정보를 찾을 수 없음"""

    def __init__(self, dungeon_id: int):
        self.dungeon_id = dungeon_id
        super().__init__(f"던전 {dungeon_id}에 스폰 가능한 몬스터가 없습니다.")


# =============================================================================
# 아이템 관련 예외
# =============================================================================


class ItemNotFoundError(CUHABotError):
    """아이템을 찾을 수 없음"""

    def __init__(self, item_id: int):
        self.item_id = item_id
        super().__init__(f"아이템을 찾을 수 없습니다: {item_id}")


class InsufficientItemError(CUHABotError):
    """아이템 수량 부족"""

    def __init__(self, item_name: str, required: int, current: int):
        self.item_name = item_name
        self.required = required
        self.current = current
        super().__init__(f"{item_name}이(가) 부족합니다. (필요: {required}, 보유: {current})")


class ItemNotEquippableError(CUHABotError):
    """장착 불가능한 아이템"""

    def __init__(self, item_name: str):
        self.item_name = item_name
        super().__init__(f"{item_name}은(는) 장착할 수 없는 아이템입니다.")


# =============================================================================
# 스킬 관련 예외
# =============================================================================


class SkillNotFoundError(CUHABotError):
    """스킬을 찾을 수 없음"""

    def __init__(self, skill_id: int):
        self.skill_id = skill_id
        super().__init__(f"스킬을 찾을 수 없습니다: {skill_id}")


class SkillComponentNotFoundError(CUHABotError):
    """스킬 컴포넌트를 찾을 수 없음"""

    def __init__(self, component_tag: str):
        self.component_tag = component_tag
        super().__init__(f"스킬 컴포넌트를 찾을 수 없습니다: {component_tag}")


class InvalidSkillConfigError(CUHABotError):
    """잘못된 스킬 설정"""

    def __init__(self, skill_name: str, reason: str):
        self.skill_name = skill_name
        self.reason = reason
        super().__init__(f"스킬 '{skill_name}' 설정 오류: {reason}")


# =============================================================================
# 전투 관련 예외
# =============================================================================


class CombatError(CUHABotError):
    """전투 관련 기본 예외"""
    pass


class CombatNotInProgressError(CombatError):
    """전투 중이 아님"""

    def __init__(self):
        super().__init__("현재 전투 중이 아닙니다.")


class CombatAlreadyInProgressError(CombatError):
    """이미 전투 중"""

    def __init__(self):
        super().__init__("이미 전투 중입니다.")


class CombatRestrictionError(CombatError):
    """전투 중 제한된 행동"""

    def __init__(self, action: str):
        self.action = action
        super().__init__(f"전투 중에는 {action}을(를) 할 수 없습니다.")


class InvalidTargetError(CombatError):
    """잘못된 대상"""

    def __init__(self, reason: str = "유효하지 않은 대상입니다"):
        super().__init__(reason)


# =============================================================================
# 콘텐츠 제한 예외
# =============================================================================


class ContentRestrictionError(CUHABotError):
    """콘텐츠별 제한 사항"""

    def __init__(self, content_name: str, restriction: str):
        self.content_name = content_name
        self.restriction = restriction
        super().__init__(f"{content_name}에서는 {restriction}")


class WeeklyTowerRestrictionError(ContentRestrictionError):
    """주간 타워 제한"""

    def __init__(self, restriction: str):
        super().__init__("주간 타워", restriction)


# =============================================================================
# 덱 관련 예외
# =============================================================================


class DeckError(CUHABotError):
    """덱 관련 기본 예외"""
    pass


class DeckSlotLimitError(DeckError):
    """덱 슬롯 초과"""

    def __init__(self, max_slots: int = 10):
        self.max_slots = max_slots
        super().__init__(f"스킬 슬롯은 최대 {max_slots}개입니다.")


class DeckEmptyError(DeckError):
    """덱이 비어있음"""

    def __init__(self):
        super().__init__("덱에 스킬이 없습니다. 스킬을 장착해주세요.")


# =============================================================================
# 자원 관련 예외
# =============================================================================


class InsufficientResourceError(CUHABotError):
    """자원 부족 (골드, MP 등)"""

    def __init__(self, resource_name: str, required: int, current: int):
        self.resource_name = resource_name
        self.required = required
        self.current = current
        super().__init__(
            f"{resource_name}이(가) 부족합니다. (필요: {required}, 보유: {current})"
        )


class InsufficientGoldError(InsufficientResourceError):
    """골드 부족"""

    def __init__(self, required: int, current: int):
        super().__init__("골드", required, current)


class InsufficientMPError(InsufficientResourceError):
    """MP 부족"""

    def __init__(self, required: int, current: int):
        super().__init__("MP", required, current)


# =============================================================================
# 상태 관련 예외
# =============================================================================


class InvalidStateError(CUHABotError):
    """잘못된 상태"""

    def __init__(self, expected_state: str, current_state: str):
        self.expected_state = expected_state
        self.current_state = current_state
        super().__init__(
            f"잘못된 상태입니다. (예상: {expected_state}, 현재: {current_state})"
        )


class EntityDeadError(CUHABotError):
    """엔티티 사망 상태"""

    def __init__(self, entity_name: str):
        self.entity_name = entity_name
        super().__init__(f"{entity_name}은(는) 이미 사망했습니다.")


# =============================================================================
# 캐시 관련 예외
# =============================================================================


class CacheNotInitializedError(CUHABotError):
    """캐시 미초기화"""

    def __init__(self, cache_name: str):
        self.cache_name = cache_name
        super().__init__(f"{cache_name} 캐시가 초기화되지 않았습니다.")


class CacheKeyNotFoundError(CUHABotError):
    """캐시 키 없음"""

    def __init__(self, cache_name: str, key: str):
        self.cache_name = cache_name
        self.key = key
        super().__init__(f"{cache_name}에서 '{key}'를 찾을 수 없습니다.")
