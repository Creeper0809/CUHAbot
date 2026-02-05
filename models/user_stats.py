"""
UserStats 모델 정의

사용자의 상세 스탯 및 분배 포인트를 관리합니다.
"""
from tortoise import models, fields


class UserStats(models.Model):
    """
    사용자 스탯 모델

    Balance.md 기준 스탯 시스템:
    - 기본 스탯은 레벨에 따라 자동 계산
    - stat_points로 추가 스탯 분배
    """

    id = fields.IntField(pk=True)
    user = fields.OneToOneField(
        "models.User",
        related_name="stats",
        on_delete=fields.CASCADE
    )

    # 경험치
    experience = fields.BigIntField(default=0)

    # 분배 가능 스탯 포인트
    stat_points = fields.IntField(default=0)

    # 보너스 스탯 (장비/버프와 별개로 영구 분배된 스탯)
    bonus_hp = fields.IntField(default=0)
    bonus_attack = fields.IntField(default=0)
    bonus_ap_attack = fields.IntField(default=0)
    bonus_ad_defense = fields.IntField(default=0)
    bonus_ap_defense = fields.IntField(default=0)
    bonus_speed = fields.IntField(default=0)

    # 보조 스탯 (퍼센트 기반, 100 = 100%)
    accuracy = fields.IntField(default=90)
    evasion = fields.IntField(default=5)
    critical_rate = fields.IntField(default=5)
    critical_damage = fields.IntField(default=150)

    # 골드
    gold = fields.BigIntField(default=0)

    # 출석 관련
    last_attendance = fields.DateField(null=True)
    attendance_streak = fields.IntField(default=0)

    class Meta:
        table = "user_stats"
