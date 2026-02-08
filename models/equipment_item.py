from tortoise import models, fields
from typing import Dict, Optional
from models.equip_pos import EquipPos
from enum import Enum
from models.base_item import BaseItem

class ItemInfoKey(Enum):
    EQUIP_POSITION = "장착 위치"
    REQUIRE_LEVEL = "요구 레벨"

class StatKey(Enum):
    ATTACK = ("attack", "공격력")
    AP_ATTACK = ("ap_attack", "마법공격력")
    HP = ("hp", "체력")
    AD_DEFENSE = ("ad_defense", "물리방어")
    AP_DEFENSE = ("ap_defense", "마법방어")
    SPEED = ("speed", "속도")

    def __init__(self, key: str, display: str):
        self._key = key
        self._display = display

    @property
    def key(self) -> str:
        return self._key

    @property
    def display(self) -> str:
        return self._display

# 장비 아이템 및 스탯
class EquipmentItem(BaseItem):
    id = fields.BigIntField(pk=True)
    item = fields.ForeignKeyField(
        'models.Item',
        related_name='equipment_item',
        source_field='equipment_item_id',
        to_field='id'
    )
    attack = fields.IntField(null=True)
    ap_attack = fields.IntField(null=True)
    hp = fields.IntField(null=True)
    ad_defense = fields.IntField(null=True)
    ap_defense = fields.IntField(null=True)
    speed = fields.IntField(null=True)
    equip_pos = fields.IntField(null=True)
    require_level = fields.IntField(null=True, default=1)

    # 능력치 요구 사항
    require_str = fields.IntField(default=0)
    require_int = fields.IntField(default=0)
    require_dex = fields.IntField(default=0)
    require_vit = fields.IntField(default=0)
    require_luk = fields.IntField(default=0)

    class Meta:
        table = "equipment_item"

    @property
    def raw_stats(self) -> Dict[StatKey, Optional[int]]:
        return {
            StatKey.ATTACK: self.attack,
            StatKey.AP_ATTACK: self.ap_attack,
            StatKey.HP: self.hp,
            StatKey.AD_DEFENSE: self.ad_defense,
            StatKey.AP_DEFENSE: self.ap_defense,
            StatKey.SPEED: self.speed,
        }

    def get_requirements(self) -> Dict[str, int]:
        """능력치 요구사항 반환 (0이 아닌 것만)"""
        reqs = {}
        if self.require_str:
            reqs["STR"] = self.require_str
        if self.require_int:
            reqs["INT"] = self.require_int
        if self.require_dex:
            reqs["DEX"] = self.require_dex
        if self.require_vit:
            reqs["VIT"] = self.require_vit
        if self.require_luk:
            reqs["LUK"] = self.require_luk
        return reqs

    async def apply_to_embed(self, embed) -> None:

        # 스탯 정보 추가
        self.add_stats_to_embed(embed, self.raw_stats)

        # 장착 위치 정보 추가
        pos_name = await self.get_position_name()
        if pos_name:
            embed.add_field(
                name=ItemInfoKey.EQUIP_POSITION.value,
                value=f"```      {pos_name}      ```",
                inline=True
            )

        # 요구 레벨 정보 추가
        if self.require_level and self.require_level > 1:
            embed.add_field(
                name=ItemInfoKey.REQUIRE_LEVEL.value,
                value=f"```      Lv.{self.require_level}      ```",
                inline=True
            )

        # 요구 능력치 표시
        reqs = self.get_requirements()
        if reqs:
            req_lines = [f"{name} {value}" for name, value in reqs.items()]
            embed.add_field(
                name="📋 요구 능력치",
                value=f"```{' / '.join(req_lines)}```",
                inline=False
            )

    async def get_position_name(self) -> Optional[str]:
        pos = await EquipPos.get_or_none(id=self.equip_pos)
        return pos.pos_name if pos else None

    def __str__(self):
        return f"Equipment {self.id}"
