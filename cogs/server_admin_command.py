import discord
from discord.ext import commands
from discord import app_commands

from bot import GUILD_IDS
from models import Item, Skill_Model
from models.repos.static_cache import load_static_data
from models.repos.users_repo import find_account_by_discordid
from service.item.inventory_service import InventoryService
from service.skill.skill_ownership_service import SkillOwnershipService
from service.player.user_service import UserService
from service.temp_admin_service import (
    is_admin_or_temp, add_temp_admin, remove_temp_admin,
    get_all_temp_admins
)
from exceptions import ItemNotFoundError, InventoryFullError, SkillNotFoundError

admin = app_commands.Group(
    name="admin",
    description="관리자 전용 명령어",
    guild_ids=GUILD_IDS
)

class ServerAdminCammand(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="임시어드민",
        description="[관리자] 대상에게 임시 어드민 권한을 부여합니다 (봇 재시작 시 초기화)"
    )
    @app_commands.guilds(*GUILD_IDS)
    @app_commands.describe(target="임시 어드민으로 지정할 대상")
    @commands.has_permissions(administrator=True)
    async def grant_temp_admin(
        self,
        interaction: discord.Interaction,
        target: discord.Member
    ):
        if not add_temp_admin(target.id):
            await interaction.response.send_message(
                f"⚠️ **{target.display_name}**은(는) 이미 임시 어드민입니다.",
                ephemeral=True
            )
            return

        await interaction.response.send_message(
            f"✅ **{target.display_name}**을(를) 임시 어드민으로 지정했습니다.\n"
            f"💡 봇 재시작 시 권한이 초기화됩니다.",
            ephemeral=True
        )

    @app_commands.command(
        name="임시어드민해제",
        description="[관리자] 대상의 임시 어드민 권한을 해제합니다"
    )
    @app_commands.guilds(*GUILD_IDS)
    @app_commands.describe(target="임시 어드민 권한을 해제할 대상")
    @commands.has_permissions(administrator=True)
    async def revoke_temp_admin(
        self,
        interaction: discord.Interaction,
        target: discord.Member
    ):
        if not remove_temp_admin(target.id):
            await interaction.response.send_message(
                f"⚠️ **{target.display_name}**은(는) 임시 어드민이 아닙니다.",
                ephemeral=True
            )
            return

        await interaction.response.send_message(
            f"✅ **{target.display_name}**의 임시 어드민 권한을 해제했습니다.",
            ephemeral=True
        )

    @app_commands.command(
        name="임시어드민목록",
        description="[관리자] 현재 임시 어드민 목록을 확인합니다"
    )
    @app_commands.guilds(*GUILD_IDS)
    @commands.has_permissions(administrator=True)
    async def list_temp_admins_cmd(self, interaction: discord.Interaction):
        temp_admins = get_all_temp_admins()
        if not temp_admins:
            await interaction.response.send_message(
                "📋 현재 임시 어드민이 없습니다.",
                ephemeral=True
            )
            return

        admin_list = []
        for user_id in temp_admins:
            user = interaction.guild.get_member(user_id)
            if user:
                admin_list.append(f"• {user.display_name} (`{user_id}`)")
            else:
                admin_list.append(f"• Unknown User (`{user_id}`)")

        await interaction.response.send_message(
            f"📋 **임시 어드민 목록** ({len(temp_admins)}명)\n" + "\n".join(admin_list),
            ephemeral=True
        )

    @app_commands.command(
        name="clear",
        description="채널에서 최근 메시지 n개를 삭제합니다."
    )
    @app_commands.describe(amount="삭제할 메시지 수 (1~100)")
    @commands.has_permissions(administrator=True)
    async def clear(self, interaction: discord.Interaction, amount: int):
        if isinstance(interaction.channel, discord.DMChannel):
            deleted_count = 0
            async for msg in interaction.channel.history(limit=50):
                if msg.author == interaction.client.user:
                    try:
                        await msg.delete()
                        deleted_count += 1
                    except discord.NotFound:
                        # 이미 삭제된 메시지는 무시
                        pass
            await interaction.response.send_message(
                f"{deleted_count}개의 메시지를 삭제했습니다.",
                ephemeral=True
            )
            return
        if not interaction.channel.permissions_for(interaction.user).manage_messages:
            await interaction.response.send_message("메시지 관리 권한이 필요합니다.", ephemeral=True)
            return

        if not interaction.channel.permissions_for(interaction.guild.me).manage_messages:
            await interaction.response.send_message("봇에 메시지 관리 권한이 없습니다.", ephemeral=True)
            return

        if amount < 1 or amount > 100:
            await interaction.response.send_message("1부터 100 사이의 수를 입력해주세요.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        try:
            deleted = await interaction.channel.purge(limit=amount)
            await interaction.followup.send(f"{len(deleted)}개의 메시지를 삭제했습니다.", ephemeral=True)
        except discord.HTTPException as e:
            await interaction.followup.send(f"메시지 삭제 실패: {e}", ephemeral=True)

    @app_commands.command(
        name="데베재캐시",
        description="데이터베이스 변동시 다시 캐시합니다"
    )
    @commands.has_permissions(administrator=True)
    async def re_cache(self, interaction: discord.Interaction):
        await load_static_data()
        await interaction.response.send_message("데이터베이스 재캐시 완료")

    @app_commands.command(
        name="아이템지급",
        description="[관리자] 대상에게 아이템을 지급합니다"
    )
    @app_commands.guilds(*GUILD_IDS)
    @app_commands.describe(
        target="지급 대상 (미지정시 자신)",
        item_id="아이템 ID",
        quantity="수량",
        enhancement_level="강화 레벨 (기본 0)"
    )
    async def give_item(
        self,
        interaction: discord.Interaction,
        item_id: int,
        quantity: int = 1,
        enhancement_level: int = 0,
        target: discord.Member = None
    ):
        # 권한 체크
        if not is_admin_or_temp(interaction):
            await interaction.response.send_message(
                "❌ 이 명령어는 관리자만 사용할 수 있습니다.",
                ephemeral=True
            )
            return

        target_discord_id = target.id if target else interaction.user.id
        target_user = await find_account_by_discordid(target_discord_id)
        if not target_user:
            await interaction.response.send_message(
                "대상 유저가 등록되어 있지 않습니다.",
                ephemeral=True
            )
            return

        item = await Item.get_or_none(id=item_id)
        if not item:
            await interaction.response.send_message(
                "아이템을 찾을 수 없습니다.",
                ephemeral=True
            )
            return

        if quantity < 1:
            await interaction.response.send_message(
                "수량은 1 이상이어야 합니다.",
                ephemeral=True
            )
            return

        try:
            await InventoryService.add_item(
                target_user,
                item_id=item_id,
                quantity=quantity,
                enhancement_level=enhancement_level
            )
        except InventoryFullError:
            await interaction.response.send_message(
                "인벤토리가 가득 찼습니다.",
                ephemeral=True
            )
            return
        except ItemNotFoundError as e:
            await interaction.response.send_message(
                f"{e.message}",
                ephemeral=True
            )
            return

        target_name = target.display_name if target else interaction.user.display_name
        await interaction.response.send_message(
            f"✅ **{target_name}**에게 **{item.name}** x{quantity} 지급 완료",
            ephemeral=True
        )

    async def item_id_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str
    ) -> list[app_commands.Choice[int]]:
        query = current.strip()
        if not query:
            items = await Item.all().order_by("id").limit(25)
        elif query.isdigit():
            items = await Item.filter(id__icontains=query).limit(25)
        else:
            items = await Item.filter(name__icontains=query).limit(25)

        choices = []
        for item in items:
            # 설명 추가 (100자 제한)
            desc = item.description or ""
            if len(desc) > 40:
                desc = desc[:37] + "..."

            name = f"{item.id} - {item.name}"
            if desc:
                name += f" ({desc})"

            # Discord 제한: 100자
            if len(name) > 100:
                name = name[:97] + "..."

            choices.append(app_commands.Choice(name=name, value=item.id))

        return choices

    give_item.autocomplete("item_id")(item_id_autocomplete)

    @app_commands.command(
        name="스킬지급",
        description="[관리자] 대상에게 스킬을 지급합니다"
    )
    @app_commands.guilds(*GUILD_IDS)
    @app_commands.describe(
        target="지급 대상 (미지정시 자신)",
        skill_id="스킬 ID",
        quantity="수량"
    )
    async def give_skill(
        self,
        interaction: discord.Interaction,
        skill_id: int,
        quantity: int = 1,
        target: discord.Member = None
    ):
        # 권한 체크
        if not is_admin_or_temp(interaction):
            await interaction.response.send_message(
                "❌ 이 명령어는 관리자만 사용할 수 있습니다.",
                ephemeral=True
            )
            return

        target_discord_id = target.id if target else interaction.user.id
        target_user = await find_account_by_discordid(target_discord_id)
        if not target_user:
            await interaction.response.send_message(
                "대상 유저가 등록되어 있지 않습니다.",
                ephemeral=True
            )
            return

        skill = await Skill_Model.get_or_none(id=skill_id)
        if not skill:
            await interaction.response.send_message(
                "스킬을 찾을 수 없습니다.",
                ephemeral=True
            )
            return

        if quantity < 1:
            await interaction.response.send_message(
                "수량은 1 이상이어야 합니다.",
                ephemeral=True
            )
            return

        try:
            await SkillOwnershipService.add_skill(
                target_user,
                skill_id=skill_id,
                quantity=quantity
            )
        except SkillNotFoundError as e:
            await interaction.response.send_message(
                f"스킬을 찾을 수 없습니다: {e}",
                ephemeral=True
            )
            return

        target_name = target.display_name if target else interaction.user.display_name
        await interaction.response.send_message(
            f"✅ **{target_name}**에게 **{skill.name}** x{quantity} 지급 완료",
            ephemeral=True
        )

    async def skill_id_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str
    ) -> list[app_commands.Choice[int]]:
        query = current.strip()
        if not query:
            skills = await Skill_Model.all().order_by("id").limit(25)
        elif query.isdigit():
            # ID 검색
            skill_id_int = int(query)
            skills = await Skill_Model.filter(id__gte=skill_id_int).order_by("id").limit(25)
        else:
            # 이름 검색
            skills = await Skill_Model.filter(name__icontains=query).limit(25)

        choices = []
        for skill in skills:
            # 설명 추가 (100자 제한)
            desc = skill.description or ""
            if len(desc) > 35:
                desc = desc[:32] + "..."

            # 속성 추가
            attr = skill.attribute or "무속성"

            name = f"{skill.id} - {skill.name} [{attr}]"
            if desc:
                name += f" {desc}"

            # Discord 제한: 100자
            if len(name) > 100:
                name = name[:97] + "..."

            choices.append(app_commands.Choice(name=name, value=skill.id))

        return choices

    give_skill.autocomplete("skill_id")(skill_id_autocomplete)

    @app_commands.command(
        name="경험치지급",
        description="[관리자] 대상에게 경험치를 지급합니다"
    )
    @app_commands.guilds(*GUILD_IDS)
    @app_commands.describe(
        target="지급 대상 (미지정시 자신)",
        amount="경험치 양"
    )
    async def give_exp(
        self,
        interaction: discord.Interaction,
        amount: int,
        target: discord.Member = None
    ):
        # 권한 체크
        if not is_admin_or_temp(interaction):
            await interaction.response.send_message(
                "❌ 이 명령어는 관리자만 사용할 수 있습니다.",
                ephemeral=True
            )
            return

        target_discord_id = target.id if target else interaction.user.id
        target_user = await find_account_by_discordid(target_discord_id)
        if not target_user:
            await interaction.response.send_message(
                "대상 유저가 등록되어 있지 않습니다.",
                ephemeral=True
            )
            return

        if amount < 1:
            await interaction.response.send_message(
                "경험치는 1 이상이어야 합니다.",
                ephemeral=True
            )
            return

        # 경험치 추가 및 레벨업 처리
        result = await UserService.add_experience(target_user, amount)

        target_name = target.display_name if target else interaction.user.display_name

        if result["leveled_up"]:
            level_diff = result["new_level"] - result["old_level"]
            response = (
                f"✅ **{target_name}**에게 경험치 **+{amount}** 지급 완료\n"
                f"🎉 레벨업! **Lv.{result['old_level']}** → **Lv.{result['new_level']}** "
                f"(+{level_diff})\n"
                f"📊 스탯 포인트 **+{result['stat_points_gained']}**"
            )
        else:
            response = (
                f"✅ **{target_name}**에게 경험치 **+{amount}** 지급 완료\n"
                f"📈 현재 레벨: **Lv.{result['new_level']}** "
                f"(경험치: {result['current_experience']})"
            )

        await interaction.response.send_message(response, ephemeral=True)

    @app_commands.command(
        name="도감전체해금",
        description="[관리자] 대상의 도감을 전체 해금합니다"
    )
    @app_commands.guilds(*GUILD_IDS)
    @app_commands.describe(target="해금할 대상 (미지정시 자신)")
    async def unlock_all_collection(
        self,
        interaction: discord.Interaction,
        target: discord.Member = None
    ):
        # 권한 체크
        if not is_admin_or_temp(interaction):
            await interaction.response.send_message(
                "❌ 이 명령어는 관리자만 사용할 수 있습니다.",
                ephemeral=True
            )
            return

        target_discord_id = target.id if target else interaction.user.id
        target_user = await find_account_by_discordid(target_discord_id)
        if not target_user:
            await interaction.response.send_message(
                "대상 유저가 등록되어 있지 않습니다.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        # 모든 아이템, 스킬, 몬스터 등록
        from models.repos.static_cache import item_cache, skill_cache_by_id, monster_cache_by_id
        from service.collection_service import CollectionService

        item_count = 0
        skill_count = 0
        monster_count = 0

        # 아이템 등록
        for item_id in item_cache.keys():
            created = await CollectionService.register_item(target_user, item_id)
            if created:
                item_count += 1

        # 스킬 등록 (몬스터 스킬 제외, ID < 9000)
        for skill_id in skill_cache_by_id.keys():
            if skill_id < 9000:  # 몬스터 스킬 제외
                created = await CollectionService.register_skill(target_user, skill_id)
                if created:
                    skill_count += 1

        # 몬스터 등록
        for monster_id in monster_cache_by_id.keys():
            created = await CollectionService.register_monster(target_user, monster_id)
            if created:
                monster_count += 1

        target_name = target.display_name if target else interaction.user.display_name

        embed = discord.Embed(
            title="📚 도감 전체 해금 완료",
            description=f"**{target_name}**의 도감을 전체 해금했습니다!",
            color=discord.Color.gold()
        )

        embed.add_field(
            name="🎒 아이템",
            value=f"{item_count}개 신규 등록",
            inline=True
        )

        embed.add_field(
            name="⚔️ 스킬",
            value=f"{skill_count}개 신규 등록",
            inline=True
        )

        embed.add_field(
            name="👹 몬스터",
            value=f"{monster_count}개 신규 등록",
            inline=True
        )

        total_count = item_count + skill_count + monster_count
        embed.set_footer(text=f"총 {total_count}개 항목 신규 등록")

        await interaction.followup.send(embed=embed, ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(ServerAdminCammand(bot))