"""
보상 계산기 - 몬스터 타입 판별, 보상 배율, 전투 결과 처리

전투 후 경험치/골드 계산 및 드롭 처리를 담당합니다.
"""
import logging
from typing import Optional

from config import DUNGEON, DROP
from models import Monster, MonsterTypeEnum, User, UserStatEnum
from service.collection_service import CollectionService

logger = logging.getLogger(__name__)


# =============================================================================
# 몬스터 타입 유틸리티
# =============================================================================


def normalize_monster_type(monster: Monster) -> Optional[str]:
    monster_type = getattr(monster, "type", None)
    if isinstance(monster_type, MonsterTypeEnum):
        return monster_type.value
    return monster_type


def is_boss_monster(monster: Monster) -> bool:
    return normalize_monster_type(monster) == MonsterTypeEnum.BOSS.value


def get_monster_exp_multiplier(monster: Monster) -> float:
    monster_type = normalize_monster_type(monster)
    if monster_type == MonsterTypeEnum.ELITE.value:
        return DUNGEON.ELITE_EXP_MULTIPLIER
    if monster_type == MonsterTypeEnum.BOSS.value:
        return DUNGEON.BOSS_EXP_MULTIPLIER
    return 1.0


def get_monster_gold_multiplier(monster: Monster) -> float:
    monster_type = normalize_monster_type(monster)
    if monster_type == MonsterTypeEnum.ELITE.value:
        return DUNGEON.ELITE_GOLD_MULTIPLIER
    if monster_type == MonsterTypeEnum.BOSS.value:
        return DUNGEON.BOSS_GOLD_MULTIPLIER
    return 1.0


def get_monster_drop_multiplier(monster: Monster) -> float:
    monster_type = normalize_monster_type(monster)
    if monster_type == MonsterTypeEnum.ELITE.value:
        return DROP.ELITE_DROP_MULTIPLIER
    if monster_type == MonsterTypeEnum.BOSS.value:
        return DROP.BOSS_DROP_MULTIPLIER
    return 1.0


def get_box_pool_by_monster(monster: Monster) -> list[tuple[int, float]]:
    """몬스터 타입에 따른 상자 풀 조회 (CSV 기반)"""
    from models.repos.static_cache import get_box_pool_by_monster_type

    monster_type = normalize_monster_type(monster)
    return get_box_pool_by_monster_type(monster_type)


# =============================================================================
# 스탯 유틸리티
# =============================================================================


def get_attack_stat(entity) -> int:
    if hasattr(entity, "get_stat"):
        stat = entity.get_stat()
        return int(stat.get(UserStatEnum.ATTACK, getattr(entity, "attack", 0)))
    return getattr(entity, "attack", 0)


# =============================================================================
# 전투 결과 처리 (다중 몬스터)
# =============================================================================


async def process_combat_result_multi(session, context, turn_count: int) -> str:
    """
    전투 결과 처리 (다중 몬스터)

    Args:
        session: 던전 세션
        context: 전투 컨텍스트
        turn_count: 총 턴 수

    Returns:
        결과 메시지
    """
    from service.dungeon.drop_handler import (
        try_drop_boss_special_item, try_drop_monster_box, try_drop_monster_skill,
    )

    user = session.user

    if user.now_hp <= 0:
        return "💀 패배..."

    # 승리 - 각 몬스터별 보상 합산
    monster_level = session.dungeon.require_level if session.dungeon else 1
    total_exp = 0
    total_gold = 0
    result_lines = []

    for monster in context.monsters:
        exp_mult = get_monster_exp_multiplier(monster)
        gold_mult = get_monster_gold_multiplier(monster)

        exp = int(DUNGEON.BASE_EXP_PER_MONSTER * (1 + monster_level / 10) * exp_mult)
        gold = int(DUNGEON.BASE_GOLD_PER_MONSTER * (1 + monster_level / 10) * gold_mult)

        total_exp += exp
        total_gold += gold

        await CollectionService.register_monster(user, monster.id)

        # 드롭 시도 (각 몬스터 독립)
        for drop_msg in await _try_all_drops(session, user, monster):
            result_lines.append(f"   {drop_msg}")

    # 그룹 보너스 (2마리 이상)
    if len(context.monsters) >= 2:
        total_exp = int(total_exp * 1.2)
        total_gold = int(total_gold * 1.1)

    session.total_exp += total_exp
    session.total_gold += total_gold
    session.monsters_defeated += len(context.monsters)

    monster_names = ", ".join([m.name for m in context.monsters])
    result_msg = (
        f"🏆 **{monster_names}** 처치! ({turn_count}턴)\n"
        f"   ⭐ +**{total_exp}** EXP │ 💰 +**{total_gold}** G"
    )

    if result_lines:
        result_msg += "\n" + "\n".join(result_lines)

    return result_msg


async def _try_all_drops(session, user: User, monster: Monster) -> list[str]:
    """모든 드롭 시도 후 메시지 리스트 반환"""
    from service.dungeon.drop_handler import (
        try_drop_boss_special_item, try_drop_monster_box, try_drop_monster_skill,
    )

    drops = []
    boss_item = await try_drop_boss_special_item(user, monster)
    if boss_item:
        drops.append(boss_item)

    chest = await try_drop_monster_box(session, monster)
    if chest:
        drops.append(chest)

    skill = await try_drop_monster_skill(user, monster)
    if skill:
        drops.append(skill)

    return drops
