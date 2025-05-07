from models import User

async def find_account_by_discordid(id) -> User:
    return await User.get_or_none(discord_id=id)

async def exists_account_by_discordid(id) -> bool:
    return await User.exists(discord_id=id)

async def exists_account_by_username(username) -> bool:
    return await User.exists(username=username)