import logging

from models import Dungeon, Monster, DungeonSpawn, Item, Skill_Model
from service.dungeon.skill import Skill
from service.dungeon.skill_component import get_component_by_tag, skill_component_register
from service.shop_service import ShopService

logger = logging.getLogger(__name__)

dungeon_cache = {}
monster_cache_by_id = {}
item_cache = {}
spawn_info = {}
skill_cache_by_id = {}


async def load_static_data():
    """정적 데이터 로드 (봇 시작 시 호출)"""
    global dungeon_cache, monster_cache_by_id, item_cache, spawn_info, skill_cache_by_id
    logger.info("Loading static data...")

    # 던전 로딩
    dungeons = await Dungeon.all()
    dungeon_cache = {d.id: d for d in dungeons}
    logger.info(f"Loaded {len(dungeon_cache)} dungeons")

    # 몬스터 로딩
    monsters = await Monster.all()
    monster_cache_by_id = {m.id: m for m in monsters}
    logger.info(f"Loaded {len(monster_cache_by_id)} monsters")

    # 스폰 정보 로딩
    all_spawns = await DungeonSpawn.all()
    for spawn in all_spawns:
        spawn_info.setdefault(spawn.dungeon_id, []).append(spawn)
    logger.info(f"Loaded spawn info for {len(spawn_info)} dungeons")

    # 아이템 로딩
    items = await Item.all()
    item_cache = {i.id: i for i in items}
    logger.info(f"Loaded {len(item_cache)} items")

    # 스킬 로딩
    logger.info(f"Registered skill component tags: {list(skill_component_register.keys())}")
    skills = await Skill_Model.all()
    for skill in skills:
        components = []
        # config 구조: {"components": [{"tag": "attack", ...}, ...]}
        component_configs = _resolve_skill_components(skill.config)

        if not component_configs:
            logger.warning(f"Skill {skill.id} ({skill.name}) has no components! Config: {skill.config}")

        for comp_config in component_configs:
            tag = comp_config.get("tag")
            if not tag:
                logger.warning(f"Skill {skill.id} has component without tag: {comp_config}")
                continue
            try:
                component = get_component_by_tag(tag)
                component.apply_config(comp_config, skill.name)
                components.append(component)
                logger.info(f"Skill {skill.id} ({skill.name}): loaded component '{tag}'")
            except KeyError:
                logger.warning(f"Unknown component tag '{tag}' in skill {skill.id}")

        skill_cache_by_id[skill.id] = Skill(skill, components)
        logger.info(f"Skill {skill.id} ({skill.name}): {len(components)} components loaded")

    logger.info(f"Loaded {len(skill_cache_by_id)} skills")

    # Grade 캐시 로딩 (상점 가격 등)
    await ShopService.load_grade_cache()


def _resolve_skill_components(skill_config):
    """레거시 스킬 설정을 컴포넌트 구조로 정규화"""
    if not isinstance(skill_config, dict):
        return []

    components = skill_config.get("components")
    if isinstance(components, list) and components:
        return components

    if "type" in skill_config and skill_config["type"] in skill_component_register:
        legacy_config = {k: v for k, v in skill_config.items() if k != "type"}
        return [{"tag": skill_config["type"], **legacy_config}]

    legacy_components = []
    for tag, config in skill_config.items():
        if tag in skill_component_register and isinstance(config, dict):
            legacy_components.append({"tag": tag, **config})

    return legacy_components


def get_dungeons():
    return dungeon_cache
