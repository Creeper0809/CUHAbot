"""
인카운터 타입 정의

던전에서 발생할 수 있는 다양한 인카운터 유형을 정의합니다.
"""
import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Optional, TYPE_CHECKING
import random

import discord

from DTO.encounter_view import (
    TreasureView,
    TrapView,
    RandomEventView,
    NPCView,
    HiddenRoomView,
    show_encounter_result
)

if TYPE_CHECKING:
    from service.session import DungeonSession
    from models import Monster


class EncounterType(Enum):
    """인카운터 유형 열거형"""

    MONSTER = "monster"          # 몬스터 전투 (60%)
    TREASURE = "treasure"        # 보물상자 (10%)
    TRAP = "trap"                # 함정 (10%)
    EVENT = "event"              # 랜덤 이벤트: 축복/저주 (10%)
    NPC = "npc"                  # NPC 만남 (5%)
    HIDDEN_ROOM = "hidden_room"  # 숨겨진 방 (5%)


@dataclass
class EncounterResult:
    """인카운터 결과 데이터"""

    encounter_type: EncounterType
    message: str
    exp_gained: int = 0
    gold_gained: int = 0
    items_gained: list = None
    damage_taken: int = 0
    healing_received: int = 0

    def __post_init__(self):
        if self.items_gained is None:
            self.items_gained = []


class Encounter(ABC):
    """인카운터 기본 추상 클래스"""

    encounter_type: EncounterType

    @abstractmethod
    async def execute(
        self,
        session: "DungeonSession",
        interaction: discord.Interaction
    ) -> EncounterResult:
        """
        인카운터 실행

        Args:
            session: 던전 세션
            interaction: Discord 인터랙션

        Returns:
            인카운터 결과
        """
        pass


class TreasureEncounter(Encounter):
    """
    보물상자 인카운터

    골드와 아이템을 획득합니다.
    """

    encounter_type = EncounterType.TREASURE

    def __init__(self, chest_grade: str = "normal"):
        """
        Args:
            chest_grade: 상자 등급 (normal, silver, gold)
        """
        self.chest_grade = chest_grade
        self.grade_multiplier = {
            "normal": 1.0,
            "silver": 2.0,
            "gold": 5.0
        }.get(chest_grade, 1.0)

    async def execute(
        self,
        session: "DungeonSession",
        interaction: discord.Interaction
    ) -> EncounterResult:
        """보물상자 열기"""
        # 보상 계산
        base_gold = 20
        dungeon_level = session.dungeon.require_level if session.dungeon else 1
        gold_gained = int(base_gold * self.grade_multiplier * (1 + dungeon_level / 10))
        gold_gained = int(gold_gained * random.uniform(0.8, 1.2))

        # View 표시
        view = TreasureView(
            user=interaction.user,
            chest_grade=self.chest_grade,
            timeout=15
        )

        embed = view.create_embed(opened=False)
        msg = await interaction.user.send(embed=embed, view=view)
        view.message = msg

        await view.wait()

        # 상자 열기 결과
        session.total_gold += gold_gained

        result_embed = view.create_embed(opened=True, gold=gold_gained)
        await show_encounter_result(msg, result_embed, delay=2.5)

        chest_emoji = {"normal": "📦", "silver": "🎁", "gold": "💎"}.get(self.chest_grade, "📦")

        return EncounterResult(
            encounter_type=self.encounter_type,
            message=f"{chest_emoji} 보물상자 발견! 💰 **+{gold_gained}** 골드",
            gold_gained=gold_gained
        )


class TrapEncounter(Encounter):
    """
    함정 인카운터

    HP 피해를 받습니다. 사망하지는 않습니다.
    """

    encounter_type = EncounterType.TRAP

    def __init__(self, damage_percent: float = 0.1):
        """
        Args:
            damage_percent: 최대 HP 대비 피해 비율
        """
        self.damage_percent = damage_percent

    async def execute(
        self,
        session: "DungeonSession",
        interaction: discord.Interaction
    ) -> EncounterResult:
        """함정 작동"""
        user = session.user

        # 함정 피해 계산 (최대 HP 기준)
        damage = int(user.hp * self.damage_percent)
        actual_damage = min(damage, user.now_hp - 1)
        actual_damage = max(actual_damage, 0)

        trap_types = ["가시 함정", "독 가스", "함정 화살", "낙하 함정", "폭발 함정"]
        trap_name = random.choice(trap_types)

        # View 표시
        view = TrapView(
            user=interaction.user,
            trap_name=trap_name,
            damage=actual_damage,
            timeout=3
        )

        embed = view.create_embed(triggered=False)
        msg = await interaction.user.send(embed=embed, view=view)
        view.message = msg

        await view.wait()

        # 회피 성공 시 피해 감소
        if view.escaped:
            actual_damage = actual_damage // 2  # 피해 절반
            result_embed = view.create_escaped_embed()
            if actual_damage > 0:
                result_embed.add_field(
                    name="부분 피해",
                    value=f"완전히 피하지는 못했다... -{actual_damage} HP",
                    inline=False
                )
        else:
            result_embed = view.create_embed(triggered=True)

        user.now_hp -= actual_damage

        await show_encounter_result(msg, result_embed, delay=2.0)

        escape_msg = " *(회피!)*" if view.escaped else ""

        return EncounterResult(
            encounter_type=self.encounter_type,
            message=f"⚠️ **{trap_name}**{escape_msg} → **-{actual_damage}** HP",
            damage_taken=actual_damage
        )


class RandomEventEncounter(Encounter):
    """
    랜덤 이벤트 인카운터

    축복(버프) 또는 저주(디버프)를 받습니다.
    """

    encounter_type = EncounterType.EVENT

    async def execute(
        self,
        session: "DungeonSession",
        interaction: discord.Interaction
    ) -> EncounterResult:
        """랜덤 이벤트 발생"""
        user = session.user

        is_blessing = random.random() < 0.6  # 60% 확률로 축복
        event_type = "blessing" if is_blessing else "curse"

        # View 표시
        view = RandomEventView(
            user=interaction.user,
            is_blessing=is_blessing,
            event_type=event_type,
            timeout=10
        )

        embed = view.create_embed(before=True)
        msg = await interaction.user.send(embed=embed, view=view)
        view.message = msg

        await view.wait()

        # 결과 임베드
        result_embed = view.create_embed(before=False)

        if is_blessing:
            # 축복 효과 (HP 회복 또는 버프)
            blessing_type = random.choice(["heal", "attack_boost", "lucky"])

            if blessing_type == "heal":
                heal_amount = int(user.hp * 0.2)
                actual_heal = min(heal_amount, user.hp - user.now_hp)
                user.now_hp += actual_heal

                result_embed.description = "신비로운 에너지가 몸을 감싼다..."
                result_embed.add_field(
                    name="✨ 신비로운 샘물",
                    value=f"HP +{actual_heal} 회복!",
                    inline=False
                )

                await show_encounter_result(msg, result_embed, delay=2.5)

                return EncounterResult(
                    encounter_type=self.encounter_type,
                    message=f"✨ 신비로운 샘물 발견! **+{actual_heal}** HP",
                    healing_received=actual_heal
                )

            elif blessing_type == "attack_boost":
                result_embed.description = "전투의 기운이 깃든다..."
                result_embed.add_field(
                    name="🔥 전투의 축복",
                    value="다음 전투 공격력 증가!",
                    inline=False
                )

                await show_encounter_result(msg, result_embed, delay=2.5)

                return EncounterResult(
                    encounter_type=self.encounter_type,
                    message="🔥 **전투의 축복**을 받았다! *(공격력 증가)*"
                )

            else:  # lucky
                bonus_gold = random.randint(10, 50)
                session.total_gold += bonus_gold

                result_embed.description = "반짝이는 무언가를 발견했다!"
                result_embed.add_field(
                    name="🍀 행운의 동전",
                    value=f"골드 +{bonus_gold}!",
                    inline=False
                )

                await show_encounter_result(msg, result_embed, delay=2.5)

                return EncounterResult(
                    encounter_type=self.encounter_type,
                    message=f"🍀 행운의 동전 발견! 💰 **+{bonus_gold}** 골드",
                    gold_gained=bonus_gold
                )

        else:
            # 저주 효과 (HP 감소 또는 디버프)
            curse_type = random.choice(["damage", "gold_loss"])

            if curse_type == "damage":
                damage = int(user.hp * 0.05)
                actual_damage = min(damage, user.now_hp - 1)
                actual_damage = max(actual_damage, 0)
                user.now_hp -= actual_damage

                result_embed.description = "어둠의 기운이 몸을 휘감는다..."
                result_embed.add_field(
                    name="👻 저주받은 장소",
                    value=f"HP -{actual_damage}",
                    inline=False
                )

                await show_encounter_result(msg, result_embed, delay=2.5)

                return EncounterResult(
                    encounter_type=self.encounter_type,
                    message=f"👻 **저주받은 장소**... **-{actual_damage}** HP",
                    damage_taken=actual_damage
                )

            else:  # gold_loss
                gold_loss = min(random.randint(5, 20), session.total_gold)
                session.total_gold -= gold_loss

                result_embed.description = "주머니가 갑자기 가벼워졌다..."
                result_embed.add_field(
                    name="💸 도둑의 저주",
                    value=f"골드 -{gold_loss}",
                    inline=False
                )

                await show_encounter_result(msg, result_embed, delay=2.5)

                return EncounterResult(
                    encounter_type=self.encounter_type,
                    message=f"💸 **도둑의 저주!** 💰 **-{gold_loss}** 골드",
                    gold_gained=-gold_loss
                )


class NPCEncounter(Encounter):
    """
    NPC 인카운터

    상인, 여행자, 현자 등을 만납니다.
    """

    encounter_type = EncounterType.NPC

    async def execute(
        self,
        session: "DungeonSession",
        interaction: discord.Interaction
    ) -> EncounterResult:
        """NPC 만남"""
        user = session.user

        npc_type = random.choice(["merchant", "healer", "sage"])

        # View 표시
        view = NPCView(
            user=interaction.user,
            npc_type=npc_type,
            timeout=15
        )

        embed = view.create_embed(before=True)
        msg = await interaction.user.send(embed=embed, view=view)
        view.message = msg

        await view.wait()

        # 결과 임베드
        result_embed = view.create_embed(before=False)

        if npc_type == "merchant":
            # 상인: 할인 또는 보너스
            bonus_gold = random.randint(15, 30)
            session.total_gold += bonus_gold

            result_embed.description = "*\"좋은 거래였네, 친구!\"*"
            result_embed.add_field(
                name="🎁 선물",
                value=f"상인이 골드 **{bonus_gold}**을 건네주었다!",
                inline=False
            )

            await show_encounter_result(msg, result_embed, delay=2.5)

            return EncounterResult(
                encounter_type=self.encounter_type,
                message=f"🧙 **떠돌이 상인**을 만났다! 💰 **+{bonus_gold}** 골드",
                gold_gained=bonus_gold
            )

        elif npc_type == "healer":
            # 치료사: HP 회복
            heal_amount = int(user.hp * 0.3)
            actual_heal = min(heal_amount, user.hp - user.now_hp)
            user.now_hp += actual_heal

            result_embed.description = "*\"상처가 다 나았군요.\"*"
            result_embed.add_field(
                name="💚 치료",
                value=f"HP **+{actual_heal}** 회복!",
                inline=False
            )

            await show_encounter_result(msg, result_embed, delay=2.5)

            return EncounterResult(
                encounter_type=self.encounter_type,
                message=f"💚 **방랑 치료사**를 만났다! **+{actual_heal}** HP",
                healing_received=actual_heal
            )

        else:  # sage
            # 현자: 경험치 보너스
            bonus_exp = random.randint(10, 25)
            session.total_exp += bonus_exp

            result_embed.description = "*\"지식은 가장 큰 보물이지...\"*"
            result_embed.add_field(
                name="📚 가르침",
                value=f"경험치 **+{bonus_exp}** 획득!",
                inline=False
            )

            await show_encounter_result(msg, result_embed, delay=2.5)

            return EncounterResult(
                encounter_type=self.encounter_type,
                message=f"📚 **현자의 가르침**을 받았다! ⭐ **+{bonus_exp}** EXP",
                exp_gained=bonus_exp
            )


class HiddenRoomEncounter(Encounter):
    """
    숨겨진 방 인카운터

    희귀한 보상을 얻습니다.
    """

    encounter_type = EncounterType.HIDDEN_ROOM

    async def execute(
        self,
        session: "DungeonSession",
        interaction: discord.Interaction
    ) -> EncounterResult:
        """숨겨진 방 발견"""
        user = session.user
        dungeon_level = session.dungeon.require_level if session.dungeon else 1

        # 숨겨진 방은 큰 보상
        gold_gained = int(50 * (1 + dungeon_level / 5))
        exp_gained = int(30 * (1 + dungeon_level / 10))

        # HP도 일부 회복
        heal_amount = int(user.hp * 0.15)
        actual_heal = min(heal_amount, user.hp - user.now_hp)

        # View 표시
        view = HiddenRoomView(
            user=interaction.user,
            timeout=15
        )

        embed = view.create_embed(before=True)
        msg = await interaction.user.send(embed=embed, view=view)
        view.message = msg

        await view.wait()

        # 보상 적용
        session.total_gold += gold_gained
        session.total_exp += exp_gained
        user.now_hp += actual_heal

        # 결과 표시
        result_embed = view.create_embed(
            before=False,
            gold=gold_gained,
            exp=exp_gained,
            heal=actual_heal
        )

        await show_encounter_result(msg, result_embed, delay=3.0)

        return EncounterResult(
            encounter_type=self.encounter_type,
            message=(
                f"🚪 **숨겨진 방**을 발견했다!\n"
                f"   💰 **+{gold_gained}** 골드 | ⭐ **+{exp_gained}** EXP\n"
                f"   💚 **+{actual_heal}** HP *(휴식)*"
            ),
            gold_gained=gold_gained,
            exp_gained=exp_gained,
            healing_received=actual_heal
        )
