import discord
from discord import app_commands
from discord.ext import commands

from DTO.dungeon_select_view import DungeonSelectView
from DTO.skill_deck_view import SkillDeckView
from DTO.user_info_view import UserInfoView
from bot import GUILD_ID
from decorator.account import requires_account
from models.repos import find_account_by_discordid
from models.repos.dungeon_repo import find_all_dungeon
from models.repos.static_cache import skill_cache_by_id
from models.user_stats import UserStats
from models.user_equipment import UserEquipment
from service.dungeon.dungeon_service import start_dungeon
from service.dungeon.item_service import get_item_info, ItemNotFoundException
from service.session import is_in_session, is_in_combat, create_session, end_session
from service.skill_deck_service import SkillDeckService
from models import User


class DungeonCommand(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @requires_account()
    @app_commands.command(
        name="던전입장",
        description="던전에 입장합니다"
    )
    @app_commands.guilds(GUILD_ID)
    async def enter_dungeon(self, interaction: discord.Interaction):
        if is_in_session(interaction.user.id):
            await interaction.response.send_message("이미 던전 탐험중입니다.")
            return
        session = create_session(interaction.user.id)

        user: User = await find_account_by_discordid(session.user_id)
        session.user = user

        dungeons = find_all_dungeon()
        if not dungeons:
            await interaction.response.send_message("등록된 던전이 없습니다.")
            return
        embed = discord.Embed(
            title="🎯 던전을 선택하세요",
            description="드롭다운에서 던전을 선택한 후 입장하거나 취소하세요.",
            color=discord.Color.blurple()
        )
        view = DungeonSelectView(interaction.user, dungeons, session)
        message = await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()
        await view.wait()
        if view.selected_dungeon is None:
            await interaction.followup.send("던전 입장이 취소되었습니다.")
            await end_session(user_id=interaction.user.id)
            return

        # 레벨 체크 (방어 로직)
        if user.level < view.selected_dungeon.require_level:
            await interaction.followup.send(
                f"⚠️ 레벨이 부족합니다. (현재: {user.level}, 필요: {view.selected_dungeon.require_level})"
            )
            await end_session(user_id=interaction.user.id)
            return

        await interaction.followup.send(f"{view.selected_dungeon.name} 던전에 입장합니다!")

        session.dungeon = view.selected_dungeon

        ended = await start_dungeon(session, interaction)
        await end_session(user_id=interaction.user.id)

    @app_commands.command(
        name="아이템검색",
        description="아이템 정보를 검색합니다"
    )
    @app_commands.guilds(GUILD_ID)
    @app_commands.describe(item_name="검색할 아이템 이름")
    async def search_item(self, interaction: discord.Interaction, item_name: str):
        """아이템 정보 검색"""
        try:
            embed = await get_item_info(item_name)
            await interaction.response.send_message(embed=embed)
        except ItemNotFoundException as e:
            await interaction.response.send_message(str(e))

    @requires_account()
    @app_commands.command(
        name="내정보",
        description="내 캐릭터 정보를 확인합니다 (스탯, 장비, 스킬)"
    )
    @app_commands.guilds(GUILD_ID)
    async def my_info(self, interaction: discord.Interaction):
        """내 정보 조회"""
        user: User = await find_account_by_discordid(interaction.user.id)
        if not user:
            await interaction.response.send_message(
                "등록된 계정이 없습니다. `/등록`을 먼저 해주세요.",
                ephemeral=True
            )
            return

        # 스탯 정보 로드
        stats = await UserStats.get_or_none(user=user)

        # 장비 정보 로드
        equipment = await UserEquipment.filter(user=user).prefetch_related("inventory_item")

        # 스킬 덱 로드
        skill_deck = await SkillDeckService.get_deck_as_list(user)

        # View 생성
        view = UserInfoView(
            discord_user=interaction.user,
            user=user,
            stats=stats,
            equipment=list(equipment),
            skill_deck=skill_deck
        )

        embed = view.create_embed()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @requires_account()
    @app_commands.command(
        name="덱",
        description="스킬 덱을 확인하고 편집합니다"
    )
    @app_commands.guilds(GUILD_ID)
    async def skill_deck(self, interaction: discord.Interaction):
        """스킬 덱 확인 및 편집"""
        # 전투 중 체크
        if is_in_combat(interaction.user.id):
            await interaction.response.send_message(
                "⚠️ 전투 중에는 덱을 변경할 수 없습니다!",
                ephemeral=True
            )
            return

        user: User = await find_account_by_discordid(interaction.user.id)
        if not user:
            await interaction.response.send_message(
                "등록된 계정이 없습니다. `/등록`을 먼저 해주세요.",
                ephemeral=True
            )
            return

        # 현재 덱 로드
        current_deck = await SkillDeckService.get_deck_as_list(user)

        # 보유 스킬 목록 (캐시에서 가져오기)
        available_skills = list(skill_cache_by_id.values())

        # View 생성 및 초기화 (프리셋 로드)
        view = SkillDeckView(
            user=interaction.user,
            current_deck=current_deck,
            available_skills=available_skills,
            db_user=user
        )
        await view.initialize()

        embed = view.create_embed()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        view.message = await interaction.original_response()

        # 사용자 응답 대기
        await view.wait()

        # 저장 처리
        if view.saved and view.changes_made:
            for slot_index, skill_id in enumerate(view.current_deck):
                await SkillDeckService.set_skill(user, slot_index, skill_id)

            # 유저 객체에 덱 로드
            await SkillDeckService.load_deck_to_user(user)


async def setup(bot):
    await bot.add_cog(DungeonCommand(bot))
