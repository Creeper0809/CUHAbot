"""
멀티유저 만남 이벤트 설정 (Phase 3 + 4)

교차로 만남, 캠프파이어, 동시 조우, 보스방 대기실, 위기 목격 등
멀티유저 encounter 이벤트의 발생 조건, 확률, 타이밍을 정의합니다.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class SocialEncounterConfig:
    """멀티유저 만남 이벤트 설정"""

    # 교차로 만남
    CROSSROADS_PROBABILITY: float = 0.20
    """교차로 만남 발생 확률 (20%)"""

    CROSSROADS_DISTANCE_THRESHOLD: int = 2
    """교차로 만남 거리 제한 (±2 스텝)"""

    CROSSROADS_TIMEOUT: int = 30
    """초대 응답 대기 시간 (초)"""

    CROSSROADS_MEETING_TIMEOUT: int = 30
    """만남 선택 대기 시간 (초)"""

    CROSSROADS_EXP_REWARD: int = 30
    """교차로 만남 성립 시 채널 EXP 보상"""

    # 캠프파이어
    CAMPFIRE_PROBABILITY: float = 0.25
    """캠프파이어 발생 확률 (25%)"""

    CAMPFIRE_DISTANCE_THRESHOLD: int = 10
    """캠프파이어 알림 거리 제한 (±10 스텝)"""

    CAMPFIRE_TIMEOUT: int = 60
    """캠프파이어 참여 대기 시간 (초)"""

    CAMPFIRE_HEAL_1P: float = 0.30
    """1명 참여 시 HP 회복 비율 (30%)"""

    CAMPFIRE_HEAL_2P: float = 0.40
    """2명 참여 시 HP 회복 비율 (40%)"""

    CAMPFIRE_HEAL_3P: float = 0.50
    """3+명 참여 시 HP 회복 비율 (50%)"""

    CAMPFIRE_BUFF_ATTACK_PCT: float = 0.10
    """캠프파이어 ATK 버프 비율 (10%)"""

    CAMPFIRE_BUFF_COMBATS_2P: int = 1
    """2명 참여 시 ATK 버프 지속 전투 수"""

    CAMPFIRE_BUFF_COMBATS_3P: int = 2
    """3+명 참여 시 ATK 버프 지속 전투 수"""

    # 공통
    ENCOUNTER_EVENT_COOLDOWN: int = 30
    """멀티유저 encounter 쿨타임 (스텝)"""

    # Phase 4: 고급 만남 이벤트
    SIMULTANEOUS_ENCOUNTER_PROBABILITY: float = 0.20
    """동시 조우 발생 확률 (20%)"""

    BOSS_WAITING_ROOM_PROBABILITY: float = 0.15
    """보스방 대기실 발생 확률 (15%)"""

    BOSS_WAITING_ROOM_TIMEOUT: int = 60
    """보스방 대기실 타임아웃 (초)"""

    BOSS_WAITING_ROOM_MAX_PARTICIPANTS: int = 3
    """보스방 대기실 최대 인원"""

    CRISIS_WITNESS_PROBABILITY: float = 0.10
    """위기 목격 발생 확률 (10%)"""

    CRISIS_HP_THRESHOLD: float = 0.30
    """위기 판정 HP 임계값 (30%)"""

    CRISIS_CHEER_ATTACK_BONUS: int = 5
    """응원 버프 공격력 보너스"""

    CRISIS_RESCUE_REWARD_BONUS: float = 0.30
    """구조 성공 시 보상 보너스 (30%)"""


# 싱글톤 설정 객체
SOCIAL_ENCOUNTER = SocialEncounterConfig()
