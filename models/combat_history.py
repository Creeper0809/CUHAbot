"""전투 기록 모델 (Phase 5 - 환영 시스템)"""
from datetime import datetime, timedelta
from tortoise import fields
from tortoise.models import Model


class CombatHistory(Model):
    """
    전투 흔적 (환영 시스템)

    다른 플레이어의 전투 기록을 던전 탐험 중 발견할 수 있습니다.
    Dark Souls의 환영 시스템과 유사하게, 근처에서 벌어진 전투의 흔적을 자동으로 표시합니다.
    """

    id = fields.IntField(pk=True)

    user = fields.ForeignKeyField("models.User", related_name="combat_histories")
    """전투를 수행한 유저"""

    dungeon = fields.ForeignKeyField("models.Dungeon", related_name="combat_histories")
    """전투가 발생한 던전"""

    voice_channel_id = fields.BigIntField(null=True)
    """유저가 속한 음성 채널 ID"""

    # 위치 정보
    exploration_step = fields.IntField()
    """전투 발생 스텝 (위치)"""

    # 전투 정보
    monster_name = fields.CharField(max_length=100)
    """몬스터 이름"""

    monster_level = fields.IntField(default=1)
    """몬스터 레벨 (난이도 분석용)"""

    result = fields.CharField(max_length=20)
    """전투 결과: victory, defeat, fled"""

    # 멀티플레이어 정보
    participant_ids = fields.JSONField(default=list)
    """참가자 Discord ID 리스트 [leader_id, participant1_id, ...]"""

    participants_count = fields.IntField(default=1)
    """참가자 수 (협력 플레이 통계)"""

    # 난이도 정보
    difficulty_multiplier = fields.FloatField(default=1.0)
    """난이도 배율 (일반=1.0, 엘리트=1.5, 보스=2.0)"""

    dungeon_name = fields.CharField(max_length=100, null=True)
    """던전 이름 (빠른 조회용 비정규화)"""

    # 전투 세부 정보
    total_damage = fields.IntField(default=0)
    """총 데미지 (모든 참가자 합계)"""

    turns_lasted = fields.IntField(default=0)
    """턴 수"""

    # 시간
    created_at = fields.DatetimeField(auto_now_add=True)
    """생성 시각"""

    expires_at = fields.DatetimeField()
    """만료 시각 (30분 후)"""

    @property
    def is_expired(self) -> bool:
        """만료 여부"""
        return datetime.now() > self.expires_at

    @staticmethod
    def calculate_expires_at() -> datetime:
        """만료 시각 계산 (30분 후)"""
        return datetime.now() + timedelta(minutes=30)

    class Meta:
        table = "combat_history"
        indexes = [
            ("dungeon_id", "exploration_step", "expires_at"),  # 근처 환영 조회 최적화
            ("voice_channel_id", "created_at"),  # 채널별 조회 최적화
        ]

    def __str__(self):
        return f"CombatHistory({self.user.name if hasattr(self, 'user') else 'Unknown'} vs {self.monster_name} @ step {self.exploration_step})"
