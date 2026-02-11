"""
우편 모델
"""

from datetime import datetime, timedelta
from enum import Enum
from tortoise import fields
from tortoise.models import Model


class MailType(str, Enum):
    """우편 타입"""

    ACHIEVEMENT = "achievement"      # 업적 보상
    SYSTEM = "system"                # 시스템 메시지
    EVENT = "event"                  # 이벤트 보상
    ADMIN = "admin"                  # 관리자 발송


class Mail(Model):
    """
    우편

    업적 보상, 시스템 메시지, 이벤트 보상 등을 수령하는 우편함
    """

    id = fields.IntField(pk=True)
    user = fields.ForeignKeyField("models.User", related_name="mails")

    # 우편 정보
    mail_type = fields.CharEnumField(MailType)
    sender = fields.CharField(max_length=50)         # "시스템", "운영팀" 등
    title = fields.CharField(max_length=200)         # 제목
    content = fields.TextField()                     # 내용

    # 첨부 보상 (JSON)
    reward_config = fields.JSONField(null=True)
    # 예: {"exp": 1000, "gold": 5000, "items": [{"id": 3001, "quantity": 1}]}

    # 상태
    is_read = fields.BooleanField(default=False)     # 읽음 여부
    is_claimed = fields.BooleanField(default=False)  # 보상 수령 여부

    # 시간
    created_at = fields.DatetimeField(auto_now_add=True)  # 발송 시각
    expires_at = fields.DatetimeField()              # 만료 시각

    class Meta:
        table = "mail"
        indexes = (
            ("user", "is_read"),                     # 미읽음 조회 최적화
            ("user", "created_at"),                  # 최신순 조회 최적화
        )

    def __str__(self) -> str:
        return f"Mail(id={self.id}, user_id={self.user_id}, title={self.title})"

    @staticmethod
    def calculate_expires_at(days: int = 30) -> datetime:
        """
        만료 시각 계산

        Args:
            days: 보관 일수 (기본 30일)

        Returns:
            만료 시각
        """
        return datetime.now() + timedelta(days=days)

    @property
    def is_expired(self) -> bool:
        """만료 여부"""
        return datetime.now() > self.expires_at

    @property
    def has_reward(self) -> bool:
        """보상 첨부 여부"""
        return self.reward_config is not None and bool(self.reward_config)

    @property
    def can_claim_reward(self) -> bool:
        """보상 수령 가능 여부"""
        return self.has_reward and not self.is_claimed and not self.is_expired
