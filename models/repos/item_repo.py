from models.repos import static_cache

def fine_all_item():
    return list(static_cache.item_cache.values())

def find_item_by_id(item_id):
    return static_cache.item_cache.get(item_id, [])