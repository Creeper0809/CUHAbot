from discord import Interaction, app_commands

from service.player.starter_recovery import ensure_account


def requires_account():
    """
    계정이 필요한 명령어에 사용하는 데코레이터.
    계정이 없으면 자동으로 Discord ID로 가입시킵니다.
    """
    async def predicate(interaction: Interaction):
        await ensure_account(interaction.user.id, interaction.user.display_name)
        return True

    return app_commands.check(predicate)
