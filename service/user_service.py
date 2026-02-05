"""
UserService

사용자 생성, 초기화, 스탯 계산, 출석 체크 등을 담당합니다.
"""
import logging
from datetime import date
from typing import Optional

from models import User
from models.user_stats import UserStats
from models.user_skill_deck import UserSkillDeck
from config import USER_STATS, SKILL_DECK_SIZE
from exceptions import (
    UserNotFoundError,
    UserAlreadyExistsError,
    AlreadyAttendedError,
)
from service.collection_service import CollectionService
from service.skill_ownership_service import SkillOwnershipService

logger = logging.getLogger(__name__)


class UserService:
    """사용자 비즈니스 로직"""

    # 기본 스킬 덱 구성 (10개)
    # 공격 7 + 회복 2 + 버프 1의 균형잡힌 덱
    DEFAULT_SKILL_DECK = [
        1001,  # 슬롯 0: 강타 (100% 데미지)
        1001,  # 슬롯 1: 강타
        1001,  # 슬롯 2: 강타
        1002,  # 슬롯 3: 연속 베기 (60% x 2회)
        1002,  # 슬롯 4: 연속 베기
        1003,  # 슬롯 5: 급소 찌르기 (120% + 치명타 보너스)
        1003,  # 슬롯 6: 급소 찌르기
        2001,  # 슬롯 7: 응급 처치 (HP 15% 회복)
        2001,  # 슬롯 8: 응급 처치
        3005,  # 슬롯 9: 결의 (공격력/방어력 +15%)
    ]

    @staticmethod
    async def create_user(discord_id: int, username: str) -> User:
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
            attack=base_stats["attack"]
        )

        # UserStats 생성
        await UserStats.create(user=user)

        # 기본 스킬 덱 초기화
        await UserService._initialize_default_deck(user)

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
        - 결의 x1 (10%): 버프

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
        레벨 기반 기본 스탯 계산 (Balance.md 공식)

        Level 1-50:
        - HP = 100 + (level × 20)
        - Attack = 10 + (level × 2)
        - AP_Attack = 5 + (level × 1.5)
        - AD_Defense = 5 + level
        - AP_Defense = 5 + level

        Level 51+:
        - 고레벨 성장 공식 적용

        Args:
            level: 사용자 레벨

        Returns:
            기본 스탯 딕셔너리
        """
        if level <= 50:
            hp = 100 + (level * 20)
            attack = 10 + (level * 2)
            ap_attack = 5 + int(level * 1.5)
            ad_defense = 5 + level
            ap_defense = 5 + level
        else:
            # 고레벨 공식 (Lv.51+)
            base_level = 50
            over_level = level - 50
            hp = (100 + (base_level * 20) +
                  (over_level * 30) +
                  int(over_level ** 2 / 10))
            attack = (10 + (base_level * 2) +
                      (over_level * 3) +
                      int(over_level / 5))
            ap_attack = (5 + int(base_level * 1.5) +
                         int(over_level * 2.5) +
                         int(over_level / 5))
            ad_defense = (5 + base_level +
                          int(over_level * 1.5) +
                          int(over_level / 8))
            ap_defense = (5 + base_level +
                          int(over_level * 1.5) +
                          int(over_level / 8))

        return {
            "hp": hp,
            "attack": attack,
            "ap_attack": ap_attack,
            "ad_defense": ad_defense,
            "ap_defense": ap_defense,
            "speed": USER_STATS.INITIAL_SPEED
        }

    @staticmethod
    async def get_user_stats(user: User) -> Optional[UserStats]:
        """
        사용자 스탯 조회

        Args:
            user: 대상 사용자

        Returns:
            UserStats 객체 또는 None
        """
        return await UserStats.get_or_none(user=user)

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
        stats = await UserStats.get_or_none(user=user)
        if not stats:
            stats = await UserStats.create(user=user)

        today = date.today()

        # 이미 출석한 경우
        if stats.last_attendance == today:
            raise AlreadyAttendedError()

        # 연속 출석 계산
        if stats.last_attendance and (today - stats.last_attendance).days == 1:
            stats.attendance_streak += 1
        else:
            stats.attendance_streak = 1

        stats.last_attendance = today

        # 보상 계산 (연속 출석 보너스)
        base_gold = 100
        streak_bonus = min(stats.attendance_streak, 7) * 50  # 최대 7일 보너스
        total_gold = base_gold + streak_bonus

        stats.gold += total_gold
        await stats.save()

        logger.info(f"User {user.id} attendance: streak={stats.attendance_streak}, gold={total_gold}")

        return {
            "success": True,
            "message": f"출석 완료! {total_gold} 골드를 획득했습니다.",
            "streak": stats.attendance_streak,
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
        stats = await UserStats.get_or_none(user=user)
        if not stats:
            stats = await UserStats.create(user=user)

        stats.experience += amount
        old_level = user.level
        new_level = old_level

        # 레벨업 체크
        while stats.experience >= UserService._get_required_exp(new_level + 1):
            stats.experience -= UserService._get_required_exp(new_level + 1)
            new_level += 1
            stats.stat_points += USER_STATS.STAT_POINTS_PER_LEVEL

        leveled_up = new_level > old_level

        if leveled_up:
            user.level = new_level
            base_stats = UserService.calculate_base_stats(new_level)
            user.hp = base_stats["hp"]
            user.attack = base_stats["attack"]
            # HP 비율 유지
            hp_ratio = user.now_hp / UserService.calculate_base_stats(old_level)["hp"]
            user.now_hp = int(base_stats["hp"] * hp_ratio)
            await user.save()

        await stats.save()

        return {
            "leveled_up": leveled_up,
            "old_level": old_level,
            "new_level": new_level,
            "experience_gained": amount,
            "current_experience": stats.experience,
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
        if level <= 10:
            return 100 * level
        elif level <= 20:
            return 200 * level
        elif level <= 30:
            return 400 * level
        elif level <= 40:
            return 800 * level
        elif level <= 50:
            return 1600 * level
        elif level <= 60:
            return 2400 * level
        else:
            # 고레벨 구간
            return 3200 * level
