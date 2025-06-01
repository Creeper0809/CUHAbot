import logging

from models import Dungeon, Monster, DungeonSpawn, Item
from models import Dungeon, Monster, DungeonSpawn, Skill_Model
from service.dungeon.skill import Skill
from service.dungeon.skill_component import get_component_by_tag
from models import Dungeon, Monster, DungeonSpawn, Item

dungeon_cache = {}
monster_cache_by_id = {}
item_cache = {}
spawn_info = {}

skill_cache_by_id = {}

async def load_static_data():
    global dungeon_cache, monster_cache_by_id, item_cache, spawn_info, skill_cache_by_id
    logging.info("Loading static data...")
    # 모든 던전 로딩
    dungeons = await Dungeon.all()
    dungeon_cache = {d.id: d for d in dungeons}

    monsters = await Monster.all()
    monster_cache_by_id = {m.id: m for m in monsters}

    all_spawns = await DungeonSpawn.all()
    for spawn in all_spawns:
        spawn_info.setdefault(spawn.dungeon_id, []).append(spawn)

    #아이템 관련
    items = await Item.all()
    item_cache = {i.id: i for i in items}

    skills = await Skill_Model.all()
    for skill in skills:
        components = []
        for skill_component,config in skill.config.items():
            component = get_component_by_tag(skill_component)
            component.apply_config(config,skill.name)
            components.append(component)
        skill_cache_by_id[skill.id] = Skill(skill, components)
    print(skill_cache_by_id)



    #아이템 관련
    items = await Item.all()
    item_cache = {i.id: i for i in items}


def get_dungeons():
    return dungeon_cache
