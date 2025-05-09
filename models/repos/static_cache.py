import logging

from models import Dungeon, Monster, DungeonSpawn

dungeon_cache = {}
monster_cache_by_id = {}
item_cache = {}
spawn_info = {}

async def load_static_data():
    global dungeon_cache, monster_cache_by_id, item_cache, spawn_info
    logging.info("Loading static data...")
    # 모든 던전 로딩
    dungeons = await Dungeon.all()
    dungeon_cache = {d.id: d for d in dungeons}

    monsters = await Monster.all()
    monster_cache_by_id = {m.id: m for m in monsters}

    all_spawns = await DungeonSpawn.all()
    for spawn in all_spawns:
        spawn_info.setdefault(spawn.dungeon_id, []).append(spawn)


def get_dungeons():
    return dungeon_cache
