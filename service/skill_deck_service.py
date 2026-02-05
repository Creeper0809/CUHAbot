"""
SkillDeckService

스킬 덱 관리를 담당합니다.
"""
import logging
from typing import List, Optional

from models import User, Skill_Model
from models.user_skill_deck import UserSkillDeck
from config import SKILL_DECK_SIZE
from exceptions import (
    SkillNotFoundError,
    DeckSlotLimitError,
    DeckEmptyError,
    CombatRestrictionError,
)
from service.collection_service import CollectionService
from service.session import get_session

logger = logging.getLogger(__name__)


class SkillDeckService:
    """스킬 덱 비즈니스 로직"""

    @staticmethod
    async def set_skill(
        user: User,
        slot_index: int,
        skill_id: int
    ) -> UserSkillDeck:
        """
        특정 슬롯에 스킬 설정

        Args:
            user: 대상 사용자
            slot_index: 슬롯 인덱스 (0-9)
            skill_id: 스킬 ID

        Returns:
            UserSkillDeck 객체

        Raises:
            CombatRestrictionError: 전투 중 스킬 변경 시도
            DeckSlotLimitError: 슬롯 범위 초과
            SkillNotFoundError: 스킬을 찾을 수 없음
        """
        # 전투 중 체크
        session = get_session(user.discord_id)
        if session and session.in_combat:
            raise CombatRestrictionError("스킬 변경")

        # 슬롯 범위 체크
        if not 0 <= slot_index < SKILL_DECK_SIZE:
            raise DeckSlotLimitError(SKILL_DECK_SIZE)

        # 스킬 존재 확인
        skill = await Skill_Model.get_or_none(id=skill_id)
        if not skill:
            raise SkillNotFoundError(skill_id)

        # 기존 슬롯 업데이트 또는 생성
        deck_slot, created = await UserSkillDeck.update_or_create(
            user=user,
            slot_index=slot_index,
            defaults={"skill": skill}
        )

        # 도감에 스킬 등록
        await CollectionService.register_skill(user, skill_id)

        action = "created" if created else "updated"
        logger.info(f"User {user.id} {action} skill in slot {slot_index}: {skill_id}")
        return deck_slot

    @staticmethod
    async def get_deck(user: User) -> List[UserSkillDeck]:
        """
        전체 덱 조회

        Args:
            user: 대상 사용자

        Returns:
            UserSkillDeck 목록 (슬롯 순서대로)
        """
        return await UserSkillDeck.filter(user=user).order_by(
            "slot_index"
        ).prefetch_related("skill")

    @staticmethod
    async def get_deck_as_list(user: User) -> List[int]:
        """
        덱을 스킬 ID 리스트로 반환

        Args:
            user: 대상 사용자

        Returns:
            스킬 ID 리스트 (10개)
        """
        deck_slots = await SkillDeckService.get_deck(user)
        result = [0] * SKILL_DECK_SIZE

        for slot in deck_slots:
            if 0 <= slot.slot_index < SKILL_DECK_SIZE:
                result[slot.slot_index] = slot.skill_id

        return result

    @staticmethod
    async def validate_deck(user: User) -> bool:
        """
        덱이 유효한지 확인 (10슬롯 모두 채워짐)

        Args:
            user: 대상 사용자

        Returns:
            True if valid

        Raises:
            DeckEmptyError: 덱이 완전히 채워지지 않음
        """
        count = await UserSkillDeck.filter(user=user).count()
        if count < SKILL_DECK_SIZE:
            raise DeckEmptyError()
        return True

    @staticmethod
    async def load_deck_to_user(user: User) -> None:
        """
        DB에서 덱을 로드하여 User 런타임 필드에 설정

        Args:
            user: 대상 사용자
        """
        deck_list = await SkillDeckService.get_deck_as_list(user)
        user.equipped_skill = deck_list
        user.skill_queue = []  # 큐 초기화
        logger.debug(f"Loaded deck for user {user.id}: {deck_list}")

    @staticmethod
    async def clear_deck(user: User) -> int:
        """
        덱 전체 초기화

        Args:
            user: 대상 사용자

        Returns:
            삭제된 슬롯 수
        """
        session = get_session(user.discord_id)
        if session and session.in_combat:
            raise CombatRestrictionError("스킬 변경")

        deleted = await UserSkillDeck.filter(user=user).delete()
        logger.info(f"Cleared deck for user {user.id}: {deleted} slots")
        return deleted

    @staticmethod
    async def get_skill_count_in_deck(user: User, skill_id: int) -> int:
        """
        덱에서 특정 스킬의 슬롯 수 조회

        Args:
            user: 대상 사용자
            skill_id: 스킬 ID

        Returns:
            해당 스킬이 차지한 슬롯 수
        """
        return await UserSkillDeck.filter(
            user=user,
            skill_id=skill_id
        ).count()

    @staticmethod
    async def copy_deck(source_user: User, target_user: User) -> None:
        """
        덱 복사

        Args:
            source_user: 원본 사용자
            target_user: 대상 사용자
        """
        session = get_session(target_user.discord_id)
        if session and session.in_combat:
            raise CombatRestrictionError("스킬 변경")

        # 대상 덱 초기화
        await UserSkillDeck.filter(user=target_user).delete()

        # 원본 덱 복사
        source_deck = await SkillDeckService.get_deck(source_user)
        for slot in source_deck:
            await UserSkillDeck.create(
                user=target_user,
                slot_index=slot.slot_index,
                skill_id=slot.skill_id
            )

        logger.info(f"Copied deck from user {source_user.id} to user {target_user.id}")
