from models import User, SkillEquip


async def find_account_by_discordid(id) -> User:
    user = await User.get_or_none(discord_id=id)
    equipped = await SkillEquip.filter(user=user).prefetch_related('skill')

    for eq in equipped:
        user.equipped_skill[eq.pos] = eq.skill.id
    return user

async def exists_account_by_discordid(id) -> bool:
    return await User.exists(discord_id=id)

async def exists_account_by_username(username) -> bool:
    return await User.exists(username=username)

