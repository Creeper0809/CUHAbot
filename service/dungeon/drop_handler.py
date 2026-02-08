"""
드롭 핸들러 - 상자/보스 아이템/스킬 드롭

전투 승리 후 아이템 및 스킬 드롭을 처리합니다.
"""
import logging
import random
from typing import Optional

from config import DROP, DUNGEON
from exceptions import InventoryFullError
from models import Droptable, Item, Monster, User
from service.item.inventory_service import InventoryService

logger = logging.getLogger(__name__)


async def try_drop_monster_box(session, monster: Monster) -> Optional[str]:
    """
    몬스터 상자 드랍 시도

    Args:
        session: 던전 세션
        monster: 몬스터 객체

    Returns:
        드랍 메시지 또는 None
    """
    from service.dungeon.reward_calculator import get_monster_drop_multiplier, get_box_pool_by_monster

    base_rate = DROP.BOX_DROP_RATE * get_monster_drop_multiplier(monster)
    luck = session.user.get_luck()
    luck_multiplier = 1.0 + (luck * DUNGEON.LUCK_DROP_BONUS_PER_POINT)
    drop_rate = base_rate * luck_multiplier

    if random.random() > min(drop_rate, 1.0):
        return None

    box_pool = get_box_pool_by_monster(monster)
    if not box_pool:
        logger.warning(f"No box pool for monster type: {monster.type}")
        return None

    box_ids = [box_id for box_id, _ in box_pool]
    weights = [weight for _, weight in box_pool]
    box_id = random.choices(box_ids, weights=weights, k=1)[0]

    try:
        await InventoryService.add_item(session.user, box_id, 1)
    except InventoryFullError:
        return "📦 상자를 얻었지만 인벤토리가 가득 찼다..."

    item = await Item.get_or_none(id=box_id)
    item_name = item.name if item else "상자"
    return f"📦 「{item_name}」 획득!"


async def try_drop_boss_special_item(user: User, monster: Monster) -> Optional[str]:
    """보스 전용 아이템 드롭"""
    from service.dungeon.reward_calculator import is_boss_monster

    if not is_boss_monster(monster):
        return None

    drop_rows = await Droptable.filter(drop_monster=monster.id).all()
    if not drop_rows:
        return None

    valid_rows = [row for row in drop_rows if row.item_id]
    if not valid_rows:
        return None

    weights = [float(row.probability or 0) for row in valid_rows]
    if sum(weights) <= 0:
        return None

    chosen = random.choices(valid_rows, weights=weights, k=1)[0]
    item = await Item.get_or_none(id=chosen.item_id)
    if not item:
        return None

    try:
        await InventoryService.add_item(user, item.id, 1)
    except InventoryFullError:
        return "🎖️ 보스 전리품을 얻었지만 인벤토리가 가득 찼다..."

    return f"🎖️ **보스 전리품!** 「{item.name}」 획득!"


async def try_drop_monster_skill(user: User, monster: Monster) -> Optional[str]:
    """
    몬스터 스킬 드롭 시도

    Args:
        user: 플레이어
        monster: 처치한 몬스터

    Returns:
        드롭 메시지 또는 None
    """
    from service.skill.skill_ownership_service import SkillOwnershipService
    from models.repos.skill_repo import get_skill_by_id

    monster_skills = getattr(monster, 'skill_ids', [])
    if not monster_skills:
        return None

    valid_skills = [sid for sid in monster_skills if sid != 0]
    if not valid_skills:
        return None

    if random.random() > DROP.SKILL_DROP_RATE:
        return None

    # 플레이어 획득 가능한 스킬만 필터링
    droppable_skills = []
    for sid in valid_skills:
        skill = get_skill_by_id(sid)
        if skill and getattr(skill.skill_model, 'player_obtainable', True):
            droppable_skills.append(sid)

    if not droppable_skills:
        return None

    dropped_skill_id = random.choice(droppable_skills)

    try:
        await SkillOwnershipService.add_skill(user, dropped_skill_id, 1)

        skill = get_skill_by_id(dropped_skill_id)
        skill_name = skill.name if skill else f"스킬 #{dropped_skill_id}"

        logger.info(
            f"Skill drop: user={user.discord_id}, monster={monster.name}, "
            f"skill_id={dropped_skill_id}, skill_name={skill_name}"
        )
        return f"✨ **희귀 드롭!** 「{skill_name}」 스킬 획득!"
    except Exception as e:
        logger.error(f"Failed to drop skill: {e}")
        return None
