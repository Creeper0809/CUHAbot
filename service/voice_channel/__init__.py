"""
음성 채널 기반 공유 던전 시스템

Phase 1: 기반 시스템
- 음성 채널 상태 추적
- 공유 인스턴스 관리
- 근접도 계산
"""

from service.voice_channel.voice_channel_service import (
    VoiceChannelService,
    VoiceChannelState,
    voice_channel_service
)
from service.voice_channel.shared_instance_manager import (
    SharedDungeonInstance,
    SharedInstanceManager,
    shared_instance_manager
)
from service.voice_channel.proximity_calculator import (
    ProximityLevel,
    ProximityCalculator
)

__all__ = [
    "VoiceChannelService",
    "VoiceChannelState",
    "voice_channel_service",
    "SharedDungeonInstance",
    "SharedInstanceManager",
    "shared_instance_manager",
    "ProximityLevel",
    "ProximityCalculator",
]
