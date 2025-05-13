from models.repos import static_cache

def get_skill_by_id(id):
    print(static_cache.skill_cache_by_id.get(id))
    return static_cache.skill_cache_by_id.get(id)