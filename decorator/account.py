from discord import Interaction, app_commands

from models.repos import find_account_by_discordid


def requires_registration():
    async def predicate(interaction: Interaction):
        user = await find_account_by_discordid(interaction.user.id)
        if user is None:
            await interaction.response.send_message(
                "❗ 회원가입이 필요합니다. `/register` 명령어로 먼저 회원가입해주세요.",
                ephemeral=True
            )
            return False
        return True

    return app_commands.check(predicate)