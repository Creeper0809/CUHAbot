"""스킬/덱 관련 설정"""
from dataclasses import dataclass


SKILL_DECK_SIZE = 10
"""스킬 덱 최대 슬롯 수"""

DEFAULT_SKILL_SLOT = 0
"""빈 스킬 슬롯 값"""


@dataclass(frozen=True)
class SkillIdConfig:
    """스킬 ID 설정"""

    BASIC_ATTACK_ID: int = 1001
    """기본 공격 스킬 (강타) ID"""

    MONSTER_SKILL_ID_THRESHOLD: int = 9000
    """몬스터 전용 스킬 ID 시작 (9000 이상은 몬스터 전용)"""


SKILL_ID = SkillIdConfig()
