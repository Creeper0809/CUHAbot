from models.repos import static_cache


def find_monster_by_id(id: int):
    return static_cache.monster_cache_by_id[id]
