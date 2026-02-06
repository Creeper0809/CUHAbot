import discord
from discord.ext import commands
from discord import app_commands

from bot import GUILD_ID
from models import Item
from models.repos.static_cache import load_static_data
from models.repos.users_repo import find_account_by_discordid
from service.inventory_service import InventoryService
from exceptions import ItemNotFoundError, InventoryFullError

admin = app_commands.Group(
    name="admin",
    description="관리자 전용 명령어",
    guild_ids=[GUILD_ID]
)

class ServerAdminCammand(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="clear",
        description="채널에서 최근 메시지 n개를 삭제합니다."
    )
    @app_commands.describe(amount="삭제할 메시지 수 (1~100)")
    @commands.has_permissions(administrator=True)
    async def clear(self, interaction: discord.Interaction, amount: int):
        if isinstance(interaction.channel, discord.DMChannel):
            async for msg in interaction.channel.history(limit=50):
                if msg.author == interaction.client.user:
                    await msg.delete()
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
    @app_commands.guilds(GUILD_ID)
    @app_commands.describe(
        target="지급 대상 (미지정시 자신)",
        item_id="아이템 ID",
        quantity="수량",
        enhancement_level="강화 레벨 (기본 0)"
    )
    @commands.has_permissions(administrator=True)
    async def give_item(
        self,
        interaction: discord.Interaction,
        item_id: int,
        quantity: int = 1,
        enhancement_level: int = 0,
        target: discord.Member = None
    ):
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

        return [
            app_commands.Choice(name=f"{item.id} - {item.name}", value=item.id)
            for item in items
        ]

    give_item.autocomplete("item_id")(item_id_autocomplete)

async def setup(bot: commands.Bot):
    await bot.add_cog(ServerAdminCammand(bot))