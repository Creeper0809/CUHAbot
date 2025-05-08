import logging

from models import Dungeon

dungeon_cache = {}
monster_cache = {}
item_cache = {}

async def load_static_data():
    global dungeon_cache, monster_cache, item_cache
    logging.info("Loading static data...")
    # 모든 던전 로딩
    dungeons = await Dungeon.all()
    dungeon_cache = {d.id: d for d in dungeons}
    print(dungeon_cache)

def get_dungeons():
    return dungeon_cache
