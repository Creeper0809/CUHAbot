from enum import Enum
import discord
from typing import Dict

class ItemType(Enum):
    CONSUME = 'consume'
    EQUIP = 'equip'
    SKILL = 'skill'
    ETC = 'etc'

    @property
    def model_name(self) -> str:
        return f"{self.value.capitalize()}Item"

class ItemEmoji:
    _instance = None
    _emojis: Dict[str, discord.Emoji] = {}
    
    def __init__(self):
        if ItemEmoji._instance is not None:
            raise Exception("이미 생성된 인스턴스가 있습니다")
        ItemEmoji._instance = self

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def initialize(cls, bot: discord.Client):
        instance = cls.get_instance()
        emoji_guild = discord.utils.get(bot.guilds, name="CUHAbot-Emoji")
        if not emoji_guild:
            raise Exception("CUHAbot-Emoji 서버를 찾을 수 없습니다. 봇을 서버에 초대해주세요.")

        cls._emojis.clear()
        for emoji in emoji_guild.emojis:
            cls._emojis[emoji.name] = emoji

    @classmethod
    def get_emoji(cls, name: str, default: str = "❓") -> str:
        # 이모지 가져오기
        emoji = cls._emojis.get(name)
        return str(emoji) if emoji else default

    @classmethod
    def get_type_emoji(cls, item_type: ItemType) -> str:
        # 아이템 타입에 해당하는 이모지 가져오기
        return cls.get_emoji(item_type.name.lower())

    @classmethod
    def get_gold_emoji(cls) -> str:
        # 골드 이모지 가져오기
        return cls.get_emoji('gold', "💰")

    @classmethod
    def get_stat_emoji(cls, stat_name: str) -> str:
        # 스탯 이모지 가져오기기
        return cls.get_emoji(stat_name)

EmojiManager = ItemEmoji