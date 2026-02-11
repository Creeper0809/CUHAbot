"""
음성 채널 기반 공유 던전 시스템 설정
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class VoiceChannelConfig:
    """음성 채널 공유 던전 설정"""

    # 근접도 임계값
    PROXIMITY_IMMEDIATE_STEPS: int = 3
    """즉시 근접 거리 (±3 스텝)"""

    PROXIMITY_NEARBY_STEPS: int = 10
    """근처 거리 (±10 스텝)"""

    # 알림 설정 (Phase 1: 기본만)
    NOTIFICATION_ENABLED: bool = True
    """입장/퇴장 알림 활성화"""

    # 인스턴스 설정
    INSTANCE_CLEANUP_DELAY: int = 60
    """빈 인스턴스 정리 지연 시간 (초) - 현재 미사용 (즉시 정리)"""

    # Phase 2: 근접도 기반 비용/보상
    COST_IMMEDIATE: int = 0
    """즉시 근접 (±3 스텝) 난입 비용 - 무료"""

    COST_NEARBY: int = 100
    """근처 거리 (±10 스텝) 난입 비용 - 100G"""

    COST_FAR: int = 500
    """먼 거리 (>10 스텝) 난입 비용 - 500G"""

    BONUS_IMMEDIATE: float = 1.1
    """즉시 근접 (±3 스텝) 보상 배율 - +10%"""

    BONUS_NEARBY: float = 1.0
    """근처 거리 (±10 스텝) 보상 배율 - 정상"""

    BONUS_FAR: float = 0.8
    """먼 거리 (>10 스텝) 보상 배율 - -20%"""


# 싱글톤 설정 객체
VOICE_CHANNEL = VoiceChannelConfig()
