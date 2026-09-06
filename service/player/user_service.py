"""
UserService

사용자 생성, 초기화, 스탯 계산, 출석 체크 등을 담당합니다.
"""
import logging
from datetime import date
from typing import Optional

from models import User
from models.user_skill_deck import UserSkillDeck
from config import USER_STATS, SKILL_DECK_SIZE, SKILL_ID, BALANCE_V2
from exceptions import (
    UserNotFoundError,
    UserAlreadyExistsError,
    AlreadyAttendedError,
)
from service.collection_service import CollectionService
from service.skill.skill_ownership_service import SkillOwnershipService

logger = logging.getLogger(__name__)


class UserService:
    """사용자 비즈니스 로직"""

    # 기본 스킬 덱 구성: 공격 7 + 회복 2 + 회복/해독 1.
    DEFAULT_SKILL_DECK = [
        SKILL_ID.BASIC_ATTACK_ID,  # 슬롯 0: 강타 (100% 데미지)
        SKILL_ID.BASIC_ATTACK_ID,  # 슬롯 1: 강타
        SKILL_ID.BASIC_ATTACK_ID,  # 슬롯 2: 강타
        1002,  # 연속 베기
        1002,
        1003,  # 급소 찌르기
        1003,
        2001,  # 응급 처치
        2001,
        2003,  # 간이 해독
    ]

    @staticmethod
    async def create_user(discord_id: int, username: str) -> User:
        from tortoise.transactions import in_transaction
        from service.player.starter_recovery import lock_registration

        async with in_transaction() as conn:
            await lock_registration(conn, discord_id)
            return await UserService._create_user(discord_id, username)

    @staticmethod
    async def _create_user(discord_id: int, username: str) -> User:
        """
        신규 사용자 생성 및 초기화

        Args:
            discord_id: Discord 사용자 ID
            username: 사용자 이름

        Returns:
            생성된 User 객체

        Raises:
            UserAlreadyExistsError: 이미 등록된 사용자
        """
        if await User.exists(discord_id=discord_id):
            raise UserAlreadyExistsError(discord_id)

        # 초기 스탯 계산
        base_stats = UserService.calculate_base_stats(USER_STATS.INITIAL_LEVEL)

        # User 생성
        user = await User.create(
            discord_id=discord_id,
            username=username,
            hp=base_stats["hp"],
            now_hp=base_stats["hp"],
            level=USER_STATS.INITIAL_LEVEL,
            attack=base_stats["attack"],
            ap_attack=base_stats["ap_attack"],
            defense=base_stats["ad_defense"],
            ap_defense=base_stats["ap_defense"],
            speed=base_stats["speed"],
            accuracy=base_stats["accuracy"],
            evasion=base_stats["evasion"],
            critical_rate=base_stats["critical_rate"],
            critical_damage=base_stats["critical_damage"],
        )

        # 기본 스킬 덱 초기화
        await UserService._initialize_default_deck(user)
        from models.game_system import UserStarterRecovery
        await UserStarterRecovery.create(user=user, hp_recovered=True)
        user.equipped_skill = list(UserService.DEFAULT_SKILL_DECK)

        logger.info(f"Created new user: {discord_id} ({username})")
        return user

    @staticmethod
    async def _initialize_default_deck(user: User) -> None:
        """
        기본 스킬 덱 초기화 (다양한 스킬 10개)

        초보자용 균형잡힌 덱:
        - 강타 x3 (30%): 기본 공격
        - 연속 베기 x2 (20%): 다단히트
        - 급소 찌르기 x2 (20%): 치명타 보너스
        - 응급 처치 x2 (20%): 회복
        - 간이 해독 x1 (10%): 회복/해독

        Args:
            user: 대상 사용자
        """
        # 기본 스킬 도감 등록 (중복 제거)
        unique_skills = set(UserService.DEFAULT_SKILL_DECK)
        for skill_id in unique_skills:
            await CollectionService.register_skill(user, skill_id)

        # 스킬 소유권 초기화 (덱에 필요한 수량만큼 지급)
        await SkillOwnershipService.initialize_for_new_user(
            user, UserService.DEFAULT_SKILL_DECK
        )

        # 스킬 덱 초기화
        for slot, skill_id in enumerate(UserService.DEFAULT_SKILL_DECK):
            await UserSkillDeck.create(
                user=user,
                slot_index=slot,
                skill_id=skill_id
            )
        logger.debug(f"Initialized default deck for user {user.id}: {UserService.DEFAULT_SKILL_DECK}")

    @staticmethod
    def calculate_base_stats(level: int) -> dict[str, int]:
        """
        레벨 기반 기본 스탯 계산

        Args:
            level: 사용자 레벨

        Returns:
            기본 스탯 딕셔너리
        """
        return BALANCE_V2.base_stats(level).as_dict()

    @staticmethod
    async def process_attendance(user: User) -> dict:
        """
        출석 체크 처리

        Args:
            user: 대상 사용자

        Returns:
            출석 결과 딕셔너리:
            - success: 성공 여부
            - message: 결과 메시지
            - streak: 연속 출석 일수
            - gold_earned: 획득 골드 (성공 시)

        Raises:
            AlreadyAttendedError: 이미 출석한 경우
        """
        today = date.today()

        # 이미 출석한 경우
        if user.last_attendance == today:
            raise AlreadyAttendedError()

        # 연속 출석 계산
        if user.last_attendance and (today - user.last_attendance).days == 1:
            user.attendance_streak += 1
        else:
            user.attendance_streak = 1

        user.last_attendance = today

        # 보상 계산 (연속 출석 보너스)
        base_gold = USER_STATS.ATTENDANCE_BASE_GOLD
        streak_bonus = min(user.attendance_streak, USER_STATS.ATTENDANCE_MAX_STREAK) * USER_STATS.ATTENDANCE_STREAK_BONUS
        total_gold = base_gold + streak_bonus

        user.gold += total_gold
        await user.save()

        logger.info(f"User {user.id} attendance: streak={user.attendance_streak}, gold={total_gold}")

        return {
            "success": True,
            "message": f"출석 완료! {total_gold} 골드를 획득했습니다.",
            "streak": user.attendance_streak,
            "gold_earned": total_gold
        }

    @staticmethod
    async def add_experience(user: User, amount: int) -> dict:
        """
        경험치 추가 및 레벨업 처리

        Args:
            user: 대상 사용자
            amount: 추가할 경험치

        Returns:
            레벨업 결과 딕셔너리
        """
        old_level = user.level
        from service.economy.reward_service import RewardService

        result = await RewardService.apply_rewards(user, amount, 0)
        new_level = user.level

        # RewardService owns the cumulative EXP, stat update, and persistence contract.
        leveled_up = result.level_up is not None

        return {
            "leveled_up": leveled_up,
            "old_level": old_level,
            "new_level": new_level,
            "experience_gained": amount,
            "current_experience": user.exp,
            "stat_points_gained": (new_level - old_level) * USER_STATS.STAT_POINTS_PER_LEVEL
        }

    @staticmethod
    def _get_required_exp(level: int) -> int:
        """
        특정 레벨 달성에 필요한 경험치 계산

        Args:
            level: 목표 레벨

        Returns:
            필요 경험치
        """
        from service.economy.reward_service import get_exp_to_next_level

        return get_exp_to_next_level(max(1, level - 1))
