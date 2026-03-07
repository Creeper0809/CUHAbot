from models.repos import static_cache


def find_raid_by_id(raid_id: int):
    return static_cache.raid_cache_by_id.get(raid_id)


def find_raid_by_dungeon_id(dungeon_id: int):
    return static_cache.raid_cache_by_dungeon_id.get(dungeon_id)


def find_all_raid_parts(raid_id: int):
    return static_cache.raid_parts_by_raid_id.get(raid_id, [])


def find_all_raid_gimmicks(raid_id: int):
    return static_cache.raid_gimmicks_by_raid_id.get(raid_id, [])


def find_raid_targeting_rule(raid_id: int):
    return static_cache.raid_targeting_rules_by_raid_id.get(raid_id)


def find_raid_special_actions():
    return static_cache.raid_special_actions_by_key
