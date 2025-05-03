from models import User

async def get_account_by_discord_id(id):
    return await User.get_or_none(discord_id = id)
