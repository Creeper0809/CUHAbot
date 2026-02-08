"""속성 타입 및 상성 설정"""
from dataclasses import dataclass
from enum import Enum


class AttributeType(str, Enum):
    """속성 타입"""
    NONE = "무속성"
    FIRE = "화염"
    ICE = "냉기"
    LIGHTNING = "번개"
    WATER = "수속성"
    HOLY = "신성"
    DARK = "암흑"


# 속성 상성표: key가 value에 강함
# Fire->Ice->Lightning->Water->Fire (순환), Holy<->Dark (상호)
ATTRIBUTE_ADVANTAGE: dict[AttributeType, AttributeType] = {
    AttributeType.FIRE: AttributeType.ICE,
    AttributeType.ICE: AttributeType.LIGHTNING,
    AttributeType.LIGHTNING: AttributeType.WATER,
    AttributeType.WATER: AttributeType.FIRE,
    AttributeType.HOLY: AttributeType.DARK,
    AttributeType.DARK: AttributeType.HOLY,
}

# 역방향 (약점 조회용)
ATTRIBUTE_DISADVANTAGE: dict[AttributeType, AttributeType] = {
    v: k for k, v in ATTRIBUTE_ADVANTAGE.items()
}


@dataclass(frozen=True)
class AttributeConfig:
    """속성 상성 설정"""

    ADVANTAGE_MULTIPLIER: float = 1.5
    """유리한 속성 데미지 배율 (+50%)"""

    DISADVANTAGE_MULTIPLIER: float = 0.5
    """불리한 속성 데미지 배율 (-50%)"""

    SAME_ELEMENT_MULTIPLIER: float = 0.5
    """동일 속성 데미지 배율 (-50%)"""

    NEUTRAL_MULTIPLIER: float = 1.0
    """무속성 데미지 배율"""

    MAX_RESISTANCE: float = 0.75
    """최대 속성 저항 (75%)"""


ATTRIBUTE = AttributeConfig()


def get_attribute_multiplier(attacker_attr: str, defender_attr: str) -> float:
    """
    속성 상성에 따른 데미지 배율 계산

    Args:
        attacker_attr: 공격 스킬의 속성 (AttributeType.value 문자열)
        defender_attr: 방어자의 속성 (AttributeType.value 문자열)

    Returns:
        데미지 배율
    """
    if attacker_attr == AttributeType.NONE.value or defender_attr == AttributeType.NONE.value:
        return ATTRIBUTE.NEUTRAL_MULTIPLIER

    if attacker_attr == defender_attr:
        return ATTRIBUTE.SAME_ELEMENT_MULTIPLIER

    try:
        atk_type = AttributeType(attacker_attr)
        def_type = AttributeType(defender_attr)
    except ValueError:
        return ATTRIBUTE.NEUTRAL_MULTIPLIER

    # 강점 체크
    if ATTRIBUTE_ADVANTAGE.get(atk_type) == def_type:
        return ATTRIBUTE.ADVANTAGE_MULTIPLIER

    # 약점 체크
    if ATTRIBUTE_DISADVANTAGE.get(atk_type) == def_type:
        return ATTRIBUTE.DISADVANTAGE_MULTIPLIER

    return ATTRIBUTE.NEUTRAL_MULTIPLIER
