"""
알림 시스템 설정 (Phase 2)
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class NotificationConfig:
    """알림 타이밍 설정"""

    # 거리별 알림 지연 시간 (초)
    IMMEDIATE_DELAY: int = 0
    """즉시 근접 (±3 스텝) 알림 지연 - 즉시"""

    NEARBY_DELAY: int = 5
    """근처 거리 (±10 스텝) 알림 지연 - 5초 후"""

    FAR_DELAY: int = 15
    """먼 거리 (>10 스텝) 알림 지연 - 15초 후"""


# 싱글톤 설정 객체
NOTIFICATION = NotificationConfig()
