from models.repos import static_cache

def find_all_dungeon():
    return list(static_cache.dungeon_cache.values())

def find_all_dungeon_spawn_monster_by(dungeon_id):
    return static_cache.spawn_info.get(dungeon_id, [])