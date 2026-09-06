"""Commands for roguelike rollout, brag channel, and box pity inspection."""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from bot import GUILD_IDS
from config import BOX_PITY_RULES
from models import UserStatEnum
from decorator.account import requires_account
from models.repos import find_account_by_discordid
from service.game_settings import set_brag_channel, set_roguelike_override, set_v4_feature_override
from service.item.box_open_service import BoxOpenService
from service.temp_admin_service import is_admin_or_temp


server_settings = app_commands.Group(
    name="서버설정",
    description="게임 기능의 서버별 설정을 관리합니다.",
    guild_ids=GUILD_IDS,
)


class GameSystemCommand(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @server_settings.command(name="로그라이크", description="일반 던전 로그라이크 적용을 설정합니다.")
    @app_commands.choices(상태=[
        app_commands.Choice(name="켜기", value="on"),
        app_commands.Choice(name="끄기", value="off"),
        app_commands.Choice(name="기본값", value="default"),
    ])
    async def roguelike_setting(self, interaction: discord.Interaction, 상태: app_commands.Choice[str]):
        if not interaction.guild_id or not is_admin_or_temp(interaction):
            await interaction.response.send_message("서버 관리자만 변경할 수 있습니다.", ephemeral=True)
            return
        enabled = {"on": True, "off": False, "default": None}[상태.value]
        await set_roguelike_override(interaction.guild_id, enabled)
        display = {True: "켜기", False: "끄기", None: "환경 기본값 사용"}[enabled]
        await interaction.response.send_message(f"로그라이크 던전: **{display}**", ephemeral=True)

    @server_settings.command(name="자랑채널", description="희귀 보상 알림 채널을 지정하거나 해제합니다.")
    async def brag_channel(self, interaction: discord.Interaction, 채널: discord.TextChannel | None = None):
        if not interaction.guild_id or not is_admin_or_temp(interaction):
            await interaction.response.send_message("서버 관리자만 변경할 수 있습니다.", ephemeral=True)
            return
        await set_brag_channel(interaction.guild_id, 채널.id if 채널 else None)
        text = 채널.mention if 채널 else "해제"
        await interaction.response.send_message(f"희귀 보상 자랑 채널: **{text}**", ephemeral=True)

    @server_settings.command(name="v4기능", description="파밍·세팅 V4 기능 플래그를 서버별로 설정합니다.")
    @app_commands.choices(
        기능=[
            app_commands.Choice(name="아이템 옵션", value="itemization_v4"),
            app_commands.Choice(name="목표 파밍", value="farming_focus"),
            app_commands.Choice(name="제작·재련", value="crafting_v4"),
            app_commands.Choice(name="통합 프리셋", value="build_presets_v4"),
            app_commands.Choice(name="세트 효과", value="set_effects_v4"),
        ],
        상태=[
            app_commands.Choice(name="켜기", value="on"),
            app_commands.Choice(name="끄기", value="off"),
            app_commands.Choice(name="기본값", value="default"),
        ],
    )
    async def v4_feature_setting(
        self, interaction: discord.Interaction,
        기능: app_commands.Choice[str], 상태: app_commands.Choice[str],
    ):
        if not interaction.guild_id or not is_admin_or_temp(interaction):
            await interaction.response.send_message("서버 관리자만 변경할 수 있습니다.", ephemeral=True)
            return
        enabled = {"on": True, "off": False, "default": None}[상태.value]
        await set_v4_feature_override(interaction.guild_id, 기능.value, enabled)
        display = {True: "켜기", False: "끄기", None: "환경 기본값 사용"}[enabled]
        await interaction.response.send_message(f"{기능.name}: **{display}**", ephemeral=True)

    @requires_account()
    @app_commands.command(name="상자천장", description="상자 티어별 천장 진행도를 확인합니다.")
    @app_commands.guilds(*GUILD_IDS)
    async def box_pity(self, interaction: discord.Interaction):
        user = await find_account_by_discordid(interaction.user.id)
        progress = await BoxOpenService.get_pity_progress(user)
        lines = []
        grade_names = {4: "A", 5: "S", 6: "SS", 7: "SSS"}
        for rule in BOX_PITY_RULES:
            failures = progress.get(rule.key, 0)
            remaining = max(0, rule.hard_pity - failures)
            lines.append(
                f"**{rule.key.upper()}** · {grade_names[rule.target_grade]} 이상\n"
                f"실패 {failures}회 / 확정까지 {remaining}회 (소프트 {rule.soft_start})"
            )
        await interaction.response.send_message(
            embed=discord.Embed(
                title="🎯 상자 천장 현황",
                description="\n\n".join(lines),
                color=discord.Color.blurple(),
            ),
            ephemeral=True,
        )

    @requires_account()
    @app_commands.command(name="전투분석", description="현재 장비·덱의 전투 성향과 약점을 분석합니다.")
    @app_commands.guilds(*GUILD_IDS)
    async def combat_analysis(self, interaction: discord.Interaction):
        from config import BALANCE_V2
        from service.item.equipment_service import EquipmentService
        from service.skill.skill_deck_service import SkillDeckService
        from models.repos.skill_repo import get_skill_by_id

        user = await find_account_by_discordid(interaction.user.id)
        await SkillDeckService.load_deck_to_user(user)
        await EquipmentService.apply_equipment_stats(user)
        stats = user.get_stat()
        active_designs = []
        passive_count = 0
        for skill_id in user.equipped_skill:
            if not skill_id:
                continue
            skill = get_skill_by_id(skill_id)
            if not skill:
                continue
            if skill.is_passive:
                passive_count += 1
            design = (getattr(skill.skill_model, "config", None) or {}).get("design", {})
            if design:
                active_designs.append(design)
        roles: dict[str, int] = {}
        archetypes: dict[str, int] = {}
        setup = set()
        payoff = set()
        for design in active_designs:
            roles[design["role"]] = roles.get(design["role"], 0) + 1
            archetypes[design["archetype"]] = archetypes.get(design["archetype"], 0) + 1
            setup.update(design.get("setup_tags", []))
            payoff.update(design.get("payoff_tags", []))
        orphan = sorted(payoff - setup)
        offense = max(
            stats.get(UserStatEnum.ATTACK, 0),
            stats.get(UserStatEnum.AP_ATTACK, 0),
        )
        avg_defense = (
            stats.get(UserStatEnum.DEFENSE, 0) + stats.get(UserStatEnum.AP_DEFENSE, 0)
        ) / 2
        embed = discord.Embed(
            title="📊 전투 분석",
            description="표시 수치는 현재 장비·스탯·덱을 V2 공식으로 평가한 결과입니다.",
            color=discord.Color.blurple(),
        )
        embed.add_field(
            name="핵심 수치",
            value=(
                f"공격 기준 **{offense:,.0f}** · HP **{stats.get(UserStatEnum.HP, 0):,}**\n"
                f"평균 피해 감소 **{BALANCE_V2.defense_reduction(avg_defense):.1%}** · "
                f"행동률 **×{BALANCE_V2.action_rate(stats.get(UserStatEnum.SPEED, 100)):.2f}**\n"
                f"명중 기대 **{BALANCE_V2.hit_rate(stats.get(UserStatEnum.ACCURACY, 95), 5):.1%}** · "
                f"치명타 **{min(70, stats.get(UserStatEnum.CRITICAL_RATE, 5))}%**"
            ),
            inline=False,
        )
        embed.add_field(
            name="덱 구조",
            value=(
                f"역할: {', '.join(f'{key} {value}' for key, value in sorted(roles.items())) or '없음'}\n"
                f"아키타입: {', '.join(f'{key} {value}' for key, value in sorted(archetypes.items())) or '없음'}\n"
                f"패시브 {passive_count}개"
            ),
            inline=False,
        )
        advice = []
        if orphan:
            advice.append("⚠️ 셋업 없이 소비하는 연계: " + ", ".join(orphan))
        if roles.get("sustain", 0) + roles.get("guardian", 0) < 2:
            advice.append("회복·보호 역할을 2칸 정도 확보하면 장기전 안정성이 좋아집니다.")
        if passive_count >= 7:
            advice.append("패시브 중첩 감쇠가 크게 적용됩니다. 한 액티브 반복 덱은 상태 대응력이 낮습니다.")
        if not advice:
            advice.append("셋업과 피니셔가 연결되어 있고 방어 슬롯도 확보되어 있습니다.")
        embed.add_field(name="조정 제안", value="\n".join(advice), inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="밸런스리포트", description="[관리자] 최근 라이브 밸런스 지표를 확인합니다.")
    @app_commands.guilds(*GUILD_IDS)
    async def balance_report(self, interaction: discord.Interaction, 일수: app_commands.Range[int, 1, 30] = 7):
        if not is_admin_or_temp(interaction):
            await interaction.response.send_message("관리자만 조회할 수 있습니다.", ephemeral=True)
            return
        from service.telemetry import balance_cohort_report

        report = await balance_cohort_report(일수)
        bands = "\n".join(
            f"Lv.{band}: {value['clear_rate']:.1%} ({value['clears']}/{value['runs']})"
            for band, value in report["clear_by_level_band"].items()
        ) or "완료된 던전 데이터 없음"
        embed = discord.Embed(title=f"⚖️ 최근 {일수}일 밸런스", color=discord.Color.gold())
        embed.add_field(name="클리어율", value=bands, inline=False)
        embed.add_field(
            name="경제",
            value=(
                f"획득 {report['gold_earned']:,} G · 소비 {report['gold_spent']:,} G\n"
                f"소모율 {report['gold_spend_ratio']:.1%} · 장비 교체 {report['equipment_replacements']}회"
            ),
            inline=False,
        )
        embed.set_footer(text=f"이벤트 {report['events']:,}건")
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    bot.tree.add_command(server_settings)
    await bot.add_cog(GameSystemCommand(bot))
