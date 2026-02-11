"""
업적 모델
"""

from enum import Enum
from tortoise import fields
from tortoise.models import Model


class AchievementCategory(str, Enum):
    """업적 카테고리"""

    COMBAT = "combat"              # 전투 업적
    EXPLORATION = "exploration"    # 탐험 업적
    COMBAT_MASTERY = "combat_mastery"  # 전투 마스터 업적
    COLLECTION = "collection"      # 수집 업적
    WEALTH = "wealth"              # 재화 업적
    GROWTH = "growth"              # 성장 업적


class Achievement(Model):
    """
    업적 마스터 데이터

    플레이어의 장기 목표를 정의합니다.
    각 업적은 티어 I/II/III로 구성됩니다.
    """

    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=100)                      # 업적 이름
    description = fields.TextField()                             # 설명
    category = fields.CharEnumField(AchievementCategory)         # 카테고리

    # 티어 (I/II/III)
    tier = fields.IntField()                                     # 1/2/3

    # 목표 조건 (JSON)
    objective_config = fields.JSONField()
    # 예: {"type": "kill_total", "count": 100}
    # 예: {"type": "kill_monster", "monster_id": 1001, "count": 1000}
    # 예: {"type": "kill_attribute", "attribute": "fire", "count": 100}
    # 예: {"type": "kill_boss", "count": 10}
    # 예: {"type": "dungeon_explore", "count": 10}
    # 예: {"type": "gold_earned", "count": 100000}
    # 예: {"type": "gold_owned", "count": 50000}
    # 예: {"type": "level", "level": 10}
    # 예: {"type": "win_streak", "count": 10}
    # 예: {"type": "win_flawless", "count": 10}
    # 예: {"type": "win_fast", "turns": 3, "count": 10}
    # 예: {"type": "item_collected", "count": 100}
    # 예: {"type": "item_used", "item_type": "consume", "count": 50}

    # 보상 (JSON)
    reward_config = fields.JSONField()
    # 예: {"exp": 1000, "gold": 5000, "title": "슬라임 헌터"}

    # 선행 업적 (티어 순서)
    prerequisite_achievement_id = fields.IntField(null=True)

    # 칭호 (티어 III만)
    title_name = fields.CharField(max_length=50, null=True)      # "슬라임 헌터 마스터"

    class Meta:
        table = "achievement"

    def __str__(self) -> str:
        return f"Achievement(id={self.id}, name={self.name}, tier={self.tier})"

    @property
    def tier_name(self) -> str:
        """티어 이름 (I/II/III)"""
        return ["I", "II", "III"][self.tier - 1] if 1 <= self.tier <= 3 else str(self.tier)

    @property
    def full_name(self) -> str:
        """전체 이름 (이름 + 티어)"""
        return f"{self.name} {self.tier_name}"
