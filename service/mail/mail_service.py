"""
우편 서비스

업적 보상, 시스템 메시지 등을 우편으로 발송하고 관리합니다.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from models.mail import Mail, MailType
from models.users import User
from .exceptions import (
    MailNotFoundError,
    AlreadyClaimedError,
    NoRewardError,
    ExpiredMailError,
    CannotDeleteError,
)

logger = logging.getLogger(__name__)


class MailService:
    """우편 서비스"""

    @staticmethod
    async def send_mail(
        user_id: int,
        mail_type: MailType,
        sender: str,
        title: str,
        content: str,
        reward_config: Optional[Dict[str, Any]] = None,
        expire_days: int = 30
    ) -> Mail:
        """
        우편 발송

        Args:
            user_id: 받는 사람 유저 ID
            mail_type: 우편 타입
            sender: 발신자 이름
            title: 제목
            content: 내용
            reward_config: 보상 설정 (JSON)
            expire_days: 만료 일수 (기본 30일)

        Returns:
            생성된 우편
        """
        expires_at = datetime.now() + timedelta(days=expire_days)

        mail = await Mail.create(
            user_id=user_id,
            mail_type=mail_type,
            sender=sender,
            title=title,
            content=content,
            reward_config=reward_config,
            expires_at=expires_at
        )

        logger.info(f"Mail sent: user_id={user_id}, type={mail_type.value}, title={title}")
        return mail

    @staticmethod
    async def get_user_mails(
        user_id: int,
        unread_only: bool = False,
        limit: int = 50,
        offset: int = 0
    ) -> List[Mail]:
        """
        유저 우편 목록 조회

        Args:
            user_id: 유저 ID
            unread_only: True이면 읽지 않은 우편만 조회
            limit: 조회 개수
            offset: 오프셋

        Returns:
            우편 목록
        """
        query = Mail.filter(user_id=user_id)

        if unread_only:
            query = query.filter(is_read=False)

        mails = await query.order_by("-created_at").offset(offset).limit(limit).all()
        return mails

    @staticmethod
    async def get_unread_count(user_id: int) -> int:
        """
        읽지 않은 우편 개수 조회

        Args:
            user_id: 유저 ID

        Returns:
            읽지 않은 우편 개수
        """
        count = await Mail.filter(user_id=user_id, is_read=False).count()
        return count

    @staticmethod
    async def read_mail(mail_id: int, user_id: int) -> Mail:
        """
        우편 읽기

        Args:
            mail_id: 우편 ID
            user_id: 유저 ID

        Returns:
            읽은 우편

        Raises:
            MailNotFoundError: 우편을 찾을 수 없음
        """
        mail = await Mail.get_or_none(id=mail_id, user_id=user_id)

        if not mail:
            raise MailNotFoundError(mail_id)

        if not mail.is_read:
            mail.is_read = True
            await mail.save()
            logger.debug(f"Mail read: mail_id={mail_id}, user_id={user_id}")

        return mail

    @staticmethod
    async def claim_reward(mail_id: int, user_id: int) -> Dict[str, Any]:
        """
        우편 보상 수령

        Args:
            mail_id: 우편 ID
            user_id: 유저 ID

        Returns:
            지급된 보상

        Raises:
            MailNotFoundError: 우편을 찾을 수 없음
            AlreadyClaimedError: 이미 수령한 보상
            NoRewardError: 첨부된 보상이 없음
            ExpiredMailError: 만료된 우편
        """
        mail = await Mail.get_or_none(id=mail_id, user_id=user_id)

        if not mail:
            raise MailNotFoundError(mail_id)

        if mail.is_claimed:
            raise AlreadyClaimedError()

        if not mail.reward_config:
            raise NoRewardError()

        if mail.is_expired:
            raise ExpiredMailError()

        # 보상 지급
        reward = mail.reward_config
        user = await User.get(id=user_id)

        # 경험치 지급
        if "exp" in reward and reward["exp"] > 0:
            # TODO: 경험치 지급 로직 (level_up 이벤트 발행 포함)
            logger.debug(f"EXP reward: user_id={user_id}, exp={reward['exp']}")

        # 골드 지급
        if "gold" in reward and reward["gold"] > 0:
            user.gold += reward["gold"]
            logger.debug(f"Gold reward: user_id={user_id}, gold={reward['gold']}")

        # 아이템 지급
        if "items" in reward and reward["items"]:
            # TODO: 아이템 지급 로직
            logger.debug(f"Item reward: user_id={user_id}, items={reward['items']}")

        await user.save()

        # 수령 완료 처리
        mail.is_claimed = True
        mail.is_read = True
        await mail.save()

        logger.info(f"Reward claimed: mail_id={mail_id}, user_id={user_id}, reward={reward}")
        return reward

    @staticmethod
    async def delete_mail(mail_id: int, user_id: int) -> None:
        """
        우편 삭제

        Args:
            mail_id: 우편 ID
            user_id: 유저 ID

        Raises:
            MailNotFoundError: 우편을 찾을 수 없음
            CannotDeleteError: 보상을 먼저 수령해야 함
        """
        mail = await Mail.get_or_none(id=mail_id, user_id=user_id)

        if not mail:
            raise MailNotFoundError(mail_id)

        if mail.has_reward and not mail.is_claimed:
            raise CannotDeleteError()

        await mail.delete()
        logger.debug(f"Mail deleted: mail_id={mail_id}, user_id={user_id}")

    @staticmethod
    async def claim_all_rewards(user_id: int) -> Dict[str, Any]:
        """
        모든 우편 보상 일괄 수령

        Args:
            user_id: 유저 ID

        Returns:
            총 지급된 보상
        """
        mails = await Mail.filter(
            user_id=user_id,
            is_claimed=False,
            reward_config__isnull=False
        ).all()

        total_reward = {"exp": 0, "gold": 0, "items": []}
        claimed_count = 0

        for mail in mails:
            if mail.is_expired:
                continue

            reward = mail.reward_config
            total_reward["exp"] += reward.get("exp", 0)
            total_reward["gold"] += reward.get("gold", 0)
            total_reward["items"].extend(reward.get("items", []))

            mail.is_claimed = True
            mail.is_read = True
            await mail.save()
            claimed_count += 1

        # 일괄 지급
        if total_reward["exp"] > 0 or total_reward["gold"] > 0:
            user = await User.get(id=user_id)

            # 경험치
            if total_reward["exp"] > 0:
                # TODO: 경험치 지급 로직
                pass

            # 골드
            if total_reward["gold"] > 0:
                user.gold += total_reward["gold"]

            # 아이템
            if total_reward["items"]:
                # TODO: 아이템 지급 로직
                pass

            await user.save()

        logger.info(
            f"All rewards claimed: user_id={user_id}, "
            f"count={claimed_count}, total_reward={total_reward}"
        )
        return total_reward

    @staticmethod
    async def delete_read_mails(user_id: int) -> int:
        """
        읽은 우편 일괄 삭제 (보상 수령 완료된 것만)

        Args:
            user_id: 유저 ID

        Returns:
            삭제된 우편 개수
        """
        deleted = await Mail.filter(
            user_id=user_id,
            is_read=True
        ).filter(
            # 보상이 없거나, 보상이 있으면 수령 완료된 것만
            reward_config__isnull=True
        ).delete()

        # 보상이 있고 수령 완료된 것도 삭제
        deleted += await Mail.filter(
            user_id=user_id,
            is_read=True,
            is_claimed=True,
            reward_config__isnull=False
        ).delete()

        logger.info(f"Read mails deleted: user_id={user_id}, count={deleted}")
        return deleted

    @staticmethod
    async def cleanup_expired_mails() -> int:
        """
        만료된 우편 자동 삭제 (크론잡용)

        Returns:
            삭제된 우편 개수
        """
        now = datetime.now()
        deleted = await Mail.filter(expires_at__lt=now).delete()
        logger.info(f"Expired mails cleaned up: count={deleted}")
        return deleted
