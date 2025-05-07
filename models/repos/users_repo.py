from models import User

async def find_account_by_discordid(id) -> User:
    return await User.get_or_none(discord_id=id)

async def exists_account_by_username(username) -> bool:
    return await User.get_or_none(username=username) is not None