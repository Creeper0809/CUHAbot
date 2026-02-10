"""
근접도 기반 비용/보상 계산기 (Phase 2)

exploration_step 거리에 따라:
- 난입 비용: 가까울수록 저렴 (무료/100G/500G)
- 보상 배율: 가까울수록 높음 (+10%/정상/-20%)
"""

from config.voice_channel import VOICE_CHANNEL


def get_intervention_cost(distance: int) -> int:
    """
    근접도에 따른 난입 비용 계산

    Args:
        distance: exploration_step 차이 (절댓값)

    Returns:
        난입 비용 (골드)
        - ±3 스텝: 0G (무료)
        - ±10 스텝: 100G
        - >10 스텝: 500G
    """
    if distance <= VOICE_CHANNEL.PROXIMITY_IMMEDIATE_STEPS:
        return VOICE_CHANNEL.COST_IMMEDIATE  # 0G
    elif distance <= VOICE_CHANNEL.PROXIMITY_NEARBY_STEPS:
        return VOICE_CHANNEL.COST_NEARBY  # 100G
    else:
        return VOICE_CHANNEL.COST_FAR  # 500G


def get_proximity_reward_multiplier(distance: int) -> float:
    """
    근접도에 따른 보상 배율 계산

    Args:
        distance: exploration_step 차이 (절댓값)

    Returns:
        보상 배율 (곱하기 계수)
        - ±3 스텝: 1.1 (+10%)
        - ±10 스텝: 1.0 (정상)
        - >10 스텝: 0.8 (-20%)
    """
    if distance <= VOICE_CHANNEL.PROXIMITY_IMMEDIATE_STEPS:
        return VOICE_CHANNEL.BONUS_IMMEDIATE  # 1.1
    elif distance <= VOICE_CHANNEL.PROXIMITY_NEARBY_STEPS:
        return VOICE_CHANNEL.BONUS_NEARBY  # 1.0
    else:
        return VOICE_CHANNEL.BONUS_FAR  # 0.8
