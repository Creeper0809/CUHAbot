import discord
from discord import app_commands
from discord.ext import commands

from DTO.collection_view import CollectionView
from DTO.dungeon_select_view import DungeonSelectView
from DTO.skill_deck_view import SkillDeckView
from DTO.stat_distribution_view import StatDistributionView
from DTO.user_info_view import UserInfoView
from bot import GUILD_ID
from decorator.account import requires_account
from models.repos import find_account_by_discordid
from models.repos.dungeon_repo import find_all_dungeon
from models.repos.static_cache import skill_cache_by_id
from models.user_stats import UserStats
from models.user_equipment import UserEquipment
from service.dungeon.dungeon_service import start_dungeon
from service.collection_service import CollectionService, EntryNotFoundError
from service.dungeon.item_service import get_item_info, ItemNotFoundException
from service.healing_service import HealingService
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

        # 스킬 덱 로드 (전투에서 사용)
        await SkillDeckService.load_deck_to_user(user)

        # 자연 회복 적용
        await HealingService.apply_natural_regen(user)

        # HP 체크 - 너무 낮으면 경고
        hp_percent = (user.now_hp / user.hp) * 100
        if hp_percent < 30:
            # 완전 회복까지 예상 시간 계산
            hp_needed = int(user.hp * 0.3) - user.now_hp
            minutes_needed = (hp_needed + user.hp_regen - 1) // user.hp_regen if user.hp_regen > 0 else 999

            await interaction.response.send_message(
                f"⚠️ HP가 너무 낮습니다! ({user.now_hp}/{user.hp}, {hp_percent:.0f}%)\n"
                f"HP 30% 이상이 되어야 입장 가능합니다.\n"
                f"자연 회복으로 약 **{minutes_needed}분** 후 입장 가능합니다.",
                ephemeral=True
            )
            await end_session(user_id=interaction.user.id)
            return

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

    @app_commands.command(
        name="설명",
        description="아이템, 스킬, 몬스터 정보를 검색합니다"
    )
    @app_commands.guilds(GUILD_ID)
    @app_commands.describe(이름="검색할 이름 (아이템/스킬/몬스터)")
    async def search_entry(self, interaction: discord.Interaction, 이름: str):
        """통합 검색 (아이템/스킬/몬스터)"""
        # 유저 정보 (도감 등록 여부 표시용)
        user = await find_account_by_discordid(interaction.user.id)

        try:
            _, embed = await CollectionService.search_entry(이름, user)
            await interaction.response.send_message(embed=embed)
        except EntryNotFoundError as e:
            await interaction.response.send_message(str(e), ephemeral=True)

    @requires_account()
    @app_commands.command(
        name="도감",
        description="수집한 아이템, 스킬, 몬스터 도감을 확인합니다"
    )
    @app_commands.guilds(GUILD_ID)
    async def collection(self, interaction: discord.Interaction):
        """도감 조회"""
        user: User = await find_account_by_discordid(interaction.user.id)
        if not user:
            await interaction.response.send_message(
                "등록된 계정이 없습니다. `/등록`을 먼저 해주세요.",
                ephemeral=True
            )
            return

        # 도감 데이터 로드
        stats = await CollectionService.get_collection_stats(user)
        items = await CollectionService.get_collected_items(user)
        skills = await CollectionService.get_collected_skills(user)
        monsters = await CollectionService.get_collected_monsters(user)

        # View 생성
        view = CollectionView(
            discord_user=interaction.user,
            user=user,
            stats=stats,
            items=items,
            skills=skills,
            monsters=monsters
        )

        embed = view.create_embed()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

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

        # 자연 회복 적용 (HP 정보 표시 전 자동 적용)
        await HealingService.apply_natural_regen(user)

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

        # 현재 덱에 있는 스킬을 도감에 자동 등록 (기존 유저 호환)
        for skill_id in set(current_deck):
            if skill_id != 0:
                await CollectionService.register_skill(user, skill_id)

        # 보유 스킬 목록 (도감에 등록된 스킬만)
        collected_skills = await CollectionService.get_collected_skills(user)
        available_skills = [
            skill_cache_by_id[entry.id]
            for entry in collected_skills
            if entry.id in skill_cache_by_id
        ]

        if not available_skills:
            await interaction.response.send_message(
                "⚠️ 보유한 스킬이 없습니다.\n"
                "던전에서 스킬을 획득하거나, 상점에서 스킬을 구매하세요.",
                ephemeral=True
            )
            return

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

    @requires_account()
    @app_commands.command(
        name="치유",
        description="[관리자] 대상의 HP를 완전히 회복합니다"
    )
    @app_commands.guilds(GUILD_ID)
    @app_commands.describe(target="회복시킬 대상 (미지정시 자신)")
    async def heal(self, interaction: discord.Interaction, target: discord.Member = None):
        """관리자용 완전 회복"""
        # 관리자 체크
        user: User = await find_account_by_discordid(interaction.user.id)
        if not user or user.user_role != "admin":
            await interaction.response.send_message(
                "⚠️ 관리자만 사용할 수 있는 명령어입니다.",
                ephemeral=True
            )
            return

        # 대상 결정
        target_discord_id = target.id if target else interaction.user.id
        target_user: User = await find_account_by_discordid(target_discord_id)

        if not target_user:
            await interaction.response.send_message(
                "대상 유저가 등록되어 있지 않습니다.",
                ephemeral=True
            )
            return

        # 완전 회복 적용
        healed = await HealingService.full_heal(target_user)

        target_name = target.display_name if target else interaction.user.display_name

        embed = discord.Embed(
            title="💚 완전 회복",
            description=f"**{target_name}**의 HP가 완전히 회복되었습니다!",
            color=discord.Color.green()
        )

        embed.add_field(
            name="회복량",
            value=f"+{healed} HP",
            inline=True
        )

        embed.add_field(
            name="현재 HP",
            value=f"{target_user.now_hp}/{target_user.hp}",
            inline=True
        )

        await interaction.response.send_message(embed=embed)

    @requires_account()
    @app_commands.command(
        name="스탯",
        description="스탯 포인트를 분배합니다"
    )
    @app_commands.guilds(GUILD_ID)
    async def stat_distribution(self, interaction: discord.Interaction):
        """스탯 분배"""
        # 전투 중 체크
        if is_in_combat(interaction.user.id):
            await interaction.response.send_message(
                "⚠️ 전투 중에는 스탯을 분배할 수 없습니다!",
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

        # 자연 회복 적용
        await HealingService.apply_natural_regen(user)

        if user.stat_points <= 0:
            await interaction.response.send_message(
                "📊 분배 가능한 스탯 포인트가 없습니다!\n"
                f"현재 레벨: Lv.{user.level}\n"
                "레벨업을 하면 스탯 포인트를 얻을 수 있습니다.",
                ephemeral=True
            )
            return

        view = StatDistributionView(
            discord_user=interaction.user,
            db_user=user
        )

        embed = view.create_embed()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        view.message = await interaction.original_response()


async def setup(bot):
    await bot.add_cog(DungeonCommand(bot))
