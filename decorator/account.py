from discord import Interaction, app_commands

from models import User
from models.repos import find_account_by_discordid


def requires_account():
    """
    계정이 필요한 명령어에 사용하는 데코레이터.
    계정이 없으면 자동으로 Discord ID로 가입시킵니다.
    """
    async def predicate(interaction: Interaction):
        user = await find_account_by_discordid(interaction.user.id)
        if user is None:
            # 자동 가입
            user = User(
                discord_id=interaction.user.id,
                username=interaction.user.display_name
            )
            await user.save()
        return True

    return app_commands.check(predicate)
