"""
유저 관련 명령어 (우편, 업적 등)
"""
import logging
import os
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from bot import GUILD_IDS
from decorator.account import requires_account
from models.repos import find_account_by_discordid
from service.mail import MailService, MailNotFoundError, NoRewardError, AlreadyClaimedError
from service.achievement import AchievementProgressTracker
from service.ranking_service import RankingService
from models.achievement import Achievement, AchievementCategory
from models.user_achievement import UserAchievement
from models.mail import Mail
from views.ranking_view import RankingView

logger = logging.getLogger(__name__)


class UserCommand(commands.Cog):
    """유저 관련 명령어"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ==================== 우편 명령어 ====================

    @app_commands.command(name="우편", description="📬 우편함을 확인합니다")
    @app_commands.guilds(*GUILD_IDS)
    @requires_account()
    async def mail_list(self, interaction: discord.Interaction):
        """우편 목록 조회"""
        user = await find_account_by_discordid(interaction.user.id)
        if not user:
            await interaction.response.send_message("❌ 유저를 찾을 수 없습니다.", ephemeral=True)
            return

        mails = await MailService.get_user_mails(user.id, limit=20)
        unread_count = await MailService.get_unread_count(user.id)

        if not mails:
            embed = discord.Embed(
                title="📬 우편함",
                description="📭 우편함이 비어 있습니다.",
                color=discord.Color.light_gray()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        embed = discord.Embed(
            title=f"📬 우편함 ({len(mails)}건)",
            description=f"📩 새 우편: {unread_count}건",
            color=discord.Color.blue()
        )

        for mail in mails[:10]:  # 최대 10개만 표시
            # 읽음 여부 표시
            status_icon = "📩" if not mail.is_read else "📭"

            # 보상 표시
            reward_text = ""
            if mail.reward_config:
                rewards = []
                if mail.reward_config.get("exp"):
                    rewards.append(f"✨ {mail.reward_config['exp']}")
                if mail.reward_config.get("gold"):
                    rewards.append(f"💰 {mail.reward_config['gold']}")
                if mail.reward_config.get("items"):
                    rewards.append(f"🎁 x{len(mail.reward_config['items'])}")
                reward_text = " | ".join(rewards)

                if mail.is_claimed:
                    reward_text += " (수령 완료)"
            else:
                reward_text = "보상 없음"

            # 만료 시간
            time_text = mail.created_at.strftime("%m/%d %H:%M")

            embed.add_field(
                name=f"{status_icon} {mail.title}",
                value=(
                    f"발신: {mail.sender} | {time_text}\n"
                    f"보상: {reward_text}\n"
                    f"ID: `{mail.id}`"
                ),
                inline=False
            )

        embed.set_footer(text="💡 /우편읽기 <ID> 로 우편을 확인하세요 | /우편모두수령 으로 일괄 수령")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="우편읽기", description="📩 우편을 읽고 보상을 수령합니다")
    @app_commands.describe(mail_id="우편 ID")
    @app_commands.guilds(*GUILD_IDS)
    @requires_account()
    async def mail_read(self, interaction: discord.Interaction, mail_id: int):
        """우편 읽기 및 보상 수령"""
        user = await find_account_by_discordid(interaction.user.id)
        if not user:
            await interaction.response.send_message("❌ 유저를 찾을 수 없습니다.", ephemeral=True)
            return

        try:
            # 우편 읽기
            mail = await MailService.read_mail(mail_id, user.id)

            embed = discord.Embed(
                title="📩 우편",
                color=discord.Color.blue()
            )

            embed.add_field(name="제목", value=mail.title, inline=False)
            embed.add_field(name="발신", value=mail.sender, inline=True)
            embed.add_field(
                name="날짜",
                value=mail.created_at.strftime("%Y-%m-%d %H:%M"),
                inline=True
            )
            embed.add_field(name="내용", value=mail.content, inline=False)

            # 보상 표시
            if mail.reward_config and not mail.is_claimed:
                reward_text = []
                if mail.reward_config.get("exp"):
                    reward_text.append(f"✨ 경험치: {mail.reward_config['exp']}")
                if mail.reward_config.get("gold"):
                    reward_text.append(f"💰 골드: {mail.reward_config['gold']}")
                if mail.reward_config.get("items"):
                    reward_text.append(f"🎁 아이템: {len(mail.reward_config['items'])}개")

                embed.add_field(
                    name="📦 첨부된 보상",
                    value="\n".join(reward_text),
                    inline=False
                )

                # 보상 수령
                try:
                    reward = await MailService.claim_reward(mail_id, user.id)

                    reward_received = []
                    if reward.get("exp"):
                        reward_received.append(f"✨ 경험치 +{reward['exp']}")
                    if reward.get("gold"):
                        reward_received.append(f"💰 골드 +{reward['gold']}")
                    if reward.get("items"):
                        reward_received.append(f"🎁 아이템 {len(reward['items'])}개")

                    embed.add_field(
                        name="✅ 보상 수령 완료",
                        value="\n".join(reward_received),
                        inline=False
                    )

                except AlreadyClaimedError:
                    embed.add_field(name="ℹ️ 상태", value="이미 수령한 보상입니다", inline=False)
                except Exception as e:
                    logger.error(f"Failed to claim mail reward: {e}")
                    embed.add_field(name="❌ 오류", value="보상 수령 실패", inline=False)

            elif mail.is_claimed:
                embed.add_field(name="ℹ️ 상태", value="수령 완료", inline=False)

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except MailNotFoundError:
            await interaction.response.send_message(
                "❌ 우편을 찾을 수 없습니다.",
                ephemeral=True
            )

    @app_commands.command(name="우편모두수령", description="📦 모든 우편 보상을 일괄 수령합니다")
    @app_commands.guilds(*GUILD_IDS)
    @requires_account()
    async def mail_claim_all(self, interaction: discord.Interaction):
        """모든 우편 보상 일괄 수령"""
        user = await find_account_by_discordid(interaction.user.id)
        if not user:
            await interaction.response.send_message("❌ 유저를 찾을 수 없습니다.", ephemeral=True)
            return

        try:
            reward = await MailService.claim_all_rewards(user.id)

            if reward["exp"] == 0 and reward["gold"] == 0 and not reward["items"]:
                await interaction.response.send_message(
                    "📭 수령할 보상이 없습니다.",
                    ephemeral=True
                )
                return

            embed = discord.Embed(
                title="✅ 보상 일괄 수령 완료!",
                color=discord.Color.green()
            )

            reward_text = []
            if reward["exp"] > 0:
                reward_text.append(f"✨ 경험치: +{reward['exp']}")
            if reward["gold"] > 0:
                reward_text.append(f"💰 골드: +{reward['gold']}")
            if reward["items"]:
                reward_text.append(f"🎁 아이템: {len(reward['items'])}개")

            embed.description = "\n".join(reward_text)

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Failed to claim all mail rewards: {e}")
            await interaction.response.send_message(
                "❌ 보상 수령 중 오류가 발생했습니다.",
                ephemeral=True
            )

    # ==================== 업적 명령어 ====================

    @app_commands.command(name="업적", description="🏆 업적 목록을 확인합니다")
    @app_commands.describe(
        category="업적 카테고리 (combat/exploration/combat_mastery/collection/wealth/growth)"
    )
    @app_commands.guilds(*GUILD_IDS)
    @requires_account()
    async def achievement_list(
        self,
        interaction: discord.Interaction,
        category: Optional[str] = None
    ):
        """업적 목록 조회"""
        user = await find_account_by_discordid(interaction.user.id)
        if not user:
            await interaction.response.send_message("❌ 유저를 찾을 수 없습니다.", ephemeral=True)
            return

        # 카테고리 필터
        if category:
            try:
                cat_enum = AchievementCategory(category)
                achievements = await Achievement.filter(category=cat_enum).order_by("tier").all()
            except ValueError:
                await interaction.response.send_message(
                    "❌ 잘못된 카테고리입니다. (combat/exploration/combat_mastery/collection/wealth/growth)",
                    ephemeral=True
                )
                return
        else:
            achievements = await Achievement.filter().order_by("category", "tier").all()

        if not achievements:
            await interaction.response.send_message(
                "❌ 업적을 찾을 수 없습니다.",
                ephemeral=True
            )
            return

        # 유저 업적 진행도 조회
        user_achievements = {
            ua.achievement_id: ua
            for ua in await UserAchievement.filter(user_id=user.id).all()
        }

        # 카테고리별 그룹핑
        from collections import defaultdict
        grouped = defaultdict(list)
        for ach in achievements:
            grouped[ach.category].append(ach)

        # 통계
        total_count = len(achievements)
        completed_count = sum(1 for ua in user_achievements.values() if ua.is_completed)

        embed = discord.Embed(
            title="🏆 업적 목록",
            description=f"진행 중: {total_count - completed_count}개 | 완료: {completed_count}개 | 전체: {total_count}개",
            color=discord.Color.gold()
        )

        # 카테고리 이름 매핑
        category_names = {
            AchievementCategory.COMBAT: "⚔️ 전투 업적",
            AchievementCategory.EXPLORATION: "🏃 탐험 업적",
            AchievementCategory.COMBAT_MASTERY: "🎯 전투 마스터 업적",
            AchievementCategory.COLLECTION: "📦 수집 업적",
            AchievementCategory.WEALTH: "💰 재화 업적",
            AchievementCategory.GROWTH: "🌱 성장 업적",
        }

        for cat, achs in list(grouped.items())[:3]:  # 최대 3개 카테고리만 표시
            cat_name = category_names.get(cat, cat.value)
            lines = []

            for ach in achs[:5]:  # 각 카테고리당 최대 5개
                user_ach = user_achievements.get(ach.id)

                if user_ach:
                    if user_ach.is_completed:
                        status = "✅"
                        progress = f"완료 ({user_ach.completed_at.strftime('%m/%d')})"
                    else:
                        status = "⏳"
                        progress = f"[{user_ach.progress_current}/{user_ach.progress_required}]"
                else:
                    status = "🔒"
                    progress = "미시작"

                lines.append(f"{status} **{ach.name} {ach.tier_name}** - {progress}")

            if lines:
                embed.add_field(
                    name=cat_name,
                    value="\n".join(lines),
                    inline=False
                )

        embed.set_footer(text="💡 카테고리를 지정하면 해당 카테고리의 업적만 볼 수 있습니다")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ==================== 랭킹 명령어 ====================

    @app_commands.command(name="랭킹", description="🏆 플레이어 랭킹을 확인합니다")
    @app_commands.guilds(*GUILD_IDS)
    @requires_account()
    async def ranking(self, interaction: discord.Interaction):
        """랭킹 조회 명령어"""
        # Defer response (데이터 로딩 시간 고려)
        await interaction.response.defer(ephemeral=True)

        # 사용자 조회
        user = await find_account_by_discordid(interaction.user.id)
        if not user:
            await interaction.followup.send("❌ 유저를 찾을 수 없습니다.", ephemeral=True)
            return

        # View 생성 및 데이터 로딩
        view = RankingView(interaction.user, user)
        await view.load_data()

        # 초기 Embed 생성
        embed = view.create_embed()

        # 메시지 전송 및 View에 메시지 참조 저장
        message = await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        view.message = message

        if os.getenv("E2E_UI_AUTOPILOT") == "TRUE":
            await view.e2e_autopilot(interaction)


async def setup(bot: commands.Bot):
    await bot.add_cog(UserCommand(bot))
