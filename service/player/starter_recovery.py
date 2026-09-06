"""Atomic registration and conservative, once-only repair of legacy starter accounts."""

from collections import Counter

from tortoise.transactions import in_transaction

from models import User, SkillEquip, UserStatEnum
from models.game_system import UserStarterRecovery
from models.user_owned_skill import UserOwnedSkill
from models.user_skill_deck import UserSkillDeck
from models.repos.users_repo import find_account_by_discordid
from service.collection_service import CollectionService


async def lock_registration(conn, discord_id: int) -> None:
    # Row locks cannot protect an account that does not exist yet. This scoped
    # transaction lock also serializes independent Bot processes on PostgreSQL.
    if conn.capabilities.dialect == "postgres":
        await conn.execute_query("SELECT pg_advisory_xact_lock($1)", [int(discord_id)])


async def ensure_account(discord_id: int, username: str) -> User:
    from service.player.user_service import UserService
    from service.session import _session_lock, is_in_session

    # Share the admission lock with create_session: no healing/deck mutation
    # can race with an in-memory run being admitted on this Bot.
    async with _session_lock:
        async with in_transaction() as conn:
            await lock_registration(conn, discord_id)
            existing = await User.filter(discord_id=discord_id).select_for_update().first()
            if existing is None:
                return await UserService._create_user(discord_id, username)
            user = await find_account_by_discordid(discord_id)
            if is_in_session(discord_id):
                return user
            receipt = await UserStarterRecovery.get_or_none(user=user)
            if receipt is None:
                old_deck = list(user.equipped_skill)
                replace = not any(old_deck) or old_deck == [1001] * 10
                deck = list(UserService.DEFAULT_SKILL_DECK) if replace else old_deck
                equipped = Counter(s for s in deck if s)
                minimums = Counter(UserService.DEFAULT_SKILL_DECK)
                grants = {}
                # Include the legacy custom deck to make ownership and loaded
                # slots agree without replacing the user's chosen composition.
                owned = {r.skill_id: r for r in await UserOwnedSkill.filter(user=user)}
                for skill_id in set(minimums) | set(equipped) | set(owned):
                    row = owned.get(skill_id)
                    before = row.quantity if row else 0
                    quantity = max(before, minimums[skill_id], equipped[skill_id])
                    if row is None:
                        row = await UserOwnedSkill.create(user=user, skill_id=skill_id,
                                                         quantity=quantity, equipped_count=equipped[skill_id])
                    else:
                        row.quantity, row.equipped_count = quantity, equipped[skill_id]
                        await row.save(update_fields=["quantity", "equipped_count"])
                    if quantity > before:
                        grants[str(skill_id)] = quantity - before
                    if skill_id in minimums or skill_id in equipped:
                        await CollectionService.register_skill(user, skill_id)
                if replace:
                    await UserSkillDeck.filter(user=user).delete()
                    await SkillEquip.filter(user=user).delete()
                    for slot, skill_id in enumerate(deck):
                        await UserSkillDeck.create(user=user, slot_index=slot, skill_id=skill_id)
                    user.equipped_skill = deck
                receipt = await UserStarterRecovery.create(
                    user=user, details={"grants": grants, "deck_replaced": replace, "previous_deck": old_deck})
            if not receipt.hp_recovered:
                if 1 <= user.level <= 10:
                    # Equipment is loaded by the same stat path used on entry.
                    from service.item.equipment_service import EquipmentService
                    await EquipmentService.apply_equipment_stats(user)
                    user.now_hp = user.get_stat()[UserStatEnum.HP]
                    await user.save(update_fields=["now_hp"])
                receipt.hp_recovered = True
                await receipt.save(update_fields=["hp_recovered"])
            return user
