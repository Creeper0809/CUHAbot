"""Integrated equipment, stat, and skill presets plus build graph analysis."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from tortoise import transactions

from config import BUILD_PRESET_LIMIT, SKILL_DECK_SIZE
from models import (
    EquipmentItem, Skill_Model, UserBuildPreset, UserBuildPresetItem,
    UserEquipment, UserEquipmentAffix, UserInventory, UserSkillDeck,
)
from models.user_equipment import EquipmentSlot
from service.session import get_session
from service.skill.design_v3 import first_link_probability


class BuildPresetError(ValueError):
    pass


EQUIP_POS_TO_SLOT = {
    1: EquipmentSlot.HELMET, 2: EquipmentSlot.ARMOR, 3: EquipmentSlot.BOOTS,
    4: EquipmentSlot.WEAPON, 5: EquipmentSlot.SUB_WEAPON, 6: EquipmentSlot.GLOVES,
    7: EquipmentSlot.NECKLACE, 8: EquipmentSlot.RING1, 9: EquipmentSlot.RING2,
}


def _model_is_passive(skill: Skill_Model) -> bool:
    from service.dungeon.skill import PASSIVE_TAGS
    components = (skill.config or {}).get("components", [])
    return bool(components) and all(component.get("tag") in PASSIVE_TAGS for component in components)


@dataclass(frozen=True)
class BuildApplication:
    preset_id: int
    name: str
    missing_slots: tuple[int, ...]


async def save_build(user, name: str, *, note: str = "", content_key: str = "") -> UserBuildPreset:
    if not name.strip():
        raise BuildPresetError("프리셋 이름을 입력해야 합니다.")
    existing = await UserBuildPreset.get_or_none(user=user, name=name.strip())
    if not existing and await UserBuildPreset.filter(user=user).count() >= BUILD_PRESET_LIMIT:
        raise BuildPresetError(f"통합 빌드 프리셋은 최대 {BUILD_PRESET_LIMIT}개입니다.")
    deck_rows = await UserSkillDeck.filter(user=user).order_by("slot_index")
    deck = [0] * SKILL_DECK_SIZE
    for row in deck_rows:
        if 0 <= row.slot_index < SKILL_DECK_SIZE:
            deck[row.slot_index] = row.skill_id
    preset, _ = await UserBuildPreset.update_or_create(
        user=user, name=name.strip(),
        defaults={
            "note": note[:160], "content_key": content_key[:64],
            "bonus_str": user.bonus_str, "bonus_int": user.bonus_int,
            "bonus_dex": user.bonus_dex, "bonus_vit": user.bonus_vit,
            "bonus_luk": user.bonus_luk, "skill_ids": deck,
        },
    )
    await UserBuildPresetItem.filter(preset=preset).delete()
    equipped = await UserEquipment.filter(user=user)
    await UserBuildPresetItem.bulk_create([
        UserBuildPresetItem(preset=preset, slot=int(row.slot), inventory_item_id=row.inventory_item_id)
        for row in equipped
    ])
    return preset


async def apply_build(user, preset_id: int) -> BuildApplication:
    session = get_session(user.discord_id)
    if session and not getattr(session, "ended", False):
        raise BuildPresetError("던전·타워·레이드 진행 중에는 빌드를 바꿀 수 없습니다.")
    preset = await UserBuildPreset.get_or_none(id=preset_id, user=user)
    if not preset:
        raise BuildPresetError("빌드 프리셋을 찾을 수 없습니다.")
    references = list(await UserBuildPresetItem.filter(preset=preset).prefetch_related("inventory_item__item"))
    missing: list[int] = []
    selected: list[tuple[int, UserInventory, EquipmentItem]] = []
    seen_inventory: set[int] = set()
    target_stats = {
        "STR": preset.bonus_str, "INT": preset.bonus_int, "DEX": preset.bonus_dex,
        "VIT": preset.bonus_vit, "LUK": preset.bonus_luk,
    }
    for ref in references:
        item = ref.inventory_item
        if not item or item.user_id != user.id:
            missing.append(ref.slot)
            continue
        if item.id in seen_inventory:
            raise BuildPresetError("한 장비가 여러 슬롯에 중복 저장되어 있습니다.")
        seen_inventory.add(item.id)
        if item.is_locked:
            raise BuildPresetError(f"슬롯 {ref.slot} 장비가 경매 잠금 상태입니다.")
        equipment = await EquipmentItem.get_or_none(item_id=item.item_id)
        if not equipment:
            raise BuildPresetError("프리셋 장비 정의를 찾을 수 없습니다.")
        if equipment.require_level and user.level < equipment.require_level:
            raise BuildPresetError(f"{item.item.name}: 요구 레벨 Lv.{equipment.require_level}")
        for stat, required in equipment.get_requirements().items():
            if target_stats.get(stat, 0) < required:
                raise BuildPresetError(f"{item.item.name}: {stat} {required} 필요")
        expected_slot = EQUIP_POS_TO_SLOT.get(equipment.equip_pos)
        if expected_slot is None or int(expected_slot) != int(ref.slot):
            raise BuildPresetError(f"{item.item.name}: 저장 슬롯과 장비 부위가 일치하지 않습니다.")
        selected.append((ref.slot, item, equipment))

    skills = [int(skill_id) for skill_id in (preset.skill_ids or [])]
    if len(skills) != SKILL_DECK_SIZE or any(skill_id <= 0 for skill_id in skills):
        raise BuildPresetError("프리셋의 10칸 스킬 덱이 완성되지 않았습니다.")
    skill_models = list(await Skill_Model.filter(id__in=set(skills)))
    if len(skill_models) != len(set(skills)):
        raise BuildPresetError("프리셋에 존재하지 않는 스킬이 있습니다.")
    passive_ids = {skill.id for skill in skill_models if _model_is_passive(skill)}
    repeated_passives = sorted(skill_id for skill_id in passive_ids if skills.count(skill_id) > 1)
    if repeated_passives:
        raise BuildPresetError("같은 패시브 스킬은 여러 장 장착할 수 없습니다: " + ", ".join(map(str, repeated_passives)))

    async with transactions.in_transaction() as conn:
        await UserEquipment.filter(user=user).using_db(conn).delete()
        for slot, item, _ in selected:
            await UserEquipment.create(user=user, slot=EquipmentSlot(slot), inventory_item=item, using_db=conn)
        locked_user = await type(user).filter(id=user.id).using_db(conn).select_for_update().first()
        locked_user.bonus_str = preset.bonus_str
        locked_user.bonus_int = preset.bonus_int
        locked_user.bonus_dex = preset.bonus_dex
        locked_user.bonus_vit = preset.bonus_vit
        locked_user.bonus_luk = preset.bonus_luk
        spent = sum(target_stats.values())
        locked_user.stat_points = max(0, 3 * max(0, locked_user.level - 1) - spent)
        await locked_user.save(using_db=conn)
        await UserSkillDeck.filter(user=user).using_db(conn).delete()
        for index, skill_id in enumerate(skills):
            await UserSkillDeck.create(user=user, slot_index=index, skill_id=skill_id, using_db=conn)

    user.bonus_str, user.bonus_int = preset.bonus_str, preset.bonus_int
    user.bonus_dex, user.bonus_vit, user.bonus_luk = preset.bonus_dex, preset.bonus_vit, preset.bonus_luk
    from service.item.equipment_service import EquipmentService
    from service.skill.skill_deck_service import SkillDeckService
    await EquipmentService.apply_equipment_stats(user)
    await SkillDeckService.load_deck_to_user(user)
    return BuildApplication(preset.id, preset.name, tuple(sorted(missing)))


async def analyze_build(user) -> dict:
    deck = [row.skill_id for row in await UserSkillDeck.filter(user=user).order_by("slot_index").prefetch_related("skill")]
    setup: Counter[str] = Counter()
    payoff: Counter[str] = Counter()
    roles: Counter[str] = Counter()
    for skill_id in deck:
        skill = await Skill_Model.get(id=skill_id)
        design = (skill.config or {}).get("design", {})
        setup.update(str(tag) for tag in design.get("setup_tags", []))
        payoff.update(str(tag) for tag in design.get("payoff_tags", []))
        if design.get("role"):
            roles[str(design["role"])] += 1
    equipped = await UserEquipment.filter(user=user)
    affix_rows = await UserEquipmentAffix.filter(
        inventory_item_id__in=[row.inventory_item_id for row in equipped]
    ).prefetch_related("affix_definition") if equipped else []
    for row in affix_rows:
        setup.update(str(tag) for tag in (row.affix_definition.setup_tags or []))
        payoff.update(str(tag) for tag in (row.affix_definition.payoff_tags or []))
    links = []
    for tag in sorted(set(setup) | set(payoff)):
        links.append({
            "tag": tag, "setup": setup[tag], "payoff": payoff[tag],
            "probability": first_link_probability(setup[tag], payoff[tag]),
        })
    return {
        "roles": dict(roles), "links": links,
        "orphan_payoffs": sorted(tag for tag in payoff if payoff[tag] and not setup[tag]),
        "unused_setups": sorted(tag for tag in setup if setup[tag] and not payoff[tag]),
    }


async def compare_equipment(user, inventory_id: int) -> dict:
    candidate = await UserInventory.get_or_none(id=inventory_id, user=user).prefetch_related("item")
    if not candidate:
        raise BuildPresetError("비교할 장비를 찾을 수 없습니다.")
    candidate_def = await EquipmentItem.get_or_none(item_id=candidate.item_id)
    if not candidate_def:
        raise BuildPresetError("장비 정의를 찾을 수 없습니다.")
    slot = EQUIP_POS_TO_SLOT.get(candidate_def.equip_pos)
    current = await UserEquipment.filter(user=user, slot=slot).prefetch_related("inventory_item__item").first() if slot else None

    from config import BALANCE_V2
    from service.item.grade_service import GradeService
    from service.item.affix_service import get_affix_bundle

    async def snapshot(inv, definition):
        if not inv or not definition:
            return {key: 0.0 for key in ("hp", "attack", "ap_attack", "ad_defense", "ap_defense", "speed")}
        mult = GradeService.get_stat_multiplier(inv.instance_grade) * BALANCE_V2.enhancement_stat_multiplier(inv.enhancement_level)
        values = {
            "hp": (definition.hp or 0) * mult, "attack": (definition.attack or 0) * mult,
            "ap_attack": (definition.ap_attack or 0) * mult,
            "ad_defense": (definition.ad_defense or 0) * mult,
            "ap_defense": (definition.ap_defense or 0) * mult, "speed": (definition.speed or 0) * mult,
        }
        bundle = await get_affix_bundle(inv)
        for key in values:
            values[key] += getattr(bundle, key)
            values[key] *= 1 + getattr(bundle, f"{key}_pct", 0.0)
        values.update({
            "crit_rate": bundle.critical_rate, "crit_damage": bundle.critical_damage,
            "armor_pen": bundle.armor_penetration * 100, "magic_pen": bundle.magic_penetration * 100,
            "drop_rate": bundle.drop_rate,
        })
        return values

    current_def = await EquipmentItem.get_or_none(item_id=current.inventory_item.item_id) if current else None
    before, after = await snapshot(current.inventory_item if current else None, current_def), await snapshot(candidate, candidate_def)
    keys = sorted(set(before) | set(after))
    deltas = {key: round(after.get(key, 0) - before.get(key, 0), 2) for key in keys}

    from models import UserStatEnum
    from service.item.equipment_service import EquipmentService
    await EquipmentService.apply_equipment_stats(user)
    live = user.get_stat()
    stat_keys = {
        "hp": UserStatEnum.HP, "attack": UserStatEnum.ATTACK,
        "ap_attack": UserStatEnum.AP_ATTACK, "ad_defense": UserStatEnum.DEFENSE,
        "ap_defense": UserStatEnum.AP_DEFENSE, "speed": UserStatEnum.SPEED,
        "crit_rate": UserStatEnum.CRITICAL_RATE, "crit_damage": UserStatEnum.CRITICAL_DAMAGE,
    }
    live_before = {key: float(live.get(enum, 0)) for key, enum in stat_keys.items()}
    live_after = {key: value + deltas.get(key, 0.0) for key, value in live_before.items()}
    benchmark = BALANCE_V2.base_stats(user.level)

    def trial(stats: dict) -> dict:
        offense = max(stats["attack"], stats["ap_attack"])
        crit_rate = min(BALANCE_V2.max_critical_rate, max(0.0, stats.get("crit_rate", 0) / 100))
        crit_mult = min(BALANCE_V2.max_critical_damage, max(1.0, stats.get("crit_damage", 150) / 100))
        expected_raw = offense * (1 + crit_rate * (crit_mult - 1))
        boss_defense = max(benchmark.ad_defense, benchmark.ap_defense) * 1.15
        action_damage = expected_raw * (1 - BALANCE_V2.defense_reduction(boss_defense))
        enemy_raw = max(benchmark.attack, benchmark.ap_attack) * 1.2
        own_defense = (stats["ad_defense"] + stats["ap_defense"]) / 2
        incoming = enemy_raw * (1 - BALANCE_V2.defense_reduction(own_defense))
        action_rate = BALANCE_V2.action_rate(stats["speed"])
        clear_score = min(0.98, max(0.05, 0.65 + (action_damage * action_rate / max(1, benchmark.hp) - 0.08) * 2.5))
        return {
            "boss_damage_8_actions": round(action_damage * 8),
            "survival_after_10_enemy_actions": round(stats["hp"] - incoming * 10),
            "estimated_clear_rate": round(clear_score, 4),
            "relative_reward_per_minute": round(action_rate * clear_score, 3),
        }

    warnings = []
    if live_after.get("crit_rate", 0) >= BALANCE_V2.max_critical_rate * 100:
        warnings.append("치명타 확률 상한 도달")
    if live_after.get("speed", 100) >= 200:
        warnings.append("속도 행동률 상한 구간 접근")
    if candidate_def.set_key != (current_def.set_key if current_def else ""):
        warnings.append("세트 단계가 변할 수 있으므로 실제 활성 효과를 확인하세요")
    return {
        "slot": int(slot) if slot else 0,
        "current_name": current.inventory_item.item.name if current else "비어 있음",
        "candidate_name": candidate.item.name,
        "deltas": deltas,
        "set_change": {"from": getattr(current_def, "set_key", "") if current_def else "", "to": candidate_def.set_key or ""},
        "trial": {"before": trial(live_before), "after": trial(live_after)},
        "warnings": warnings,
    }


async def rename_build(user, preset_id: int, name: str) -> UserBuildPreset:
    preset = await UserBuildPreset.get_or_none(id=preset_id, user=user)
    if not preset:
        raise BuildPresetError("빌드 프리셋을 찾을 수 없습니다.")
    name = name.strip()
    if not name:
        raise BuildPresetError("새 이름을 입력해야 합니다.")
    if await UserBuildPreset.filter(user=user, name=name).exclude(id=preset.id).exists():
        raise BuildPresetError("같은 이름의 빌드가 이미 있습니다.")
    preset.name = name[:24]
    await preset.save(update_fields=["name", "updated_at"])
    return preset


async def delete_build(user, preset_id: int) -> str:
    preset = await UserBuildPreset.get_or_none(id=preset_id, user=user)
    if not preset:
        raise BuildPresetError("빌드 프리셋을 찾을 수 없습니다.")
    name = preset.name
    await preset.delete()
    return name
