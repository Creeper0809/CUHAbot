"""
업적 진행 추적기 (Achievement Progress Tracker)

옵저버 패턴을 사용하여 게임 이벤트를 구독하고,
업적 진행도를 자동으로 업데이트합니다.
"""

import logging
from datetime import datetime
from typing import Any, Dict

from service.event import EventBus, GameEvent, GameEventType
from service.mail import MailService
from models.achievement import Achievement
from models.user_achievement import UserAchievement
from models.mail import MailType

logger = logging.getLogger(__name__)


class AchievementProgressTracker:
    """
    업적 진행 추적기 (옵저버)

    게임 이벤트를 구독하고, 해당 이벤트와 관련된 업적의 진행도를 자동으로 업데이트합니다.
    업적 완료 시 우편으로 보상을 발송합니다.
    """

    def __init__(self, event_bus: EventBus, mail_service: MailService = None):
        """
        Args:
            event_bus: 이벤트 버스
            mail_service: 우편 서비스 (없으면 자동 생성)
        """
        self.event_bus = event_bus
        self.mail_service = mail_service or MailService()
        self._register_listeners()
        logger.info("AchievementProgressTracker initialized")

    def _register_listeners(self) -> None:
        """이벤트 리스너 등록"""
        self.event_bus.subscribe(GameEventType.MONSTER_KILLED, self.on_monster_killed)
        self.event_bus.subscribe(GameEventType.COMBAT_WON, self.on_combat_won)
        self.event_bus.subscribe(GameEventType.DUNGEON_EXPLORED, self.on_dungeon_explored)
        self.event_bus.subscribe(GameEventType.DUNGEON_CLEARED, self.on_dungeon_cleared)
        self.event_bus.subscribe(GameEventType.GOLD_OBTAINED, self.on_gold_obtained)
        self.event_bus.subscribe(GameEventType.GOLD_CHANGED, self.on_gold_changed)
        self.event_bus.subscribe(GameEventType.LEVEL_UP, self.on_level_up)
        self.event_bus.subscribe(GameEventType.ITEM_OBTAINED, self.on_item_obtained)
        self.event_bus.subscribe(GameEventType.ITEM_USED, self.on_item_used)
        self.event_bus.subscribe(GameEventType.WIN_STREAK_UPDATED, self.on_win_streak_updated)
        logger.debug("Event listeners registered")

    async def on_monster_killed(self, event: GameEvent) -> None:
        """몬스터 처치 이벤트 핸들러"""
        user_id = event.user_id
        monster_id = event.data.get("monster_id")
        attribute = event.data.get("monster_attribute")
        is_boss = event.data.get("is_boss", False)

        # 전체 몬스터 처치
        await self._update_achievement(
            user_id=user_id,
            achievement_type="kill_total",
            increment=1
        )

        # 특정 몬스터 처치
        if monster_id:
            await self._update_achievement(
                user_id=user_id,
                achievement_type="kill_monster",
                filters={"monster_id": monster_id},
                increment=1
            )

        # 속성별 처치
        if attribute:
            await self._update_achievement(
                user_id=user_id,
                achievement_type="kill_attribute",
                filters={"attribute": attribute},
                increment=1
            )

        # 보스 처치
        if is_boss:
            await self._update_achievement(
                user_id=user_id,
                achievement_type="kill_boss",
                increment=1
            )

    async def on_combat_won(self, event: GameEvent) -> None:
        """전투 승리 이벤트 핸들러"""
        user_id = event.user_id
        is_flawless = event.data.get("is_flawless", False)
        is_fast = event.data.get("is_fast", False)
        turns = event.data.get("turns", 0)

        # 무상 승리 (체력 100%)
        if is_flawless:
            await self._update_achievement(
                user_id=user_id,
                achievement_type="win_flawless",
                increment=1
            )

        # 속전속결 (N턴 이내)
        if is_fast:
            await self._update_achievement(
                user_id=user_id,
                achievement_type="win_fast",
                filters={"turns": turns},
                increment=1
            )

    async def on_dungeon_explored(self, event: GameEvent) -> None:
        """던전 탐험 이벤트 핸들러"""
        user_id = event.user_id

        await self._update_achievement(
            user_id=user_id,
            achievement_type="dungeon_explore",
            increment=1
        )

    async def on_dungeon_cleared(self, event: GameEvent) -> None:
        """던전 클리어 이벤트 핸들러"""
        user_id = event.user_id
        dungeon_id = event.data.get("dungeon_id")

        if dungeon_id:
            await self._update_achievement(
                user_id=user_id,
                achievement_type="dungeon_clear",
                filters={"dungeon_id": dungeon_id},
                increment=1
            )

    async def on_gold_obtained(self, event: GameEvent) -> None:
        """골드 획득 이벤트 핸들러"""
        user_id = event.user_id
        gold_amount = event.data.get("gold_amount", 0)

        await self._update_achievement(
            user_id=user_id,
            achievement_type="gold_earned",
            increment=gold_amount
        )

    async def on_gold_changed(self, event: GameEvent) -> None:
        """보유 골드 변경 이벤트 핸들러"""
        user_id = event.user_id
        current_gold = event.data.get("current_gold", 0)

        # 보유 골드 업적은 set 방식 (누적이 아닌 현재값)
        await self._update_achievement(
            user_id=user_id,
            achievement_type="gold_owned",
            set_value=current_gold
        )

    async def on_level_up(self, event: GameEvent) -> None:
        """레벨업 이벤트 핸들러"""
        user_id = event.user_id
        new_level = event.data.get("new_level", 0)

        # 레벨 업적은 set 방식 (누적이 아닌 현재값)
        await self._update_achievement(
            user_id=user_id,
            achievement_type="level",
            set_value=new_level
        )

    async def on_item_obtained(self, event: GameEvent) -> None:
        """아이템 획득 이벤트 핸들러"""
        user_id = event.user_id
        quantity = event.data.get("quantity", 1)

        await self._update_achievement(
            user_id=user_id,
            achievement_type="item_collected",
            increment=quantity
        )

    async def on_item_used(self, event: GameEvent) -> None:
        """아이템 사용 이벤트 핸들러"""
        user_id = event.user_id
        item_type = event.data.get("item_type")
        quantity = event.data.get("quantity", 1)

        if item_type:
            await self._update_achievement(
                user_id=user_id,
                achievement_type="item_used",
                filters={"item_type": item_type},
                increment=quantity
            )

    async def on_win_streak_updated(self, event: GameEvent) -> None:
        """연승 갱신 이벤트 핸들러"""
        user_id = event.user_id
        win_streak = event.data.get("win_streak", 0)

        # 연승 업적은 set 방식 (현재 최고 연승 기록)
        await self._update_achievement(
            user_id=user_id,
            achievement_type="win_streak",
            set_value=win_streak
        )

    async def _update_achievement(
        self,
        user_id: int,
        achievement_type: str,
        increment: int = 0,
        set_value: int = None,
        filters: Dict[str, Any] = None
    ) -> None:
        """
        업적 진행도 업데이트

        Args:
            user_id: 유저 ID
            achievement_type: 업적 타입 (objective_config의 type)
            increment: 증가량 (누적형)
            set_value: 설정값 (절대값형 - 레벨, 보유 골드 등)
            filters: 추가 필터 (objective_config의 필드)
        """
        if filters is None:
            filters = {}

        # 모든 업적 조회 (Tortoise ORM은 JSONField 중첩 필터를 지원하지 않음)
        all_achievements = await Achievement.all()

        # Python에서 필터링
        achievements = []
        for achievement in all_achievements:
            if not achievement.objective_config:
                continue

            # 타입 확인
            if achievement.objective_config.get("type") != achievement_type:
                continue

            # 추가 필터 확인
            match = True
            for key, value in filters.items():
                if achievement.objective_config.get(key) != value:
                    match = False
                    break

            if match:
                achievements.append(achievement)

        for achievement in achievements:
            await self._process_achievement_progress(
                user_id=user_id,
                achievement=achievement,
                increment=increment,
                set_value=set_value
            )

    async def _process_achievement_progress(
        self,
        user_id: int,
        achievement: Achievement,
        increment: int = 0,
        set_value: int = None
    ) -> None:
        """
        개별 업적 진행도 처리

        Args:
            user_id: 유저 ID
            achievement: 업적
            increment: 증가량
            set_value: 설정값
        """
        # 선행 업적 확인 (티어 II/III는 이전 티어 완료 필요)
        if achievement.prerequisite_achievement_id:
            prerequisite = await UserAchievement.get_or_none(
                user_id=user_id,
                achievement_id=achievement.prerequisite_achievement_id,
                is_completed=True
            )
            if not prerequisite:
                # 선행 업적 미완료
                return

        # 유저 업적 조회 또는 생성
        user_achievement, created = await UserAchievement.get_or_create(
            user_id=user_id,
            achievement=achievement,
            defaults={
                "progress_required": achievement.objective_config.get("count", 1)
            }
        )

        if user_achievement.is_completed:
            # 이미 완료된 업적
            return

        # 진행도 업데이트
        if set_value is not None:
            # 절대값 설정 (레벨, 보유 골드 등)
            user_achievement.progress_current = set_value
        else:
            # 증가량 추가 (누적형)
            user_achievement.progress_current += increment

        # 완료 체크
        if user_achievement.progress_current >= user_achievement.progress_required:
            user_achievement.is_completed = True
            user_achievement.completed_at = datetime.now()

            # 우편 발송
            await self._send_achievement_mail(user_id, achievement)

            logger.info(
                f"Achievement completed: user_id={user_id}, "
                f"achievement_id={achievement.id}, name={achievement.name}"
            )

        await user_achievement.save()

    async def _send_achievement_mail(self, user_id: int, achievement: Achievement) -> None:
        """
        업적 달성 시 우편 발송

        Args:
            user_id: 유저 ID
            achievement: 달성한 업적
        """
        title = f"🏆 업적 달성: {achievement.full_name}"

        content = f"""축하합니다! 업적을 달성하셨습니다.

⚔️ {achievement.full_name}
{achievement.description}

보상을 수령해주세요!"""

        # 칭호 획득 메시지 추가 (티어 III)
        if achievement.title_name:
            content += f"\n\n🏆 칭호 획득: {achievement.title_name}"

        await self.mail_service.send_mail(
            user_id=user_id,
            mail_type=MailType.ACHIEVEMENT,
            sender="시스템",
            title=title,
            content=content,
            reward_config=achievement.reward_config
        )

        logger.debug(f"Achievement mail sent: user_id={user_id}, achievement_id={achievement.id}")
