"""
테스트용 User 픽스처 데이터
"""
from typing import Any

# 기본 테스트 유저 데이터
DEFAULT_USER_DATA: dict[str, Any] = {
    "discord_id": 123456789,
    "username": "TestUser",
    "level": 1,
    "hp": 300,
    "now_hp": 300,
    "attack": 10,
    "speed": 10,
}

# 다양한 레벨의 유저 데이터
USER_LEVEL_1: dict[str, Any] = {
    "discord_id": 100000001,
    "username": "Newbie",
    "level": 1,
    "hp": 300,
    "now_hp": 300,
    "attack": 10,
    "speed": 10,
}

USER_LEVEL_10: dict[str, Any] = {
    "discord_id": 100000010,
    "username": "Intermediate",
    "level": 10,
    "hp": 500,
    "now_hp": 500,
    "attack": 30,
    "speed": 15,
}

USER_LEVEL_50: dict[str, Any] = {
    "discord_id": 100000050,
    "username": "Advanced",
    "level": 50,
    "hp": 2000,
    "now_hp": 2000,
    "attack": 150,
    "speed": 50,
}

USER_LEVEL_100: dict[str, Any] = {
    "discord_id": 100000100,
    "username": "Master",
    "level": 100,
    "hp": 10000,
    "now_hp": 10000,
    "attack": 500,
    "speed": 100,
}

# 특수 상태 유저 데이터
USER_LOW_HP: dict[str, Any] = {
    "discord_id": 200000001,
    "username": "Wounded",
    "level": 10,
    "hp": 500,
    "now_hp": 50,  # HP 10%
    "attack": 30,
    "speed": 15,
}

USER_DEAD: dict[str, Any] = {
    "discord_id": 200000002,
    "username": "Dead",
    "level": 10,
    "hp": 500,
    "now_hp": 0,
    "attack": 30,
    "speed": 15,
}

# 테스트용 유저 목록
ALL_TEST_USERS = [
    DEFAULT_USER_DATA,
    USER_LEVEL_1,
    USER_LEVEL_10,
    USER_LEVEL_50,
    USER_LEVEL_100,
    USER_LOW_HP,
    USER_DEAD,
]
