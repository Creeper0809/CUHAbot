"""
SkillOwnershipService

스킬 소유 및 수량 관리를 담당합니다.
스킬 덱에 장착할 때 수량을 소모하고, 해제하면 수량을 복구합니다.
"""
import logging
from typing import Dict, List, Optional

from models import User, Skill_Model
from models.user_owned_skill import UserOwnedSkill
from exceptions import InsufficientSkillError, SkillNotFoundError
from service.collection_service import CollectionService

logger = logging.getLogger(__name__)


class SkillOwnershipService:
    """스킬 소유 비즈니스 로직"""

    @staticmethod
    async def get_owned_skill(user: User, skill_id: int) -> Optional[UserOwnedSkill]:
        """
        소유한 스킬 정보 조회

        Args:
            user: 대상 사용자
            skill_id: 스킬 ID

        Returns:
            UserOwnedSkill 또는 None
        """
        return await UserOwnedSkill.get_or_none(user=user, skill_id=skill_id)

    @staticmethod
    async def get_all_owned_skills(user: User) -> List[UserOwnedSkill]:
        """
        모든 소유 스킬 목록 조회

        Args:
            user: 대상 사용자

        Returns:
            소유 스킬 목록
        """
        return await UserOwnedSkill.filter(user=user).prefetch_related("skill")

    @staticmethod
    async def get_available_count(user: User, skill_id: int) -> int:
        """
        장착 가능한 스킬 수량 조회

        Args:
            user: 대상 사용자
            skill_id: 스킬 ID

        Returns:
            장착 가능한 수량 (보유 - 장착)
        """
        owned = await SkillOwnershipService.get_owned_skill(user, skill_id)
        if not owned:
            return 0
        return owned.available_count

    @staticmethod
    async def add_skill(user: User, skill_id: int, quantity: int = 1) -> UserOwnedSkill:
        """
        스킬 추가 (획득/구매)

        Args:
            user: 대상 사용자
            skill_id: 스킬 ID
            quantity: 추가할 수량

        Returns:
            UserOwnedSkill 객체

        Raises:
            SkillNotFoundError: 존재하지 않는 스킬
        """
        skill = await Skill_Model.get_or_none(id=skill_id)
        if not skill:
            raise SkillNotFoundError(skill_id)

        owned, created = await UserOwnedSkill.get_or_create(
            user=user,
            skill=skill,
            defaults={"quantity": quantity, "equipped_count": 0}
        )

        if not created:
            owned.quantity += quantity
            await owned.save()

        # 도감에 등록 (이미 등록된 경우 무시됨)
        await CollectionService.register_skill(user, skill_id)

        action = "added" if created else "increased"
        logger.info(
            f"User {user.id} {action} skill {skill_id}: "
            f"qty={owned.quantity}, equipped={owned.equipped_count}"
        )
        return owned

    @staticmethod
    async def remove_skill(user: User, skill_id: int, quantity: int = 1) -> bool:
        """
        스킬 제거 (판매/소모)

        Args:
            user: 대상 사용자
            skill_id: 스킬 ID
            quantity: 제거할 수량

        Returns:
            성공 여부

        Raises:
            InsufficientSkillError: 수량 부족
        """
        owned = await SkillOwnershipService.get_owned_skill(user, skill_id)
        if not owned:
            skill = await Skill_Model.get_or_none(id=skill_id)
            skill_name = skill.name if skill else f"스킬 #{skill_id}"
            raise InsufficientSkillError(skill_name, quantity, 0)

        if owned.available_count < quantity:
            skill = await Skill_Model.get_or_none(id=skill_id)
            skill_name = skill.name if skill else f"스킬 #{skill_id}"
            raise InsufficientSkillError(skill_name, quantity, owned.available_count)

        owned.quantity -= quantity
        if owned.quantity <= 0:
            await owned.delete()
        else:
            await owned.save()

        logger.info(f"User {user.id} removed skill {skill_id}: qty=-{quantity}")
        return True

    @staticmethod
    async def equip_skill(user: User, skill_id: int, count: int = 1) -> bool:
        """
        스킬 장착 (수량 소모)

        Args:
            user: 대상 사용자
            skill_id: 스킬 ID
            count: 장착할 슬롯 수

        Returns:
            성공 여부

        Raises:
            InsufficientSkillError: 수량 부족
        """
        owned = await SkillOwnershipService.get_owned_skill(user, skill_id)
        if not owned:
            skill = await Skill_Model.get_or_none(id=skill_id)
            skill_name = skill.name if skill else f"스킬 #{skill_id}"
            raise InsufficientSkillError(skill_name, count, 0)

        if owned.available_count < count:
            skill = await Skill_Model.get_or_none(id=skill_id)
            skill_name = skill.name if skill else f"스킬 #{skill_id}"
            raise InsufficientSkillError(skill_name, count, owned.available_count)

        owned.equipped_count += count
        await owned.save()

        logger.debug(
            f"User {user.id} equipped skill {skill_id}: "
            f"equipped={owned.equipped_count}/{owned.quantity}"
        )
        return True

    @staticmethod
    async def unequip_skill(user: User, skill_id: int, count: int = 1) -> bool:
        """
        스킬 장착 해제 (수량 복구)

        Args:
            user: 대상 사용자
            skill_id: 스킬 ID
            count: 해제할 슬롯 수

        Returns:
            성공 여부
        """
        owned = await SkillOwnershipService.get_owned_skill(user, skill_id)
        if not owned:
            return False

        owned.equipped_count = max(0, owned.equipped_count - count)
        await owned.save()

        logger.debug(
            f"User {user.id} unequipped skill {skill_id}: "
            f"equipped={owned.equipped_count}/{owned.quantity}"
        )
        return True

    @staticmethod
    async def sync_equipped_count(user: User, deck: List[int]) -> None:
        """
        덱 기반으로 장착 수량 동기화

        Args:
            user: 대상 사용자
            deck: 현재 덱 (스킬 ID 리스트)
        """
        # 덱에서 각 스킬 수량 계산
        deck_counts: Dict[int, int] = {}
        for skill_id in deck:
            if skill_id != 0:
                deck_counts[skill_id] = deck_counts.get(skill_id, 0) + 1

        # 모든 소유 스킬의 equipped_count 업데이트
        owned_skills = await SkillOwnershipService.get_all_owned_skills(user)
        for owned in owned_skills:
            expected_equipped = deck_counts.get(owned.skill_id, 0)
            if owned.equipped_count != expected_equipped:
                owned.equipped_count = expected_equipped
                await owned.save()
                logger.debug(
                    f"User {user.id} synced skill {owned.skill_id}: "
                    f"equipped={expected_equipped}"
                )

    @staticmethod
    async def can_change_deck(
        user: User,
        current_deck: List[int],
        new_deck: List[int]
    ) -> tuple[bool, Optional[str]]:
        """
        덱 변경 가능 여부 확인

        Args:
            user: 대상 사용자
            current_deck: 현재 덱
            new_deck: 변경하려는 덱

        Returns:
            (가능 여부, 에러 메시지)
        """
        # 현재 덱 수량
        current_counts: Dict[int, int] = {}
        for skill_id in current_deck:
            if skill_id != 0:
                current_counts[skill_id] = current_counts.get(skill_id, 0) + 1

        # 새 덱 수량
        new_counts: Dict[int, int] = {}
        for skill_id in new_deck:
            if skill_id != 0:
                new_counts[skill_id] = new_counts.get(skill_id, 0) + 1

        # 추가로 필요한 스킬 확인
        for skill_id, new_count in new_counts.items():
            # 강타(1001)는 항상 사용 가능
            if skill_id == 1001:
                continue

            current_count = current_counts.get(skill_id, 0)
            additional_needed = new_count - current_count

            if additional_needed > 0:
                available = await SkillOwnershipService.get_available_count(
                    user, skill_id
                )
                if available < additional_needed:
                    skill = await Skill_Model.get_or_none(id=skill_id)
                    skill_name = skill.name if skill else f"#{skill_id}"
                    return False, (
                        f"'{skill_name}' 스킬이 부족합니다. "
                        f"(필요: {additional_needed}, 보유: {available})"
                    )

        return True, None

    @staticmethod
    async def apply_deck_change(
        user: User,
        current_deck: List[int],
        new_deck: List[int]
    ) -> None:
        """
        덱 변경 적용 (장착 수량 업데이트)

        Args:
            user: 대상 사용자
            current_deck: 현재 덱
            new_deck: 새 덱
        """
        # 현재 덱 수량
        current_counts: Dict[int, int] = {}
        for skill_id in current_deck:
            if skill_id != 0:
                current_counts[skill_id] = current_counts.get(skill_id, 0) + 1

        # 새 덱 수량
        new_counts: Dict[int, int] = {}
        for skill_id in new_deck:
            if skill_id != 0:
                new_counts[skill_id] = new_counts.get(skill_id, 0) + 1

        # 모든 관련 스킬 ID
        all_skill_ids = set(current_counts.keys()) | set(new_counts.keys())

        for skill_id in all_skill_ids:
            # 강타(1001)는 장착 수량 관리 제외
            if skill_id == 1001:
                continue

            current_count = current_counts.get(skill_id, 0)
            new_count = new_counts.get(skill_id, 0)
            diff = new_count - current_count

            if diff > 0:
                # 추가 장착
                await SkillOwnershipService.equip_skill(user, skill_id, diff)
            elif diff < 0:
                # 장착 해제
                await SkillOwnershipService.unequip_skill(user, skill_id, -diff)

        logger.info(f"User {user.id} deck change applied")

    @staticmethod
    async def initialize_for_new_user(user: User, default_deck: List[int]) -> None:
        """
        신규 유저 초기화 (기본 스킬 지급)

        Args:
            user: 신규 사용자
            default_deck: 기본 덱 구성
        """
        # 기본 덱에 필요한 스킬 수량 계산
        skill_counts: Dict[int, int] = {}
        for skill_id in default_deck:
            if skill_id != 0:
                skill_counts[skill_id] = skill_counts.get(skill_id, 0) + 1

        # 스킬 지급 및 장착
        for skill_id, count in skill_counts.items():
            await SkillOwnershipService.add_skill(user, skill_id, count)
            await SkillOwnershipService.equip_skill(user, skill_id, count)

        logger.info(f"User {user.id} initialized with default skills")

    @staticmethod
    async def migrate_existing_user(user: User, current_deck: List[int]) -> None:
        """
        기존 유저 마이그레이션 (현재 덱 기준으로 스킬 소유 데이터 생성)

        Args:
            user: 기존 사용자
            current_deck: 현재 장착된 덱
        """
        # 이미 마이그레이션되었는지 확인
        existing = await UserOwnedSkill.filter(user=user).count()
        if existing > 0:
            return

        # 현재 덱에 필요한 스킬 수량 계산
        skill_counts: Dict[int, int] = {}
        for skill_id in current_deck:
            if skill_id != 0:
                skill_counts[skill_id] = skill_counts.get(skill_id, 0) + 1

        # 스킬 지급 (현재 덱 수량 + 여유분 1개씩)
        for skill_id, count in skill_counts.items():
            bonus = 1  # 여유분
            await SkillOwnershipService.add_skill(user, skill_id, count + bonus)
            await SkillOwnershipService.equip_skill(user, skill_id, count)

        logger.info(f"User {user.id} migrated with current deck skills")
