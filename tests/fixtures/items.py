"""
테스트용 Item 픽스처 데이터
"""
from typing import Any

# 무기 아이템
WEAPON_ITEMS: list[dict[str, Any]] = [
    {
        "id": 1,
        "name": "초보자의 검",
        "description": "초보자용 검",
        "type": "weapon",
        "grade": "D",
        "attack": 5,
        "level_req": 1,
    },
    {
        "id": 2,
        "name": "강철 검",
        "description": "튼튼한 강철 검",
        "type": "weapon",
        "grade": "C",
        "attack": 15,
        "level_req": 10,
    },
    {
        "id": 3,
        "name": "전설의 검",
        "description": "전설적인 힘이 깃든 검",
        "type": "weapon",
        "grade": "S",
        "attack": 100,
        "level_req": 50,
    },
]

# 방어구 아이템
ARMOR_ITEMS: list[dict[str, Any]] = [
    {
        "id": 10,
        "name": "가죽 갑옷",
        "description": "기본 가죽 갑옷",
        "type": "armor",
        "grade": "D",
        "defense": 5,
        "hp": 20,
        "level_req": 1,
    },
    {
        "id": 11,
        "name": "철 갑옷",
        "description": "튼튼한 철 갑옷",
        "type": "armor",
        "grade": "C",
        "defense": 20,
        "hp": 50,
        "level_req": 10,
    },
    {
        "id": 12,
        "name": "용비늘 갑옷",
        "description": "드래곤의 비늘로 만든 갑옷",
        "type": "armor",
        "grade": "S",
        "defense": 80,
        "hp": 300,
        "level_req": 50,
    },
]

# 소비 아이템
CONSUMABLE_ITEMS: list[dict[str, Any]] = [
    {
        "id": 100,
        "name": "HP 포션 (소)",
        "description": "HP를 50 회복합니다",
        "type": "consumable",
        "grade": "D",
        "heal_amount": 50,
    },
    {
        "id": 101,
        "name": "HP 포션 (중)",
        "description": "HP를 150 회복합니다",
        "type": "consumable",
        "grade": "C",
        "heal_amount": 150,
    },
    {
        "id": 102,
        "name": "HP 포션 (대)",
        "description": "HP를 300 회복합니다",
        "type": "consumable",
        "grade": "B",
        "heal_amount": 300,
    },
    {
        "id": 103,
        "name": "만병통치약",
        "description": "HP를 완전히 회복합니다",
        "type": "consumable",
        "grade": "S",
        "heal_percent": 1.0,
    },
]

# 악세서리 아이템
ACCESSORY_ITEMS: list[dict[str, Any]] = [
    {
        "id": 200,
        "name": "행운의 반지",
        "description": "드롭률이 증가합니다",
        "type": "accessory",
        "grade": "C",
        "drop_bonus": 0.05,
    },
    {
        "id": 201,
        "name": "민첩의 목걸이",
        "description": "속도가 증가합니다",
        "type": "accessory",
        "grade": "B",
        "speed": 10,
    },
]

# 테스트용 아이템 전체 목록
ALL_TEST_ITEMS = WEAPON_ITEMS + ARMOR_ITEMS + CONSUMABLE_ITEMS + ACCESSORY_ITEMS
