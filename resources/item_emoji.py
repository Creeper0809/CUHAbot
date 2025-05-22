from enum import Enum

class ItemType(Enum):
    CONSUME = 'consume'
    EQUIP = 'equip'
    SKILL = 'skill'
    ETC = 'etc'

class ItemEmoji:
    TYPE = {
        ItemType.CONSUME.value: "🧪",
        ItemType.EQUIP.value: "⚔️",
        ItemType.SKILL.value: "📖",
        ItemType.ETC.value: "📦"
    }

    STAT = {
        "공격력": "⚔️",
        "체력": "❤️",
        "속도": "🏃",
        "HP 회복량": "💊"
    }