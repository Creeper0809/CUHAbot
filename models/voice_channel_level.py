"""음성 채널 레벨 시스템 모델 (Phase 5)"""
from datetime import date as date_type
from tortoise import fields
from tortoise.models import Model


class VoiceChannelLevel(Model):
    """
    음성 채널 레벨 시스템 (일일 통계)

    같은 음성 채널의 플레이어들이 함께 던전을 탐험하며 쌓는 채널 경험치와 레벨을 추적합니다.
    일일 단위로 리셋되며, 채널 레벨에 따라 보상 보너스가 적용됩니다.
    """

    id = fields.IntField(pk=True)
    voice_channel_id = fields.BigIntField()
    """Discord 음성 채널 ID"""

    date = fields.DateField()
    """통계 날짜 (일일 리셋용)"""

    # 레벨/경험치 (User 모델 패턴)
    level = fields.IntField(default=1)
    """채널 레벨 (경험치로 자동 계산)"""

    exp = fields.BigIntField(default=0)
    """누적 경험치"""

    # 통계
    total_combats = fields.IntField(default=0)
    """오늘 총 전투 수"""

    total_damage = fields.BigIntField(default=0)
    """오늘 총 데미지"""

    total_exp_gained = fields.BigIntField(default=0)
    """오늘 획득한 총 경험치 (채널 진행도 추적)"""

    active_players = fields.IntField(default=0)
    """오늘 활성 플레이어 수 (고유 유저 카운트)"""

    intervention_count = fields.IntField(default=0)
    """오늘 난입 횟수 (멀티플레이 참여도)"""

    # MVP
    mvp_user_id = fields.BigIntField(null=True)
    """오늘의 MVP 유저 ID"""

    mvp_damage = fields.IntField(default=0)
    """MVP 유저의 총 데미지"""

    # 시간
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "voice_channel_level"
        unique_together = (("voice_channel_id", "date"),)  # 채널별 일일 1개 레코드

    def __str__(self):
        return f"VoiceChannelLevel(channel={self.voice_channel_id}, date={self.date}, level={self.level})"
