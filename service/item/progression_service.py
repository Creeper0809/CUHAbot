"""Transactional farming, salvage, reforge, crafting, and inheritance services."""
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from datetime import datetime, timezone

from tortoise import transactions

from config import BALANCE_V2, GRADE_TABLE
from config.itemization_v4 import (
    EQUIPMENT_STORAGE_MAX, EQUIPMENT_STORAGE_STEP, PRESERVED_AFFIX_MULTIPLIER,
    REFORGE_ESSENCE, SALVAGE_ESSENCE,
    SOURCE_PROGRESS_THRESHOLDS, TARGET_CRAFT_ESSENCE, TARGET_CRAFT_GRADE,
)
from models import (
    EquipmentActionReceipt, EquipmentItem, EquipmentProvenance, UserBuildPresetItem,
    UserCraftingWallet, UserEquipment, UserEquipmentAffix, UserFarmProgress,
    UserInventory,
)
from resources.item_emoji import ItemType
from service.item.affix_service import (
    AFFIX_BY_ID, EQUIP_POS_SLOT_KEYS, ensure_instance_affixes, roll_replacement_affix,
)


class EquipmentProgressionError(ValueError):
    pass


@dataclass(frozen=True)
class FarmProgressResult:
    source_key: str
    progress: int
    threshold: int
    seals_awarded: int
    featured_bonus: int


async def _wallet(user, conn=None) -> UserCraftingWallet:
    query = UserCraftingWallet.filter(user=user)
    if conn:
        query = query.using_db(conn).select_for_update()
    wallet = await query.first()
    if wallet:
        return wallet
    return await UserCraftingWallet.create(user=user, using_db=conn)


async def complete_source(
    user, source_type: str, source_key: str, *, featured: bool = False,
) -> FarmProgressResult:
    threshold = SOURCE_PROGRESS_THRESHOLDS.get(source_type)
    if not threshold:
        raise EquipmentProgressionError(f"unsupported source type: {source_type}")
    gain = 1 + int(featured)
    async with transactions.in_transaction() as conn:
        row = await UserFarmProgress.filter(
            user=user, source_type=source_type, source_key=source_key,
        ).using_db(conn).select_for_update().first()
        if not row:
            row = await UserFarmProgress.create(
                user=user, source_type=source_type, source_key=source_key, using_db=conn,
            )
        row.progress += gain
        awarded = row.progress // threshold
        row.progress %= threshold
        row.seals_earned += awarded
        await row.save(using_db=conn)
        if awarded:
            wallet = await _wallet(user, conn)
            seals = dict(wallet.source_seals or {})
            seals[source_key] = int(seals.get(source_key, 0)) + awarded
            wallet.source_seals = seals
            await wallet.save(using_db=conn, update_fields=["source_seals"])
    return FarmProgressResult(source_key, row.progress, threshold, awarded, int(featured))


async def _existing_receipt(interaction_id: str):
    return await EquipmentActionReceipt.get_or_none(interaction_id=interaction_id)


async def salvage_equipment(user, inventory_id: int, interaction_id: str, *, confirmed: bool = False) -> dict:
    receipt = await _existing_receipt(interaction_id)
    if receipt:
        return dict(receipt.result)
    async with transactions.in_transaction() as conn:
        item = await UserInventory.filter(id=inventory_id, user=user).using_db(conn).select_for_update().prefetch_related("item").first()
        if not item or item.item.type != ItemType.EQUIP:
            raise EquipmentProgressionError("분해할 장비를 찾을 수 없습니다.")
        if item.is_locked or await UserEquipment.filter(inventory_item=item).using_db(conn).exists():
            raise EquipmentProgressionError("잠금 또는 장착 중인 장비는 분해할 수 없습니다.")
        if await UserBuildPresetItem.filter(inventory_item=item).using_db(conn).exists():
            raise EquipmentProgressionError("빌드 프리셋에서 사용하는 장비는 분해할 수 없습니다.")
        same_base = await UserInventory.filter(user=user, item_id=item.item_id).using_db(conn).count()
        protected = item.instance_grade >= 7 or item.enhancement_level >= 10 or same_base <= 1
        if protected and not confirmed:
            raise EquipmentProgressionError("첫 보유·SSS 이상·+10 이상 장비는 확인 후 분해해야 합니다.")
        essence = SALVAGE_ESSENCE.get(item.instance_grade, 0)
        wallet = await _wallet(user, conn)
        wallet.equipment_essence += essence
        await wallet.save(using_db=conn, update_fields=["equipment_essence"])
        result = {"item_id": item.item_id, "item_name": item.item.name, "essence": essence}
        await item.delete(using_db=conn)
        await EquipmentActionReceipt.create(
            interaction_id=interaction_id, user=user, action="salvage",
            inventory_item_id=inventory_id, result=result, using_db=conn,
        )
    return result


async def salvage_many(user, inventory_ids: list[int], interaction_id: str, *, confirmed: bool = False) -> dict:
    receipt = await _existing_receipt(interaction_id)
    if receipt:
        return dict(receipt.result)
    ids = list(dict.fromkeys(int(value) for value in inventory_ids))
    if not ids or len(ids) > 30:
        raise EquipmentProgressionError("일괄 분해는 1~30개 장비를 지정해야 합니다.")
    async with transactions.in_transaction() as conn:
        items = list(await UserInventory.filter(id__in=ids, user=user).using_db(conn).select_for_update().prefetch_related("item"))
        if len(items) != len(ids) or any(item.item.type != ItemType.EQUIP for item in items):
            raise EquipmentProgressionError("분해 목록에 없거나 장비가 아닌 항목이 있습니다.")
        if await UserEquipment.filter(inventory_item_id__in=ids).using_db(conn).exists():
            raise EquipmentProgressionError("장착 중인 장비가 포함되어 있습니다.")
        if await UserBuildPresetItem.filter(inventory_item_id__in=ids).using_db(conn).exists():
            raise EquipmentProgressionError("빌드 프리셋 장비가 포함되어 있습니다.")
        if any(item.is_locked for item in items):
            raise EquipmentProgressionError("잠금 또는 경매 중인 장비가 포함되어 있습니다.")
        for item in items:
            same_base = await UserInventory.filter(user=user, item_id=item.item_id).using_db(conn).count()
            if (item.instance_grade >= 7 or item.enhancement_level >= 10 or same_base <= 1) and not confirmed:
                raise EquipmentProgressionError("첫 보유·SSS 이상·+10 이상 장비가 포함되어 확인이 필요합니다.")
        essence = sum(SALVAGE_ESSENCE.get(item.instance_grade, 0) for item in items)
        wallet = await _wallet(user, conn)
        wallet.equipment_essence += essence
        await wallet.save(using_db=conn, update_fields=["equipment_essence"])
        names = [item.item.name for item in items]
        await UserInventory.filter(id__in=ids).using_db(conn).delete()
        result = {"inventory_ids": ids, "count": len(ids), "item_names": names, "essence": essence}
        await EquipmentActionReceipt.create(
            interaction_id=interaction_id, user=user, action="salvage_many",
            result=result, using_db=conn,
        )
    return result


def reforge_gold_cost(level: int, grade: int, preserved_count: int) -> int:
    info = GRADE_TABLE.get(grade)
    grade_name = "MYTHIC" if info and info.name == "신화" else (info.name if info else "A")
    multiplier = PRESERVED_AFFIX_MULTIPLIER[min(2, max(0, preserved_count))]
    return max(10, round(BALANCE_V2.dungeon_gold(level) * 0.15 * math.sqrt(BALANCE_V2.grade_multipliers[grade_name]) * multiplier / 10) * 10)


async def get_reforge_quote(user, inventory_id: int, position: int) -> dict:
    from config.itemization_v4 import AFFIX_DEFINITIONS, tier_range
    item = await UserInventory.get_or_none(id=inventory_id, user=user).prefetch_related("item")
    if not item or item.item.type != ItemType.EQUIP or item.is_locked:
        raise EquipmentProgressionError("재련할 수 없는 장비입니다.")
    equipment = await EquipmentItem.get_or_none(item_id=item.item_id)
    if not equipment:
        raise EquipmentProgressionError("장비 정의가 없습니다.")
    affixes = list(await UserEquipmentAffix.filter(inventory_item=item).order_by("position").prefetch_related("affix_definition"))
    target = next((row for row in affixes if row.position == position), None)
    if not target:
        raise EquipmentProgressionError("재련할 옵션 슬롯이 없습니다.")
    preserved = len(affixes) - 1
    excluded = {row.affix_definition.effect_group for row in affixes if row.position != position}
    slot_key = EQUIP_POS_SLOT_KEYS[equipment.equip_pos]
    candidates = [row for row in AFFIX_DEFINITIONS if slot_key in row.allowed_slots and row.effect_group not in excluded]
    tiers = tier_range(item.instance_grade)
    return {
        "current": {"id": target.affix_definition_id, "tier": target.tier, "value": target.value},
        "tier_range": tiers, "candidate_count": len(candidates),
        "essence_cost": REFORGE_ESSENCE[item.instance_grade] * PRESERVED_AFFIX_MULTIPLIER[min(2, preserved)],
        "gold_cost": reforge_gold_cost(equipment.require_level or 1, item.instance_grade, preserved),
    }


async def reforge_affix(user, inventory_id: int, position: int, interaction_id: str, *, rng=None) -> dict:
    receipt = await _existing_receipt(interaction_id)
    if receipt:
        return dict(receipt.result)
    rng = rng or random.Random()
    async with transactions.in_transaction() as conn:
        item = await UserInventory.filter(id=inventory_id, user=user).using_db(conn).select_for_update().prefetch_related("item").first()
        if not item or item.item.type != ItemType.EQUIP or item.is_locked:
            raise EquipmentProgressionError("재련할 수 없는 장비입니다.")
        equipment = await EquipmentItem.filter(item_id=item.item_id).using_db(conn).first()
        if not equipment:
            raise EquipmentProgressionError("장비 정의가 없습니다.")
        await ensure_instance_affixes(item, equipment.equip_pos, rng, using_db=conn)
        affixes = list(await UserEquipmentAffix.filter(inventory_item=item).using_db(conn).select_for_update().prefetch_related("affix_definition"))
        target = next((row for row in affixes if row.position == position), None)
        if not target:
            raise EquipmentProgressionError("재련할 옵션 슬롯이 없습니다.")
        preserved = len(affixes) - 1
        multiplier = PRESERVED_AFFIX_MULTIPLIER[min(2, preserved)]
        essence_cost = REFORGE_ESSENCE[item.instance_grade] * multiplier
        gold_cost = reforge_gold_cost(equipment.require_level or 1, item.instance_grade, preserved)
        wallet = await _wallet(user, conn)
        locked_user = await type(user).filter(id=user.id).using_db(conn).select_for_update().first()
        if wallet.equipment_essence < essence_cost or locked_user.gold < gold_cost:
            raise EquipmentProgressionError(f"재련 비용이 부족합니다. 정수 {essence_cost}, 골드 {gold_cost:,}G 필요")
        excluded = {row.affix_definition.effect_group for row in affixes if row.position != position}
        replacement = roll_replacement_affix(
            item.instance_grade, EQUIP_POS_SLOT_KEYS[equipment.equip_pos], excluded, rng,
        )
        before = {"id": target.affix_definition_id, "tier": target.tier, "value": target.value}
        target.affix_definition_id = replacement.affix_id
        target.tier = replacement.tier
        target.value = replacement.value
        target.quality_percentile = replacement.quality_percentile
        await target.save(using_db=conn)
        wallet.equipment_essence -= essence_cost
        locked_user.gold -= gold_cost
        await wallet.save(using_db=conn, update_fields=["equipment_essence"])
        await locked_user.save(using_db=conn, update_fields=["gold"])
        provenance = await EquipmentProvenance.get_or_none(inventory_item=item).using_db(conn)
        if provenance:
            provenance.reforge_count += 1
            await provenance.save(using_db=conn, update_fields=["reforge_count"])
        result = {
            "item_id": item.item_id, "before": before,
            "after": {"id": replacement.affix_id, "tier": replacement.tier, "value": replacement.value, "quality": replacement.quality_percentile},
            "essence_cost": essence_cost, "gold_cost": gold_cost,
        }
        await EquipmentActionReceipt.create(
            interaction_id=interaction_id, user=user, action="reforge",
            inventory_item_id=inventory_id, result=result, using_db=conn,
        )
    return result


async def craft_target(user, source_key: str, item_id: int, interaction_id: str) -> dict:
    receipt = await _existing_receipt(interaction_id)
    if receipt:
        return dict(receipt.result)
    equipment = await EquipmentItem.get_or_none(item_id=item_id).prefetch_related("item")
    if not equipment or equipment.acquisition_source != source_key:
        raise EquipmentProgressionError("해당 지역에서 제작할 수 없는 장비입니다.")
    async with transactions.in_transaction() as conn:
        wallet = await _wallet(user, conn)
        seals = dict(wallet.source_seals or {})
        if int(seals.get(source_key, 0)) < 1 or wallet.equipment_essence < TARGET_CRAFT_ESSENCE:
            raise EquipmentProgressionError(f"완성 인장 1개와 장비 정수 {TARGET_CRAFT_ESSENCE}개가 필요합니다.")
        seals[source_key] -= 1
        wallet.source_seals = seals
        wallet.equipment_essence -= TARGET_CRAFT_ESSENCE
        await wallet.save(using_db=conn, update_fields=["source_seals", "equipment_essence"])
        from models import Item
        item = await Item.get(id=item_id, using_db=conn)
        created = await UserInventory.create(
            user=user, item=item, quantity=1, instance_grade=TARGET_CRAFT_GRADE,
            special_effects=[], using_db=conn,
        )
        await ensure_instance_affixes(created, equipment.equip_pos, using_db=conn)
        await EquipmentProvenance.create(
            inventory_item=created, source_type="craft", source_key=source_key,
            original_owner_id=user.id, crafted=True, using_db=conn,
        )
        result = {"inventory_id": created.id, "item_id": item_id, "grade": TARGET_CRAFT_GRADE, "source_key": source_key}
        await EquipmentActionReceipt.create(
            interaction_id=interaction_id, user=user, action="craft",
            inventory_item_id=created.id, result=result, using_db=conn,
        )
    return result


async def recover_destroyed_item(user, target_id: int, interaction_id: str) -> dict:
    """Consume one same-base broken core and restore a replacement item to +12."""
    receipt = await _existing_receipt(interaction_id)
    if receipt:
        return dict(receipt.result)
    async with transactions.in_transaction() as conn:
        target = await UserInventory.filter(id=target_id, user=user).using_db(conn).select_for_update().prefetch_related("item").first()
        if not target or target.item.type != ItemType.EQUIP:
            raise EquipmentProgressionError("복구할 장비를 찾을 수 없습니다.")
        if target.is_locked or await UserEquipment.filter(inventory_item=target).using_db(conn).exists():
            raise EquipmentProgressionError("잠금 또는 장착 중인 장비는 복구할 수 없습니다.")
        if target.enhancement_level > 12:
            raise EquipmentProgressionError("이미 +13 이상인 장비에는 파손된 핵을 사용할 수 없습니다.")
        wallet = await _wallet(user, conn)
        cores = dict(wallet.recovery_cores or {})
        key = str(target.item_id)
        if int(cores.get(key, 0)) <= 0:
            raise EquipmentProgressionError("같은 베이스의 파손된 핵이 없습니다.")
        cores[key] -= 1
        if cores[key] <= 0:
            cores.pop(key, None)
        wallet.recovery_cores = cores
        target.enhancement_level = 12
        await wallet.save(using_db=conn, update_fields=["recovery_cores"])
        await target.save(using_db=conn, update_fields=["enhancement_level"])
        result = {"target_id": target_id, "item_id": target.item_id, "item_name": target.item.name, "enhancement": 12}
        await EquipmentActionReceipt.create(
            interaction_id=interaction_id, user=user, action="recover",
            inventory_item_id=target_id, result=result, using_db=conn,
        )
    return result


async def expand_equipment_storage(user, interaction_id: str) -> dict:
    receipt = await _existing_receipt(interaction_id)
    if receipt:
        return dict(receipt.result)
    async with transactions.in_transaction() as conn:
        wallet = await _wallet(user, conn)
        if wallet.equipment_storage >= EQUIPMENT_STORAGE_MAX:
            raise EquipmentProgressionError("장비 창고가 이미 최대 600칸입니다.")
        steps_owned = max(0, (wallet.equipment_storage - 300) // EQUIPMENT_STORAGE_STEP)
        gold_cost = BALANCE_V2.dungeon_gold(user.level) * (5 + steps_owned * 2)
        locked_user = await type(user).filter(id=user.id).using_db(conn).select_for_update().first()
        if locked_user.gold < gold_cost:
            raise EquipmentProgressionError(f"창고 확장에 {gold_cost:,}G가 필요합니다.")
        locked_user.gold -= gold_cost
        wallet.equipment_storage = min(EQUIPMENT_STORAGE_MAX, wallet.equipment_storage + EQUIPMENT_STORAGE_STEP)
        await locked_user.save(using_db=conn, update_fields=["gold"])
        await wallet.save(using_db=conn, update_fields=["equipment_storage"])
        result = {"capacity": wallet.equipment_storage, "gold_cost": gold_cost}
        await EquipmentActionReceipt.create(
            interaction_id=interaction_id, user=user, action="storage_expand",
            result=result, using_db=conn,
        )
    user.gold -= result["gold_cost"]
    return result


async def inherit_enhancement(
    user, donor_id: int, target_id: int, interaction_id: str, *, use_catalyst: bool = False,
) -> dict:
    receipt = await _existing_receipt(interaction_id)
    if receipt:
        return dict(receipt.result)
    if donor_id == target_id:
        raise EquipmentProgressionError("같은 장비로 계승할 수 없습니다.")
    async with transactions.in_transaction() as conn:
        rows = list(await UserInventory.filter(id__in=[donor_id, target_id], user=user).using_db(conn).select_for_update().prefetch_related("item"))
        by_id = {row.id: row for row in rows}
        donor, target = by_id.get(donor_id), by_id.get(target_id)
        if not donor or not target or donor.is_locked or target.is_locked:
            raise EquipmentProgressionError("계승 장비를 찾을 수 없거나 잠겨 있습니다.")
        if await UserEquipment.filter(inventory_item_id__in=[donor_id, target_id]).using_db(conn).exists():
            raise EquipmentProgressionError("장착 중인 장비는 계승할 수 없습니다.")
        donor_def = await EquipmentItem.filter(item_id=donor.item_id).using_db(conn).first()
        target_def = await EquipmentItem.filter(item_id=target.item_id).using_db(conn).first()
        if not donor_def or not target_def or donor_def.equip_pos != target_def.equip_pos:
            raise EquipmentProgressionError("같은 슬롯의 장비끼리만 계승할 수 있습니다.")
        if donor.enhancement_level <= target.enhancement_level:
            raise EquipmentProgressionError("재료 장비의 강화 단계가 더 높아야 합니다.")
        inherited = donor.enhancement_level
        wallet = await _wallet(user, conn)
        if inherited >= 13:
            if use_catalyst:
                if wallet.preservation_catalysts <= 0:
                    raise EquipmentProgressionError("보존 촉매가 없습니다.")
                wallet.preservation_catalysts -= 1
                await wallet.save(using_db=conn, update_fields=["preservation_catalysts"])
            else:
                inherited -= 1
        target.enhancement_level = inherited
        await target.save(using_db=conn, update_fields=["enhancement_level"])
        await donor.delete(using_db=conn)
        result = {"donor_id": donor_id, "target_id": target_id, "enhancement": inherited, "catalyst": use_catalyst}
        await EquipmentActionReceipt.create(
            interaction_id=interaction_id, user=user, action="inherit",
            inventory_item_id=target_id, result=result, using_db=conn,
        )
    return result


def source_type_for_session(session) -> str:
    from service.session import ContentType
    if session.content_type == ContentType.RAID:
        return "raid"
    return "elite" if int(getattr(session.dungeon, "require_level", 1) or 1) >= 31 else "normal"


def is_daily_featured(source_key: str, *, now=None) -> bool:
    now = now or datetime.now(timezone.utc)
    # Roughly three of the 23 normal/elite sources are featured each day.
    import hashlib
    value = int.from_bytes(hashlib.sha256(f"{now.date()}:{source_key}".encode()).digest()[:4], "big")
    return value % 8 == 0


def is_weekly_featured_raid(source_key: str, *, now=None) -> bool:
    """Select one stable raid bucket for an ISO week without limiting entry."""
    now = now or datetime.now(timezone.utc)
    import hashlib
    iso_year, iso_week, _ = now.isocalendar()
    value = int.from_bytes(
        hashlib.sha256(f"{iso_year}-W{iso_week}:{source_key}".encode()).digest()[:4],
        "big",
    )
    # Raid sources are intentionally much scarcer than normal/elite sources.
    return value % 8 == 0


def is_featured_source(source_type: str, source_key: str, *, now=None) -> bool:
    if source_type == "raid":
        return is_weekly_featured_raid(source_key, now=now)
    return is_daily_featured(source_key, now=now)
