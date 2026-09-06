"""Atomic, idempotent box rewards with tier-scoped pity."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
import random
from typing import Iterable

from tortoise.transactions import in_transaction

from config import (
    BOX_CONFIGS, BOX_PITY_BY_ID, GRADE_DROP_WEIGHTS, INVENTORY,
    SOFT_PITY_CAP, SOFT_PITY_INCREMENT, BoxRewardType,
)
from exceptions import InventoryFullError, ItemNotFoundError, InsufficientItemError
from models import (
    EquipmentItem, EquipmentProvenance, Grade, Item, Skill_Model, User,
    UserCraftingWallet,
)
from models.game_system import BoxOpenReceipt, UserBoxPity
from models.user_collection import CollectionType, UserCollection
from models.user_inventory import UserInventory
from models.user_owned_skill import UserOwnedSkill
from resources.item_emoji import ItemType
from service.item.grade_service import GradeService


GRADE_NAMES = {1: "D", 2: "C", 3: "B", 4: "A", 5: "S", 6: "SS", 7: "SSS", 8: "신화"}
GRADE_CONTEXT_BY_BOX = {
    5940: "box_low", 5941: "box_mid", 5942: "box_high",
    5943: "box_best", 5945: "box_high", 5946: "box_best", 5947: "box_high",
}


@dataclass(frozen=True)
class RewardAtom:
    reward_type: BoxRewardType
    grade: int
    weight: float


@dataclass
class BoxRewardOutcome:
    reward_type: str
    grade: int
    grade_name: str
    name: str
    quantity: int = 1
    gold: int = 0
    item_id: int | None = None
    skill_id: int | None = None
    special_effects: list | None = None
    new_collection: bool = False
    pity_group: str | None = None
    pity_before: int = 0
    pity_after: int = 0
    base_target_chance: float = 0.0
    adjusted_target_chance: float = 0.0
    hard_pity_triggered: bool = False

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict) -> "BoxRewardOutcome":
        return cls(**value)


@dataclass
class BoxOpenBatch:
    interaction_id: str
    box_id: int
    box_name: str
    outcomes: list[BoxRewardOutcome]
    replayed: bool = False


def _grade_weights(box_id: int) -> dict[int, float]:
    context = GRADE_CONTEXT_BY_BOX.get(box_id, "box_low")
    return {int(grade): float(weight) for grade, weight in GRADE_DROP_WEIGHTS[context].items()}


def build_reward_atoms(box_id: int) -> list[RewardAtom]:
    config = BOX_CONFIGS[box_id]
    atoms: list[RewardAtom] = []
    grades = _grade_weights(box_id)
    grade_total = sum(grades.values())
    for reward in config.rewards:
        if reward.reward_type == BoxRewardType.GOLD:
            atoms.append(RewardAtom(reward.reward_type, 0, reward.probability))
            continue
        if reward.guaranteed_grade:
            grade = next((key for key, name in GRADE_NAMES.items() if name == reward.guaranteed_grade), 1)
            atoms.append(RewardAtom(reward.reward_type, grade, reward.probability))
            continue
        for grade, weight in grades.items():
            atoms.append(RewardAtom(reward.reward_type, grade, reward.probability * weight / grade_total))
    return atoms


def pity_chances(box_id: int, failure_count: int) -> tuple[float, float, bool]:
    rule = BOX_PITY_BY_ID.get(box_id)
    if not rule:
        return 0.0, 0.0, False
    atoms = build_reward_atoms(box_id)
    total = sum(atom.weight for atom in atoms)
    base = sum(atom.weight for atom in atoms if atom.grade >= rule.target_grade) / total
    hard = failure_count >= rule.hard_pity - 1
    if hard:
        return base, 1.0, True
    bonus_steps = max(0, failure_count - rule.soft_start + 1)
    adjusted = min(SOFT_PITY_CAP, base + bonus_steps * SOFT_PITY_INCREMENT)
    return base, adjusted, False


def roll_atom(box_id: int, failure_count: int, rng: random.Random) -> tuple[RewardAtom, float, float, bool]:
    atoms = build_reward_atoms(box_id)
    rule = BOX_PITY_BY_ID.get(box_id)
    if not rule:
        picked = rng.choices(atoms, weights=[atom.weight for atom in atoms], k=1)[0]
        return picked, 0.0, 0.0, False

    base, adjusted, hard = pity_chances(box_id, failure_count)
    high = [atom for atom in atoms if atom.grade >= rule.target_grade]
    low = [atom for atom in atoms if atom.grade < rule.target_grade]
    pool = high if rng.random() < adjusted else low
    picked = rng.choices(pool, weights=[atom.weight for atom in pool], k=1)[0]
    return picked, base, adjusted, hard


def _gold_amount(level: int, multiplier: float, rng: random.Random) -> int:
    from config import DROP
    base = DROP.CHEST_BASE_GOLD * multiplier * (1 + level / 10)
    return int(base * rng.uniform(DROP.CHEST_GOLD_VARIANCE_MIN, DROP.CHEST_GOLD_VARIANCE_MAX))


async def _register_collection(conn, user_id: int, collection_type: CollectionType, target_id: int) -> bool:
    existing = await UserCollection.filter(
        user_id=user_id, collection_type=collection_type, target_id=target_id
    ).using_db(conn).exists()
    if existing:
        return False
    await UserCollection.create(
        user_id=user_id, collection_type=collection_type, target_id=target_id,
        using_db=conn,
    )
    return True


async def _grant_atom(conn, locked_user: User, atom: RewardAtom, box_id: int, dungeon_level: int | None, rng: random.Random) -> BoxRewardOutcome:
    config = BOX_CONFIGS[box_id]
    grade_name = GRADE_NAMES.get(atom.grade, "")
    if atom.reward_type == BoxRewardType.GOLD:
        gold = _gold_amount(locked_user.level, config.gold_multiplier, rng)
        locked_user.gold += gold
        await locked_user.save(using_db=conn, update_fields=["gold"])
        return BoxRewardOutcome("gold", 0, "", f"골드 +{gold:,}", gold=gold)

    if atom.reward_type == BoxRewardType.EQUIPMENT:
        query = EquipmentItem.all().using_db(conn)
        if dungeon_level:
            from models.repos.static_cache import get_previous_dungeon_level
            query = query.filter(
                require_level__gte=get_previous_dungeon_level(dungeon_level),
                require_level__lte=dungeon_level,
            )
        candidate_ids = list(await query.values_list("item_id", flat=True))
        if not candidate_ids:
            raise ItemNotFoundError(-1)
        wallet = await UserCraftingWallet.filter(user_id=locked_user.id).using_db(conn).first()
        storage = wallet.equipment_storage if wallet else 300
        equipment_ids = await EquipmentItem.all().using_db(conn).values_list("item_id", flat=True)
        if await UserInventory.filter(user_id=locked_user.id, item_id__in=equipment_ids).using_db(conn).count() >= storage:
            raise InventoryFullError(storage)
        item_id = rng.choice(candidate_ids)
        item = await Item.get(id=item_id, using_db=conn)
        special_effects = GradeService.roll_special_effects(atom.grade)
        created = await UserInventory.create(
            user_id=locked_user.id, item_id=item_id, quantity=1,
            instance_grade=atom.grade, special_effects=special_effects,
            using_db=conn,
        )
        from service.item.affix_service import ensure_instance_affixes
        definition = await EquipmentItem.filter(item_id=item_id).using_db(conn).first()
        if definition:
            await ensure_instance_affixes(created, definition.equip_pos, rng, using_db=conn)
            await EquipmentProvenance.create(
                inventory_item=created, source_type="box", source_key=str(box_id),
                original_owner_id=locked_user.id, using_db=conn,
            )
        is_new = await _register_collection(conn, locked_user.id, CollectionType.ITEM, item_id)
        return BoxRewardOutcome(
            "equipment", atom.grade, grade_name, item.name or f"장비 #{item_id}",
            item_id=item_id, special_effects=special_effects, new_collection=is_new,
        )

    grade_row = await Grade.get_or_none(name=grade_name, using_db=conn)
    if not grade_row and grade_name == "신화":
        grade_row = await Grade.get_or_none(name="Mythic", using_db=conn)
    grade_id = grade_row.id if grade_row else atom.grade
    skill_ids = list(await Skill_Model.filter(
        grade=grade_id, id__lt=9000, player_obtainable=True
    ).using_db(conn).values_list("id", flat=True))
    if not skill_ids:
        raise ItemNotFoundError(-1)
    skill_id = rng.choice(skill_ids)
    skill = await Skill_Model.get(id=skill_id, using_db=conn)
    owned = await UserOwnedSkill.filter(
        user_id=locked_user.id, skill_id=skill_id
    ).select_for_update().using_db(conn).first()
    if owned:
        owned.quantity += 1
        await owned.save(using_db=conn, update_fields=["quantity", "updated_at"])
    else:
        await UserOwnedSkill.create(
            user_id=locked_user.id, skill_id=skill_id, quantity=1, equipped_count=0,
            using_db=conn,
        )
    is_new = await _register_collection(conn, locked_user.id, CollectionType.SKILL, skill_id)
    return BoxRewardOutcome(
        "skill", atom.grade, grade_name, skill.name, skill_id=skill_id,
        new_collection=is_new,
    )


class BoxOpenService:
    @staticmethod
    async def get_pity_progress(user: User) -> dict[str, int]:
        rows = await UserBoxPity.filter(user=user)
        return {row.pity_group: row.failure_count for row in rows}

    @staticmethod
    async def open_boxes(
        user: User,
        inventory_id: int,
        quantity: int,
        interaction_id: str | int,
        *,
        rng: random.Random | None = None,
    ) -> BoxOpenBatch:
        rng = rng or random.SystemRandom()
        receipt_key = str(interaction_id)
        existing = await BoxOpenReceipt.get_or_none(interaction_id=receipt_key)
        if existing:
            item = await Item.get(id=existing.box_id)
            return BoxOpenBatch(receipt_key, existing.box_id, item.name or "상자", [
                BoxRewardOutcome.from_dict(value) for value in existing.outcomes
            ], replayed=True)

        async with in_transaction() as conn:
            locked_user = await User.filter(id=user.id).select_for_update().using_db(conn).first()
            if not locked_user:
                raise ItemNotFoundError(user.id)
            existing = await BoxOpenReceipt.get_or_none(interaction_id=receipt_key, using_db=conn)
            if existing:
                item = await Item.get(id=existing.box_id, using_db=conn)
                return BoxOpenBatch(receipt_key, existing.box_id, item.name or "상자", [
                    BoxRewardOutcome.from_dict(value) for value in existing.outcomes
                ], replayed=True)

            inventory = await UserInventory.filter(
                id=inventory_id, user_id=user.id
            ).select_for_update().using_db(conn).first()
            if not inventory:
                raise ItemNotFoundError(inventory_id)
            box_id = inventory.item_id
            config = BOX_CONFIGS.get(box_id)
            if not config:
                raise ItemNotFoundError(box_id)
            quantity = max(1, int(quantity))
            if inventory.quantity < quantity:
                box_item = await Item.get(id=box_id, using_db=conn)
                raise InsufficientItemError(box_item.name or "상자", quantity, inventory.quantity)

            rule = BOX_PITY_BY_ID.get(box_id)
            pity = None
            if rule:
                pity = await UserBoxPity.filter(
                    user_id=user.id, pity_group=rule.key
                ).select_for_update().using_db(conn).first()
                if not pity:
                    pity = await UserBoxPity.create(
                        user_id=user.id, pity_group=rule.key, failure_count=0,
                        using_db=conn,
                    )

            outcomes = []
            for _ in range(quantity):
                pity_before = pity.failure_count if pity else 0
                atom, base, adjusted, hard = roll_atom(box_id, pity_before, rng)
                outcome = await _grant_atom(
                    conn, locked_user, atom, box_id,
                    inventory.instance_grade if inventory.instance_grade > 0 else None,
                    rng,
                )
                if pity and rule:
                    success = atom.grade >= rule.target_grade
                    pity.failure_count = 0 if success else pity.failure_count + 1
                    outcome.pity_group = rule.key
                    outcome.pity_before = pity_before
                    outcome.pity_after = pity.failure_count
                    outcome.base_target_chance = base
                    outcome.adjusted_target_chance = adjusted
                    outcome.hard_pity_triggered = hard and success
                outcomes.append(outcome)

            if pity:
                await pity.save(using_db=conn, update_fields=["failure_count", "last_opened_at"])
            inventory.quantity -= quantity
            if inventory.quantity <= 0:
                await inventory.delete(using_db=conn)
            else:
                await inventory.save(using_db=conn, update_fields=["quantity"])
            await BoxOpenReceipt.create(
                interaction_id=receipt_key, user_id=user.id, box_id=box_id,
                quantity=quantity, outcomes=[outcome.to_dict() for outcome in outcomes],
                using_db=conn,
            )
            box_item = await Item.get(id=box_id, using_db=conn)

        user.gold = locked_user.gold
        batch = BoxOpenBatch(receipt_key, box_id, box_item.name or "상자", outcomes)
        from service.telemetry import record_game_event
        await record_game_event(
            "box_opened", user=user, content_type="rewards",
            run_nonce=receipt_key,
            metrics={
                "box_id": box_id, "quantity": quantity,
                "grades": [outcome.grade for outcome in outcomes],
                "types": [outcome.reward_type for outcome in outcomes],
                "hard_pity": any(outcome.hard_pity_triggered for outcome in outcomes),
            },
        )
        return batch

    @staticmethod
    async def cleanup_receipts(days: int = 30) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        return await BoxOpenReceipt.filter(created_at__lt=cutoff).delete()
