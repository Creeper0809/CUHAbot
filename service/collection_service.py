"""
Collection Service

도감 관련 비즈니스 로직을 담당합니다.
"""
from dataclasses import dataclass
from typing import List, Optional

import discord

from models import User, Item, Monster
from models.user_collection import CollectionType
from models.repos import collection_repo
from models.repos.static_cache import (
    item_cache,
    monster_cache_by_id,
    skill_cache_by_id
)
from service.dungeon.skill import Skill


class EntryNotFoundError(Exception):
    """검색 항목을 찾을 수 없음"""
    pass


@dataclass
class CollectionEntry:
    """도감 항목"""
    id: int
    name: str
    description: str
    collection_type: CollectionType
    is_collected: bool = False


@dataclass
class CollectionStats:
    """도감 통계"""
    item_collected: int
    item_total: int
    skill_collected: int
    skill_total: int
    monster_collected: int
    monster_total: int

    @property
    def total_collected(self) -> int:
        return self.item_collected + self.skill_collected + self.monster_collected

    @property
    def total(self) -> int:
        return self.item_total + self.skill_total + self.monster_total

    @property
    def completion_rate(self) -> float:
        if self.total == 0:
            return 0.0
        return self.total_collected / self.total


class CollectionService:
    """도감 서비스"""

    # ==========================================================================
    # 도감 등록
    # ==========================================================================

    @staticmethod
    async def register_item(user: User, item_id: int) -> bool:
        """
        아이템을 도감에 등록

        Args:
            user: 대상 유저
            item_id: 아이템 ID

        Returns:
            새로 등록되었으면 True
        """
        _, created = await collection_repo.add_collection(
            user, CollectionType.ITEM, item_id
        )
        return created

    @staticmethod
    async def register_skill(user: User, skill_id: int) -> bool:
        """
        스킬을 도감에 등록

        Args:
            user: 대상 유저
            skill_id: 스킬 ID

        Returns:
            새로 등록되었으면 True
        """
        _, created = await collection_repo.add_collection(
            user, CollectionType.SKILL, skill_id
        )
        return created

    @staticmethod
    async def register_monster(user: User, monster_id: int) -> bool:
        """
        몬스터를 도감에 등록 (처치 시)

        Args:
            user: 대상 유저
            monster_id: 몬스터 ID

        Returns:
            새로 등록되었으면 True
        """
        _, created = await collection_repo.add_collection(
            user, CollectionType.MONSTER, monster_id
        )
        return created

    # ==========================================================================
    # 도감 조회
    # ==========================================================================

    @staticmethod
    async def get_collection_stats(user: User) -> CollectionStats:
        """
        도감 통계 조회

        Args:
            user: 대상 유저

        Returns:
            도감 통계
        """
        item_collected = await collection_repo.get_collection_count(
            user, CollectionType.ITEM
        )
        skill_collected = await collection_repo.get_collection_count(
            user, CollectionType.SKILL
        )
        monster_collected = await collection_repo.get_collection_count(
            user, CollectionType.MONSTER
        )

        return CollectionStats(
            item_collected=item_collected,
            item_total=len(item_cache),
            skill_collected=skill_collected,
            skill_total=len(skill_cache_by_id),
            monster_collected=monster_collected,
            monster_total=len(monster_cache_by_id),
        )

    @staticmethod
    async def get_collected_items(user: User) -> List[CollectionEntry]:
        """유저가 수집한 아이템 목록"""
        collected_ids = await collection_repo.get_collected_ids(
            user, CollectionType.ITEM
        )
        entries = []
        for item_id in collected_ids:
            item = item_cache.get(item_id)
            if item:
                entries.append(CollectionEntry(
                    id=item.id,
                    name=item.name,
                    description=item.description or "",
                    collection_type=CollectionType.ITEM,
                    is_collected=True
                ))
        return entries

    @staticmethod
    async def get_collected_skills(user: User) -> List[CollectionEntry]:
        """유저가 수집한 스킬 목록"""
        collected_ids = await collection_repo.get_collected_ids(
            user, CollectionType.SKILL
        )
        entries = []
        for skill_id in collected_ids:
            skill = skill_cache_by_id.get(skill_id)
            if skill:
                entries.append(CollectionEntry(
                    id=skill.id,
                    name=skill.name,
                    description=skill.description or "",
                    collection_type=CollectionType.SKILL,
                    is_collected=True
                ))
        return entries

    @staticmethod
    async def get_collected_monsters(user: User) -> List[CollectionEntry]:
        """유저가 수집한 몬스터 목록"""
        collected_ids = await collection_repo.get_collected_ids(
            user, CollectionType.MONSTER
        )
        entries = []
        for monster_id in collected_ids:
            monster = monster_cache_by_id.get(monster_id)
            if monster:
                entries.append(CollectionEntry(
                    id=monster.id,
                    name=monster.name,
                    description=monster.description or "",
                    collection_type=CollectionType.MONSTER,
                    is_collected=True
                ))
        return entries

    # ==========================================================================
    # 통합 검색
    # ==========================================================================

    @staticmethod
    async def search_entry(
        name: str,
        user: Optional[User] = None
    ) -> tuple[CollectionType, discord.Embed]:
        """
        이름으로 항목 검색 (아이템/스킬/몬스터)
        도감에 등록된 항목만 검색 가능

        Args:
            name: 검색할 이름
            user: 유저 (도감에서 해금된 항목만 검색 가능)

        Returns:
            (타입, Embed)

        Raises:
            EntryNotFoundError: 항목을 찾을 수 없거나 도감에 미등록
        """
        # 1. 아이템 검색
        item = await Item.filter(name=name).first()
        if item:
            is_collected = False
            if user:
                is_collected = await collection_repo.has_collection(
                    user, CollectionType.ITEM, item.id
                )
            if not is_collected:
                raise EntryNotFoundError(f"'{name}'을(를) 도감에서 찾을 수 없습니다.")
            embed = await CollectionService._create_item_embed(item, is_collected)
            return CollectionType.ITEM, embed

        # 2. 스킬 검색 (캐시에서)
        skill = CollectionService._find_skill_by_name(name)
        if skill:
            is_collected = False
            if user:
                is_collected = await collection_repo.has_collection(
                    user, CollectionType.SKILL, skill.id
                )
            if not is_collected:
                raise EntryNotFoundError(f"'{name}'을(를) 도감에서 찾을 수 없습니다.")
            embed = CollectionService._create_skill_embed(skill, is_collected)
            return CollectionType.SKILL, embed

        # 3. 몬스터 검색 (캐시에서)
        monster = CollectionService._find_monster_by_name(name)
        if monster:
            is_collected = False
            if user:
                is_collected = await collection_repo.has_collection(
                    user, CollectionType.MONSTER, monster.id
                )
            if not is_collected:
                raise EntryNotFoundError(f"'{name}'을(를) 도감에서 찾을 수 없습니다.")
            embed = CollectionService._create_monster_embed(monster, is_collected)
            return CollectionType.MONSTER, embed

        raise EntryNotFoundError(f"'{name}'을(를) 찾을 수 없습니다.")

    @staticmethod
    def _find_skill_by_name(name: str):
        """이름으로 스킬 찾기"""
        for skill in skill_cache_by_id.values():
            if skill.name == name:
                return skill
        return None

    @staticmethod
    def _find_monster_by_name(name: str):
        """이름으로 몬스터 찾기"""
        for monster in monster_cache_by_id.values():
            if monster.name == name:
                return monster
        return None

    # ==========================================================================
    # Embed 생성
    # ==========================================================================

    @staticmethod
    async def _create_item_embed(item: Item, is_collected: bool) -> discord.Embed:
        """아이템 Embed 생성"""
        embed = await item.get_description_embed()
        CollectionService._add_collection_status(embed, is_collected)
        return embed

    @staticmethod
    def _create_skill_embed(skill: Skill, is_collected: bool) -> discord.Embed:
        """스킬 Embed 생성"""
        embed = discord.Embed(
            title=f"✨ {skill.name}",
            description=skill.description or "설명 없음",
            color=discord.Color.purple()
        )

        # 컴포넌트 정보
        components_info = []
        for comp in skill.components:
            comp_name = type(comp).__name__.replace("Component", "")
            components_info.append(f"• {comp_name}")

        if components_info:
            embed.add_field(
                name="스킬 효과",
                value="\n".join(components_info),
                inline=False
            )

        CollectionService._add_collection_status(embed, is_collected)
        return embed

    @staticmethod
    def _create_monster_embed(monster: Monster, is_collected: bool) -> discord.Embed:
        """몬스터 Embed 생성"""
        embed = discord.Embed(
            title=f"👹 {monster.name}",
            description=monster.description or "설명 없음",
            color=discord.Color.red()
        )

        embed.add_field(
            name="기본 스탯",
            value=(
                f"```\n"
                f"HP     : {monster.hp}\n"
                f"공격력 : {monster.attack}\n"
                f"```"
            ),
            inline=False
        )

        CollectionService._add_collection_status(embed, is_collected)
        return embed

    @staticmethod
    def _add_collection_status(embed: discord.Embed, is_collected: bool):
        """도감 등록 상태 추가"""
        if is_collected:
            embed.set_footer(text="✅ 도감에 등록됨")
        else:
            embed.set_footer(text="❌ 도감에 미등록")
