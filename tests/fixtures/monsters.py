"""
테스트용 Monster 픽스처 데이터
"""
from typing import Any

# 기본 테스트 몬스터 데이터
DEFAULT_MONSTER_DATA: dict[str, Any] = {
    "id": 1,
    "name": "테스트 슬라임",
    "description": "테스트용 슬라임입니다.",
    "hp": 100,
    "attack": 10,
    "speed": 5,
}

# 약한 몬스터 (초반 던전용)
WEAK_MONSTERS: list[dict[str, Any]] = [
    {
        "id": 1,
        "name": "슬라임",
        "description": "끈적끈적한 슬라임",
        "hp": 50,
        "attack": 5,
        "speed": 3,
    },
    {
        "id": 2,
        "name": "고블린",
        "description": "작은 고블린",
        "hp": 80,
        "attack": 8,
        "speed": 5,
    },
    {
        "id": 3,
        "name": "박쥐",
        "description": "날아다니는 박쥐",
        "hp": 30,
        "attack": 6,
        "speed": 10,
    },
]

# 중간 몬스터 (중반 던전용)
MEDIUM_MONSTERS: list[dict[str, Any]] = [
    {
        "id": 10,
        "name": "오크 전사",
        "description": "강력한 오크 전사",
        "hp": 300,
        "attack": 25,
        "speed": 8,
    },
    {
        "id": 11,
        "name": "스켈레톤 기사",
        "description": "갑옷을 입은 해골",
        "hp": 250,
        "attack": 30,
        "speed": 10,
    },
    {
        "id": 12,
        "name": "트롤",
        "description": "재생력이 강한 트롤",
        "hp": 500,
        "attack": 20,
        "speed": 5,
    },
]

# 강한 몬스터 (후반 던전용)
STRONG_MONSTERS: list[dict[str, Any]] = [
    {
        "id": 50,
        "name": "드래곤",
        "description": "화염을 뿜는 드래곤",
        "hp": 2000,
        "attack": 100,
        "speed": 30,
    },
    {
        "id": 51,
        "name": "리치",
        "description": "강력한 언데드 마법사",
        "hp": 1500,
        "attack": 80,
        "speed": 25,
    },
    {
        "id": 52,
        "name": "데몬 로드",
        "description": "지옥에서 온 악마 군주",
        "hp": 3000,
        "attack": 150,
        "speed": 40,
    },
]

# 보스 몬스터
BOSS_MONSTERS: list[dict[str, Any]] = [
    {
        "id": 100,
        "name": "고블린 킹",
        "description": "고블린들의 왕",
        "hp": 500,
        "attack": 40,
        "speed": 15,
    },
    {
        "id": 101,
        "name": "얼음 드래곤",
        "description": "냉기를 뿜는 고대 드래곤",
        "hp": 5000,
        "attack": 200,
        "speed": 35,
    },
    {
        "id": 102,
        "name": "최종 보스",
        "description": "모든 것의 끝",
        "hp": 10000,
        "attack": 500,
        "speed": 50,
    },
]

# 테스트용 몬스터 전체 목록
ALL_TEST_MONSTERS = WEAK_MONSTERS + MEDIUM_MONSTERS + STRONG_MONSTERS + BOSS_MONSTERS
