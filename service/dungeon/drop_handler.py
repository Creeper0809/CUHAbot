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
from service.item.grade_service import GradeService

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

    # 탐험 드롭률 버프 적용
    drop_bonus = session.explore_buffs.get("drop_bonus", 0)
    if drop_bonus > 0:
        drop_rate *= (1 + drop_bonus / 100)
        session.explore_buffs["drop_bonus"] = 0
        del session.explore_buffs["drop_bonus"]

    # 스탯 시너지: 드롭률 배수 (운명의 총아)
    from service.player.stat_synergy_combat import get_drop_rate_multiplier
    drop_rate *= get_drop_rate_multiplier(session.user)

    if random.random() > min(drop_rate, 1.0):
        return None

    box_pool = get_box_pool_by_monster(monster)
    if not box_pool:
        logger.warning(f"No box pool for monster type: {monster.type}")
        return None

    box_ids = [box_id for box_id, _ in box_pool]
    weights = [weight for _, weight in box_pool]
    box_id = random.choices(box_ids, weights=weights, k=1)[0]

    # 던전 레벨을 instance_grade에 저장 (상자 렙제 필터링용)
    from models.repos.static_cache import get_previous_dungeon_level
    dungeon_level = session.dungeon.require_level if session.dungeon else 0
    prev_level = get_previous_dungeon_level(dungeon_level)

    try:
        await InventoryService.add_item(
            session.user, box_id, 1,
            instance_grade=dungeon_level,
        )
    except InventoryFullError:
        return "📦 상자를 얻었지만 인벤토리가 가득 찼다..."

    item = await Item.get_or_none(id=box_id)
    item_name = item.name if item else "상자"
    return f"📦 「{item_name}({prev_level}~{dungeon_level}Lv)」 획득!"


async def try_drop_boss_special_item(user: User, monster: Monster) -> Optional[str]:
    """보스 전용 아이템 드롭 (인스턴스 등급 부여)"""
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

    # 인스턴스 등급 롤링 (보스 컨텍스트)
    grade = GradeService.roll_grade("boss")
    effects = GradeService.roll_special_effects(grade)
    grade_display = GradeService.get_grade_display(grade)

    try:
        await InventoryService.add_item(
            user, item.id, 1,
            instance_grade=grade,
            special_effects=effects,
        )
    except InventoryFullError:
        return "🎖️ 보스 전리품을 얻었지만 인벤토리가 가득 찼다..."

    return f"🎖️ **보스 전리품!** {grade_display} 「{item.name}」 획득!"


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

    # drop_skill_ids 우선, 없으면 skill_ids에서 player_obtainable 필터링 (fallback)
    drop_skills = getattr(monster, 'drop_skill_ids', [])
    if drop_skills:
        valid_skills = [sid for sid in drop_skills if sid != 0]
    else:
        monster_skills = getattr(monster, 'skill_ids', [])
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
