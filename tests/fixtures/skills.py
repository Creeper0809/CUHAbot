"""
테스트용 Skill 픽스처 데이터
"""
from typing import Any

# 기본 공격 스킬
BASIC_ATTACK_SKILLS: list[dict[str, Any]] = [
    {
        "id": 1,
        "name": "강타",
        "description": "기본 공격 스킬",
        "grade": "D",
        "damage_multiplier": 1.0,
        "config": {"type": "attack", "damage": 1},
    },
    {
        "id": 2,
        "name": "연속 베기",
        "description": "2회 공격",
        "grade": "D",
        "damage_multiplier": 0.6,
        "hit_count": 2,
        "config": {"type": "attack", "damage": 2},
    },
    {
        "id": 3,
        "name": "급소 찌르기",
        "description": "치명타 확률 증가",
        "grade": "C",
        "damage_multiplier": 1.2,
        "crit_bonus": 0.3,
        "config": {"type": "attack", "damage": 1, "crit_bonus": 30},
    },
]

# 회복 스킬
HEAL_SKILLS: list[dict[str, Any]] = [
    {
        "id": 10,
        "name": "치유",
        "description": "HP를 회복합니다",
        "grade": "D",
        "heal_amount": 50,
        "config": {"type": "heal", "amount": 50},
    },
    {
        "id": 11,
        "name": "대치유",
        "description": "HP를 대량 회복합니다",
        "grade": "B",
        "heal_amount": 200,
        "config": {"type": "heal", "amount": 200},
    },
    {
        "id": 12,
        "name": "완전 회복",
        "description": "HP를 완전히 회복합니다",
        "grade": "S",
        "heal_percent": 1.0,
        "config": {"type": "heal", "percent": 100},
    },
]

# 버프 스킬
BUFF_SKILLS: list[dict[str, Any]] = [
    {
        "id": 20,
        "name": "공격력 증가",
        "description": "공격력을 15% 증가시킵니다",
        "grade": "D",
        "buff_type": "attack",
        "buff_amount": 0.15,
        "duration": 3,
        "config": {"type": "buff", "stat": "attack", "amount": 15, "duration": 3},
    },
    {
        "id": 21,
        "name": "방어력 증가",
        "description": "방어력을 20% 증가시킵니다",
        "grade": "C",
        "buff_type": "defense",
        "buff_amount": 0.20,
        "duration": 3,
        "config": {"type": "buff", "stat": "defense", "amount": 20, "duration": 3},
    },
    {
        "id": 22,
        "name": "속도 증가",
        "description": "속도를 30% 증가시킵니다",
        "grade": "B",
        "buff_type": "speed",
        "buff_amount": 0.30,
        "duration": 2,
        "config": {"type": "buff", "stat": "speed", "amount": 30, "duration": 2},
    },
]

# 속성 스킬
ELEMENTAL_SKILLS: list[dict[str, Any]] = [
    {
        "id": 30,
        "name": "화염구",
        "description": "화염 속성 공격",
        "grade": "C",
        "element": "fire",
        "damage_multiplier": 1.3,
        "config": {"type": "attack", "damage": 1, "element": "fire"},
    },
    {
        "id": 31,
        "name": "빙결",
        "description": "냉기 속성 공격",
        "grade": "C",
        "element": "ice",
        "damage_multiplier": 1.2,
        "slow_chance": 0.3,
        "config": {"type": "attack", "damage": 1, "element": "ice", "slow": 30},
    },
    {
        "id": 32,
        "name": "번개",
        "description": "번개 속성 공격",
        "grade": "B",
        "element": "lightning",
        "damage_multiplier": 1.4,
        "stun_chance": 0.1,
        "config": {"type": "attack", "damage": 1, "element": "lightning", "stun": 10},
    },
]

# 테스트용 스킬 전체 목록
ALL_TEST_SKILLS = BASIC_ATTACK_SKILLS + HEAL_SKILLS + BUFF_SKILLS + ELEMENTAL_SKILLS

# 기본 덱 구성 (10슬롯)
DEFAULT_SKILL_DECK = [1, 1, 1, 1, 1, 10, 10, 20, 30, 31]  # 강타x5, 치유x2, 공증x1, 화염구x1, 빙결x1
