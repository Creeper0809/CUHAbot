"""
Collection Embeds

도감 항목의 Discord Embed 생성을 담당합니다.
"""
from typing import Optional

import discord

from models import Item, Monster


async def create_item_embed(item: Item, is_collected: bool) -> discord.Embed:
    """아이템 Embed 생성"""
    embed = await item.get_description_embed()
    _add_collection_status(embed, is_collected)
    return embed


def create_skill_embed(skill, is_collected: bool) -> discord.Embed:
    """스킬 Embed 생성"""
    color = _get_attribute_color(skill.attribute)

    embed = discord.Embed(
        title=f"✨ {skill.name}",
        description=skill.description or "설명 없음",
        color=color
    )

    _add_skill_basic_info(embed, skill)
    _add_skill_components_info(embed, skill)
    _add_skill_synergy_info(embed, skill)

    _add_collection_status(embed, is_collected)
    return embed


def create_monster_embed(monster: Monster, is_collected: bool) -> discord.Embed:
    """몬스터 Embed 생성"""
    from models.repos.skill_repo import get_skill_by_id

    monster_type = getattr(monster, 'monster_type', 'normal')
    color = _get_monster_type_color(monster_type)
    emoji = _get_monster_type_emoji(monster_type)

    main_desc = _extract_monster_description(monster)

    embed = discord.Embed(
        title=f"{emoji} {monster.name}",
        description=main_desc,
        color=color
    )

    _add_monster_type_field(embed, monster_type)
    _add_monster_level_field(embed, monster)
    _add_monster_reward_fields(embed, monster)
    _add_monster_stat_fields(embed, monster)
    _add_monster_skill_fields(embed, monster, get_skill_by_id)
    _add_monster_drop_fields(embed, monster_type)

    _add_collection_status(embed, is_collected)
    return embed


def create_keyword_embed(keyword: str) -> Optional[discord.Embed]:
    """키워드 정보 Embed 생성"""
    from service.skill.synergy_service import SynergyService
    from config import ATTRIBUTE_SYNERGIES
    from models.repos.static_cache import skill_cache_by_id

    skills_with_keyword = _find_skills_with_keyword(
        keyword, skill_cache_by_id, SynergyService
    )
    if not skills_with_keyword:
        return None

    color = _get_keyword_color(keyword)
    embed = discord.Embed(
        title=f"🔑 키워드: {keyword}",
        color=color,
        description=f"**{keyword}** 키워드를 가진 스킬 목록"
    )

    if keyword in ATTRIBUTE_SYNERGIES:
        tiers = ATTRIBUTE_SYNERGIES[keyword]
        synergy_lines = [f"• **×{tier.threshold}개**: {tier.effect}" for tier in tiers]
        embed.add_field(
            name="🔮 속성 밀도 시너지",
            value="\n".join(synergy_lines),
            inline=False
        )

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


def create_synergy_embed(synergy_name: str) -> Optional[discord.Embed]:
    """시너지 정보 Embed 생성"""
    from config import ATTRIBUTE_SYNERGIES, COMBO_SYNERGIES

    # 속성 밀도 시너지 검색
    embed = _try_create_attribute_synergy_embed(synergy_name, ATTRIBUTE_SYNERGIES)
    if embed:
        return embed

    # 복합 시너지 검색
    return _try_create_combo_synergy_embed(synergy_name, COMBO_SYNERGIES)


def _add_collection_status(embed: discord.Embed, is_collected: bool):
    """도감 등록 상태 추가"""
    if is_collected:
        embed.set_footer(text="✅ 도감에 등록됨")
    else:
        embed.set_footer(text="❌ 도감에 미등록")


# ==========================================================================
# 스킬 Embed 헬퍼
# ==========================================================================


def _get_attribute_color(attribute: str) -> discord.Color:
    """속성별 색상"""
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
    return attribute_colors.get(attribute, discord.Color.purple())


def _add_skill_basic_info(embed: discord.Embed, skill) -> None:
    """스킬 기본 정보 필드 추가"""
    info_lines = [f"**속성**: {skill.attribute}"]

    if skill.skill_model.grade:
        grade_map = {1: "D", 2: "C", 3: "B", 4: "A", 5: "S", 6: "SS", 7: "SSS", 8: "신화"}
        grade_name = grade_map.get(skill.skill_model.grade, "?")
        info_lines.append(f"**등급**: {grade_name}")

    if hasattr(skill.skill_model, 'keyword') and skill.skill_model.keyword:
        from service.skill.synergy_service import SynergyService
        keywords = SynergyService.parse_keywords(skill.skill_model.keyword)
        if keywords:
            info_lines.append(f"**키워드**: {', '.join(keywords)}")

    embed.add_field(name="📋 기본 정보", value="\n".join(info_lines), inline=False)


def _add_skill_components_info(embed: discord.Embed, skill) -> None:
    """스킬 컴포넌트 정보 필드 추가"""
    if not skill.components:
        return

    components_info = []
    for comp in skill.components:
        comp_type = type(comp).__name__.replace("Component", "")
        comp_detail = f"• **{comp_type}**"

        if hasattr(comp, 'damage_multiplier'):
            comp_detail += f"\n  └ 데미지: {int(comp.damage_multiplier * 100)}%"
        if hasattr(comp, 'heal_percent'):
            comp_detail += f"\n  └ 회복량: 최대 HP의 {int(comp.heal_percent * 100)}%"
        elif hasattr(comp, 'heal_amount'):
            comp_detail += f"\n  └ 회복량: {comp.heal_amount}"
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


def _add_skill_synergy_info(embed: discord.Embed, skill) -> None:
    """스킬 시너지 정보 필드 추가"""
    if not (hasattr(skill.skill_model, 'keyword') and skill.skill_model.keyword):
        return

    from service.skill.synergy_service import SynergyService
    from config import ATTRIBUTE_SYNERGIES, COMBO_SYNERGIES

    keywords = SynergyService.parse_keywords(skill.skill_model.keyword)
    related_synergies = []

    for keyword in keywords:
        if keyword in ATTRIBUTE_SYNERGIES:
            tiers = ATTRIBUTE_SYNERGIES[keyword]
            if tiers:
                first_tier = tiers[0]
                related_synergies.append(
                    f"• **{keyword} 밀도**: {first_tier.effect} (×{first_tier.threshold}개 이상)"
                )

    for combo in COMBO_SYNERGIES:
        for keyword in keywords:
            if keyword in combo.conditions and not keyword.startswith("__"):
                related_synergies.append(f"• **{combo.name}**: {combo.description}")
                break

    if related_synergies:
        embed.add_field(
            name="🔮 관련 시너지",
            value="\n".join(related_synergies[:5]),
            inline=False
        )


# ==========================================================================
# 몬스터 Embed 헬퍼
# ==========================================================================


def _get_monster_type_color(monster_type: str) -> discord.Color:
    """몬스터 타입별 색상"""
    type_colors = {
        "boss": discord.Color.dark_red(),
        "elite": discord.Color.orange(),
        "normal": discord.Color.red()
    }
    return type_colors.get(monster_type, discord.Color.red())


def _get_monster_type_emoji(monster_type: str) -> str:
    """몬스터 타입별 이모지"""
    type_emoji = {"boss": "👑", "elite": "⭐", "normal": "👹"}
    return type_emoji.get(monster_type, "👹")


def _extract_monster_description(monster: Monster) -> str:
    """몬스터 설명에서 메인 설명 추출"""
    description = monster.description or ""
    main_desc = description
    if "스킬 1:" in description:
        main_desc = description.split("스킬 1:")[0].strip()
    if not main_desc:
        main_desc = "무서운 기운이 느껴진다..."
    return main_desc


def _add_monster_type_field(embed: discord.Embed, monster_type: str) -> None:
    """몬스터 타입 필드"""
    type_name = {"boss": "보스", "elite": "엘리트", "normal": "일반"}.get(monster_type, "일반")
    embed.add_field(name="📌 타입", value=f"**{type_name}** 몬스터", inline=True)


def _add_monster_level_field(embed: discord.Embed, monster: Monster) -> None:
    """몬스터 레벨 필드"""
    if hasattr(monster, 'level'):
        embed.add_field(name="🔰 레벨", value=f"Lv.{monster.level}", inline=True)


def _add_monster_reward_fields(embed: discord.Embed, monster: Monster) -> None:
    """몬스터 보상 필드"""
    reward_info = []
    if hasattr(monster, 'exp_reward') and monster.exp_reward:
        reward_info.append(f"**경험치**: {monster.exp_reward} EXP")
    if hasattr(monster, 'gold_reward') and monster.gold_reward:
        reward_info.append(f"**골드**: {monster.gold_reward} G")

    if reward_info:
        embed.add_field(name="💰 보상", value="\n".join(reward_info), inline=False)


def _add_monster_stat_fields(embed: discord.Embed, monster: Monster) -> None:
    """몬스터 스탯 필드"""
    embed.add_field(name="❤️ 체력", value=f"{monster.hp:,}", inline=True)
    embed.add_field(name="⚔️ 공격력", value=f"{monster.attack}", inline=True)
    embed.add_field(name="🔮 마공", value=f"{getattr(monster, 'ap_attack', 0)}", inline=True)
    embed.add_field(name="🛡️ 방어력", value=f"{getattr(monster, 'defense', 0)}", inline=True)
    embed.add_field(name="🌀 마방", value=f"{getattr(monster, 'ap_defense', 0)}", inline=True)
    embed.add_field(name="💨 속도", value=f"{getattr(monster, 'speed', 10)}", inline=True)
    embed.add_field(name="💫 회피", value=f"{getattr(monster, 'evasion', 0)}%", inline=True)


def _add_monster_skill_fields(embed: discord.Embed, monster: Monster, get_skill_by_id) -> None:
    """몬스터 스킬 필드"""
    monster_skill_ids = getattr(monster, 'skill_ids', [])
    skill_lines = []
    for i, sid in enumerate(monster_skill_ids, 1):
        if sid != 0:
            skill = get_skill_by_id(sid)
            if skill:
                skill_desc = skill.description or "설명 없음"
                skill_lines.append(f"**스킬 {i}**: {skill.name}\n└ {skill_desc}")

    if skill_lines:
        embed.add_field(
            name="⚔️ 사용 스킬",
            value="\n\n".join(skill_lines),
            inline=False
        )


def _add_monster_drop_fields(embed: discord.Embed, monster_type: str) -> None:
    """몬스터 드랍 정보 필드"""
    drop_info_map = {
        "boss": "📦 **상자**: 상급/최상급 혼합 상자, A~S등급 장비/스킬 상자",
        "elite": "📦 **상자**: 중급 혼합 상자, B~A등급 장비/스킬 상자",
    }
    drop_info = drop_info_map.get(
        monster_type, "📦 **상자**: 하급 혼합 상자, D~C등급 장비/스킬 상자"
    )
    embed.add_field(name="🎁 드랍 아이템", value=drop_info, inline=False)


# ==========================================================================
# 키워드/시너지 Embed 헬퍼
# ==========================================================================


def _get_keyword_color(keyword: str) -> discord.Color:
    """키워드별 색상"""
    keyword_colors = {
        "화염": discord.Color.red(),
        "냉기": discord.Color.blue(),
        "번개": discord.Color.gold(),
        "수속성": discord.Color.teal(),
        "신성": discord.Color.from_rgb(255, 223, 0),
        "암흑": discord.Color.from_rgb(75, 0, 130),
        "물리": discord.Color.dark_gray(),
    }
    return keyword_colors.get(keyword, discord.Color.greyple())


def _find_skills_with_keyword(keyword: str, skill_cache, synergy_service) -> list:
    """특정 키워드를 가진 스킬 찾기 (플레이어 획득 가능 스킬만)"""
    skills = []
    for skill in skill_cache.values():
        if not (hasattr(skill.skill_model, 'keyword') and skill.skill_model.keyword):
            continue
        if not getattr(skill.skill_model, 'player_obtainable', True):
            continue
        keywords = synergy_service.parse_keywords(skill.skill_model.keyword)
        if keyword in keywords:
            skills.append(skill)
    return skills


def _try_create_attribute_synergy_embed(synergy_name: str, attribute_synergies) -> Optional[discord.Embed]:
    """속성 밀도 시너지 Embed 생성 시도"""
    for attribute, tiers in attribute_synergies.items():
        for tier in tiers:
            if synergy_name != f"{attribute} ×{tier.threshold}" and synergy_name != attribute:
                continue

            embed = discord.Embed(
                title=f"🔮 시너지: {attribute} 밀도",
                color=discord.Color.purple(),
                description=f"**{attribute}** 키워드를 가진 스킬을 모아 시너지를 발동하세요"
            )

            tier_lines = []
            for t in tiers:
                line = f"• **×{t.threshold}개**: {t.effect}"
                if t.damage_mult != 1.0:
                    line += f" (데미지 {t.damage_mult:.0%})"
                if t.status_duration_bonus > 0:
                    line += f" (지속시간 +{t.status_duration_bonus}턴)"
                if t.status_chance_bonus > 0:
                    line += f" (확률 +{t.status_chance_bonus:.0%})"
                tier_lines.append(line)

            embed.add_field(name="📊 단계별 효과", value="\n".join(tier_lines), inline=False)
            embed.add_field(
                name="🎯 발동 조건",
                value=f"덱에 **{attribute}** 키워드 스킬 3개 이상",
                inline=False
            )
            embed.set_footer(text="💡 더 많은 키워드를 모으면 더 강력한 시너지가 발동됩니다")
            return embed

    return None


def _try_create_combo_synergy_embed(synergy_name: str, combo_synergies) -> Optional[discord.Embed]:
    """복합 시너지 Embed 생성 시도"""
    for combo in combo_synergies:
        if synergy_name != combo.name:
            continue

        embed = discord.Embed(
            title=f"🔮 시너지: {combo.name}",
            color=discord.Color.purple(),
            description=combo.description
        )

        _add_combo_conditions(embed, combo)
        _add_combo_effects(embed, combo)

        embed.set_footer(text="💡 조건을 만족하는 스킬 덱을 구성하세요")
        return embed

    return None


def _add_combo_conditions(embed: discord.Embed, combo) -> None:
    """복합 시너지 조건 필드 추가"""
    condition_lines = []
    for keyword, count in combo.conditions.items():
        if keyword == "__attack_count__":
            condition_lines.append(f"• 공격 스킬 {count}개 이상")
        elif keyword == "__heal_buff_count__":
            condition_lines.append(f"• 회복/버프 스킬 {count}개 이상")
        else:
            condition_lines.append(f"• **{keyword}** 키워드 {count}개 이상")

    embed.add_field(name="🎯 발동 조건", value="\n".join(condition_lines), inline=False)


def _add_combo_effects(embed: discord.Embed, combo) -> None:
    """복합 시너지 효과 필드 추가"""
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
        embed.add_field(name="✨ 시너지 효과", value="\n".join(effect_lines), inline=False)
