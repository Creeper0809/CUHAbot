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
from models.repos import static_cache
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
    grade_id: Optional[int] = None  # 등급 ID (1=D, 2=C, 3=B, 4=A, 5=S)


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

        # 플레이어 획득 가능한 스킬만 카운트
        player_obtainable_skills = sum(
            1 for skill in static_cache.skill_cache_by_id.values()
            if getattr(skill.skill_model, 'player_obtainable', True)
        )

        return CollectionStats(
            item_collected=item_collected,
            item_total=len(static_cache.item_cache),
            skill_collected=skill_collected,
            skill_total=player_obtainable_skills,
            monster_collected=monster_collected,
            monster_total=len(static_cache.monster_cache_by_id),
        )

    @staticmethod
    async def get_collected_items(user: User) -> List[CollectionEntry]:
        """유저가 수집한 아이템 목록"""
        collected_ids = await collection_repo.get_collected_ids(
            user, CollectionType.ITEM
        )
        entries = []
        for item_id in collected_ids:
            item = static_cache.item_cache.get(item_id)
            if item:
                entries.append(CollectionEntry(
                    id=item.id,
                    name=item.name,
                    description=item.description or "",
                    collection_type=CollectionType.ITEM,
                    is_collected=True,
                    grade_id=getattr(item, 'grade_id', None)
                ))
        return entries

    @staticmethod
    async def get_collected_skills(user: User) -> List[CollectionEntry]:
        """유저가 수집한 스킬 목록 (플레이어 획득 가능한 스킬만)"""
        collected_ids = await collection_repo.get_collected_ids(
            user, CollectionType.SKILL
        )
        entries = []
        for skill_id in collected_ids:
            skill = static_cache.skill_cache_by_id.get(skill_id)
            if skill:
                # 플레이어 획득 불가능한 스킬 제외
                if not getattr(skill.skill_model, 'player_obtainable', True):
                    continue
                entries.append(CollectionEntry(
                    id=skill.id,
                    name=skill.name,
                    description=skill.description or "",
                    collection_type=CollectionType.SKILL,
                    is_collected=True,
                    grade_id=skill.skill_model.grade
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
            monster = static_cache.monster_cache_by_id.get(monster_id)
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

        # 4. 키워드 검색
        keyword_embed = CollectionService._create_keyword_embed(name)
        if keyword_embed:
            return CollectionType.SKILL, keyword_embed

        # 5. 시너지 검색
        synergy_embed = CollectionService._create_synergy_embed(name)
        if synergy_embed:
            return CollectionType.SKILL, synergy_embed

        raise EntryNotFoundError(f"'{name}'을(를) 찾을 수 없습니다.")

    @staticmethod
    def _find_skill_by_name(name: str):
        """이름으로 스킬 찾기 (플레이어 획득 가능한 스킬만)"""
        for skill in static_cache.skill_cache_by_id.values():
            if skill.name == name:
                # 플레이어 획득 가능한 스킬만 검색
                if getattr(skill.skill_model, 'player_obtainable', True):
                    return skill
        return None

    @staticmethod
    def _find_monster_by_name(name: str):
        """이름으로 몬스터 찾기"""
        for monster in static_cache.monster_cache_by_id.values():
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
        from models import Grade

        # 속성별 색상
        attribute_colors = {
            "화염": discord.Color.red(),
            "냉기": discord.Color.blue(),
            "번개": discord.Color.gold(),
            "수속성": discord.Color.teal(),
            "신성": discord.Color.from_rgb(255, 223, 0),
            "암흑": discord.Color.from_rgb(75, 0, 130),
            "물리": discord.Color.dark_gray(),
            "무속성": discord.Color.purple()
        }

        color = attribute_colors.get(skill.attribute, discord.Color.purple())

        embed = discord.Embed(
            title=f"✨ {skill.name}",
            description=skill.description or "설명 없음",
            color=color
        )

        # 기본 정보
        info_lines = []

        # 속성
        info_lines.append(f"**속성**: {skill.attribute}")

        # 등급 (비동기 호출 불가하므로 ID로 표시)
        if skill.skill_model.grade:
            grade_map = {1: "D", 2: "C", 3: "B", 4: "A", 5: "S", 6: "SS", 7: "SSS", 8: "신화"}
            grade_name = grade_map.get(skill.skill_model.grade, "?")
            info_lines.append(f"**등급**: {grade_name}")

        # 키워드
        if hasattr(skill.skill_model, 'keyword') and skill.skill_model.keyword:
            from service.synergy_service import SynergyService
            keywords = SynergyService.parse_keywords(skill.skill_model.keyword)
            if keywords:
                info_lines.append(f"**키워드**: {', '.join(keywords)}")

        embed.add_field(
            name="📋 기본 정보",
            value="\n".join(info_lines),
            inline=False
        )

        # 컴포넌트 정보 (상세)
        if skill.components:
            components_info = []
            for comp in skill.components:
                comp_type = type(comp).__name__.replace("Component", "")

                # 컴포넌트별 상세 정보
                comp_detail = f"• **{comp_type}**"

                # 데미지 정보
                if hasattr(comp, 'damage_multiplier'):
                    comp_detail += f"\n  └ 데미지: {int(comp.damage_multiplier * 100)}%"

                # 회복 정보
                if hasattr(comp, 'heal_percent'):
                    comp_detail += f"\n  └ 회복량: 최대 HP의 {int(comp.heal_percent * 100)}%"
                elif hasattr(comp, 'heal_amount'):
                    comp_detail += f"\n  └ 회복량: {comp.heal_amount}"

                # 버프 정보
                if hasattr(comp, 'stat_type'):
                    comp_detail += f"\n  └ 효과: {comp.stat_type}"
                    if hasattr(comp, 'value'):
                        comp_detail += f" +{comp.value}"
                    if hasattr(comp, 'duration'):
                        comp_detail += f" ({comp.duration}턴)"

                components_info.append(comp_detail)

            embed.add_field(
                name="⚔️ 스킬 효과",
                value="\n".join(components_info) if components_info else "정보 없음",
                inline=False
            )

        # 시너지 정보 (이 스킬이 기여할 수 있는 시너지)
        if hasattr(skill.skill_model, 'keyword') and skill.skill_model.keyword:
            from service.synergy_service import SynergyService
            from config import ATTRIBUTE_SYNERGIES, COMBO_SYNERGIES

            keywords = SynergyService.parse_keywords(skill.skill_model.keyword)
            related_synergies = []

            # 속성 시너지
            for keyword in keywords:
                if keyword in ATTRIBUTE_SYNERGIES:
                    tiers = ATTRIBUTE_SYNERGIES[keyword]
                    # 가장 낮은 단계만 표시
                    if tiers:
                        first_tier = tiers[0]
                        related_synergies.append(f"• **{keyword} 밀도**: {first_tier.effect} (×{first_tier.threshold}개 이상)")

            # 복합 시너지 (이 키워드가 필요한 시너지)
            for combo in COMBO_SYNERGIES:
                for keyword in keywords:
                    if keyword in combo.conditions and not keyword.startswith("__"):
                        related_synergies.append(f"• **{combo.name}**: {combo.description}")
                        break

            if related_synergies:
                embed.add_field(
                    name="🔮 관련 시너지",
                    value="\n".join(related_synergies[:5]),  # 최대 5개
                    inline=False
                )

        CollectionService._add_collection_status(embed, is_collected)
        return embed

    @staticmethod
    def _create_monster_embed(monster: Monster, is_collected: bool) -> discord.Embed:
        """몬스터 Embed 생성"""
        from models.repos.skill_repo import get_skill_by_id
        from models import UserStatEnum

        # 몬스터 타입별 색상
        type_colors = {
            "boss": discord.Color.dark_red(),
            "elite": discord.Color.orange(),
            "normal": discord.Color.red()
        }

        monster_type = getattr(monster, 'monster_type', 'normal')
        color = type_colors.get(monster_type, discord.Color.red())

        # 타입별 이모지
        type_emoji = {
            "boss": "👑",
            "elite": "⭐",
            "normal": "👹"
        }
        emoji = type_emoji.get(monster_type, "👹")

        # description에서 스킬 정보 분리
        description = monster.description or ""
        main_desc = description

        # "스킬 1:" 또는 "스킬 2:" 등이 있으면 그 앞까지만 표시
        if "스킬 1:" in description:
            main_desc = description.split("스킬 1:")[0].strip()

        # description이 비어있거나 스킬 정보만 있으면 기본 메시지
        if not main_desc:
            main_desc = "무서운 기운이 느껴진다..."

        embed = discord.Embed(
            title=f"{emoji} {monster.name}",
            description=main_desc,
            color=color
        )

        # 몬스터 타입
        type_name = {"boss": "보스", "elite": "엘리트", "normal": "일반"}.get(monster_type, "일반")
        embed.add_field(
            name="📌 타입",
            value=f"**{type_name}** 몬스터",
            inline=True
        )

        # 레벨 정보
        if hasattr(monster, 'level'):
            embed.add_field(
                name="🔰 레벨",
                value=f"Lv.{monster.level}",
                inline=True
            )

        # 보상 정보
        reward_info = []
        if hasattr(monster, 'exp_reward') and monster.exp_reward:
            reward_info.append(f"**경험치**: {monster.exp_reward} EXP")
        if hasattr(monster, 'gold_reward') and monster.gold_reward:
            reward_info.append(f"**골드**: {monster.gold_reward} G")

        if reward_info:
            embed.add_field(
                name="💰 보상",
                value="\n".join(reward_info),
                inline=False
            )

        # 기본 스탯 (전투 화면과 동일한 형식)
        embed.add_field(name="❤️ 체력", value=f"{monster.hp:,}", inline=True)
        embed.add_field(name="⚔️ 공격력", value=f"{monster.attack}", inline=True)
        embed.add_field(name="🔮 마공", value=f"{getattr(monster, 'ap_attack', 0)}", inline=True)
        embed.add_field(name="🛡️ 방어력", value=f"{getattr(monster, 'defense', 0)}", inline=True)
        embed.add_field(name="🌀 마방", value=f"{getattr(monster, 'ap_defense', 0)}", inline=True)
        embed.add_field(name="💨 속도", value=f"{getattr(monster, 'speed', 10)}", inline=True)
        embed.add_field(name="💫 회피", value=f"{getattr(monster, 'evasion', 0)}%", inline=True)

        # 스킬 정보
        monster_skill_ids = getattr(monster, 'skill_ids', [])
        skill_lines = []
        for i, sid in enumerate(monster_skill_ids, 1):
            if sid != 0:
                skill = get_skill_by_id(sid)
                if skill:
                    # 스킬 이름과 효과 설명을 함께 표시
                    skill_desc = skill.description or "설명 없음"
                    skill_lines.append(f"**스킬 {i}**: {skill.name}\n└ {skill_desc}")

        if skill_lines:
            embed.add_field(
                name="⚔️ 사용 스킬",
                value="\n\n".join(skill_lines),
                inline=False
            )

        # 드랍 정보
        drop_info = []

        # 상자 드랍
        if monster_type == "boss":
            drop_info.append("📦 **상자**: 상급/최상급 혼합 상자, A~S등급 장비/스킬 상자")
        elif monster_type == "elite":
            drop_info.append("📦 **상자**: 중급 혼합 상자, B~A등급 장비/스킬 상자")
        else:
            drop_info.append("📦 **상자**: 하급 혼합 상자, D~C등급 장비/스킬 상자")

        if drop_info:
            embed.add_field(
                name="🎁 드랍 아이템",
                value="\n".join(drop_info),
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

    @staticmethod
    def _create_keyword_embed(keyword: str) -> Optional[discord.Embed]:
        """키워드 정보 Embed 생성"""
        from service.synergy_service import SynergyService
        from config import ATTRIBUTE_SYNERGIES
        from models.repos.static_cache import skill_cache_by_id

        # 이 키워드를 가진 스킬 찾기 (플레이어 획득 가능한 스킬만)
        skills_with_keyword = []
        for skill in skill_cache_by_id.values():
            if hasattr(skill.skill_model, 'keyword') and skill.skill_model.keyword:
                # 플레이어 획득 불가능한 스킬 제외
                if not getattr(skill.skill_model, 'player_obtainable', True):
                    continue
                keywords = SynergyService.parse_keywords(skill.skill_model.keyword)
                if keyword in keywords:
                    skills_with_keyword.append(skill)

        if not skills_with_keyword:
            return None

        # 키워드별 색상
        keyword_colors = {
            "화염": discord.Color.red(),
            "냉기": discord.Color.blue(),
            "번개": discord.Color.gold(),
            "수속성": discord.Color.teal(),
            "신성": discord.Color.from_rgb(255, 223, 0),
            "암흑": discord.Color.from_rgb(75, 0, 130),
            "물리": discord.Color.dark_gray(),
        }

        embed = discord.Embed(
            title=f"🔑 키워드: {keyword}",
            color=keyword_colors.get(keyword, discord.Color.greyple()),
            description=f"**{keyword}** 키워드를 가진 스킬 목록"
        )

        # 관련 시너지 표시
        if keyword in ATTRIBUTE_SYNERGIES:
            tiers = ATTRIBUTE_SYNERGIES[keyword]
            synergy_lines = []
            for tier in tiers:
                synergy_lines.append(f"• **×{tier.threshold}개**: {tier.effect}")

            embed.add_field(
                name="🔮 속성 밀도 시너지",
                value="\n".join(synergy_lines),
                inline=False
            )

        # 스킬 목록 (최대 10개)
        skill_names = [f"• {skill.name}" for skill in skills_with_keyword[:10]]
        if len(skills_with_keyword) > 10:
            skill_names.append(f"... 외 {len(skills_with_keyword) - 10}개")

        embed.add_field(
            name=f"⚔️ 관련 스킬 ({len(skills_with_keyword)}개)",
            value="\n".join(skill_names),
            inline=False
        )

        embed.set_footer(text="💡 스킬 덱에 같은 키워드를 여러 개 모아 시너지를 발동하세요")
        return embed

    @staticmethod
    def _create_synergy_embed(synergy_name: str) -> Optional[discord.Embed]:
        """시너지 정보 Embed 생성"""
        from config import ATTRIBUTE_SYNERGIES, COMBO_SYNERGIES

        # 속성 밀도 시너지 검색
        for attribute, tiers in ATTRIBUTE_SYNERGIES.items():
            for tier in tiers:
                # "화염 ×3", "화염 ×5" 등의 형식으로 검색
                if synergy_name == f"{attribute} ×{tier.threshold}" or synergy_name == attribute:
                    embed = discord.Embed(
                        title=f"🔮 시너지: {attribute} 밀도",
                        color=discord.Color.purple(),
                        description=f"**{attribute}** 키워드를 가진 스킬을 모아 시너지를 발동하세요"
                    )

                    # 모든 단계 표시
                    tier_lines = []
                    for t in tiers:
                        tier_lines.append(f"• **×{t.threshold}개**: {t.effect}")
                        if t.damage_mult != 1.0:
                            tier_lines[-1] += f" (데미지 {t.damage_mult:.0%})"
                        if t.status_duration_bonus > 0:
                            tier_lines[-1] += f" (지속시간 +{t.status_duration_bonus}턴)"
                        if t.status_chance_bonus > 0:
                            tier_lines[-1] += f" (확률 +{t.status_chance_bonus:.0%})"

                    embed.add_field(
                        name="📊 단계별 효과",
                        value="\n".join(tier_lines),
                        inline=False
                    )

                    embed.add_field(
                        name="🎯 발동 조건",
                        value=f"덱에 **{attribute}** 키워드 스킬 3개 이상",
                        inline=False
                    )

                    embed.set_footer(text="💡 더 많은 키워드를 모으면 더 강력한 시너지가 발동됩니다")
                    return embed

        # 복합 시너지 검색
        for combo in COMBO_SYNERGIES:
            if synergy_name == combo.name:
                embed = discord.Embed(
                    title=f"🔮 시너지: {combo.name}",
                    color=discord.Color.purple(),
                    description=combo.description
                )

                # 조건 표시
                condition_lines = []
                for keyword, count in combo.conditions.items():
                    if keyword == "__attack_count__":
                        condition_lines.append(f"• 공격 스킬 {count}개 이상")
                    elif keyword == "__heal_buff_count__":
                        condition_lines.append(f"• 회복/버프 스킬 {count}개 이상")
                    else:
                        condition_lines.append(f"• **{keyword}** 키워드 {count}개 이상")

                embed.add_field(
                    name="🎯 발동 조건",
                    value="\n".join(condition_lines),
                    inline=False
                )

                # 효과 표시
                effect_lines = []
                if combo.damage_mult != 1.0:
                    if combo.damage_mult > 1.0:
                        effect_lines.append(f"• 데미지 **+{(combo.damage_mult - 1) * 100:.0f}%**")
                    else:
                        effect_lines.append(f"• 데미지 **{(1 - combo.damage_mult) * 100:.0f}%** 감소")

                if combo.damage_taken_mult != 1.0:
                    if combo.damage_taken_mult > 1.0:
                        effect_lines.append(f"• 받는 피해 **+{(combo.damage_taken_mult - 1) * 100:.0f}%**")
                    else:
                        effect_lines.append(f"• 받는 피해 **-{(1 - combo.damage_taken_mult) * 100:.0f}%**")

                if combo.lifesteal_bonus > 0:
                    effect_lines.append(f"• 흡혈 **+{combo.lifesteal_bonus * 100:.0f}%**")

                if effect_lines:
                    embed.add_field(
                        name="✨ 시너지 효과",
                        value="\n".join(effect_lines),
                        inline=False
                    )

                embed.set_footer(text="💡 조건을 만족하는 스킬 덱을 구성하세요")
                return embed

        return None
