import logging

from models import Dungeon, Monster, DungeonSpawn, Item, Skill_Model
from service.dungeon.skill import Skill
from service.dungeon.components import get_component_by_tag, skill_component_register
from service.economy.shop_service import ShopService

logger = logging.getLogger(__name__)

dungeon_cache = {}
monster_cache_by_id = {}
item_cache = {}
spawn_info = {}
skill_cache_by_id = {}
box_drop_table = {}  # {"normal": [(box_id, weight), ...], ...}
_dungeon_levels_sorted: list[int] = []  # 던전 require_level 정렬 리스트
equipment_cache = {}  # item_id -> EquipmentItem
set_name_by_item_id = {}  # item_id -> set_name (e.g. "🔥 화염")
equipment_by_source = {}  # acquisition_source -> [item_id, ...]


async def load_static_data():
    """정적 데이터 로드 (봇 시작 시 호출)"""
    global dungeon_cache, monster_cache_by_id, item_cache, spawn_info, skill_cache_by_id, box_drop_table, _dungeon_levels_sorted
    logger.info("Loading static data...")

    # 던전 로딩
    dungeons = await Dungeon.all()
    dungeon_cache = {d.id: d for d in dungeons}
    _dungeon_levels_sorted = sorted(set(d.require_level for d in dungeons))
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
                component._tag = tag
                component.apply_config(comp_config, skill.name)
                component.skill_attribute = getattr(skill, 'attribute', '무속성')
                components.append(component)
                logger.info(f"Skill {skill.id} ({skill.name}): loaded component '{tag}'")
            except KeyError:
                logger.warning(f"Unknown component tag '{tag}' in skill {skill.id}")

        skill_cache_by_id[skill.id] = Skill(skill, components)
        logger.info(f"Skill {skill.id} ({skill.name}): {len(components)} components loaded")

    logger.info(f"Loaded {len(skill_cache_by_id)} skills")

    # 장비 캐시 로딩
    await _load_equipment_cache()

    # Grade 캐시 로딩 (상점 가격 등)
    await ShopService.load_grade_cache()

    # 상자 드랍 테이블 로딩
    await load_box_drop_table()


EQUIP_POS_NAMES = {
    1: "투구", 2: "갑옷", 3: "신발", 4: "무기",
    5: "보조무기", 6: "장갑", 7: "목걸이", 8: "반지",
}


async def _load_equipment_cache():
    """장비 및 세트 캐시 로드"""
    global equipment_cache, set_name_by_item_id, equipment_by_source

    from models.equipment_item import EquipmentItem
    from models.set_item import SetItem, SetItemMember

    # EquipmentItem: item_id -> EquipmentItem
    all_equip = await EquipmentItem.all()
    equipment_cache = {eq.item_id: eq for eq in all_equip}
    logger.info(f"Loaded {len(equipment_cache)} equipment items into cache")

    # 획득처별 장비 캐시 (acquisition_source -> [item_id, ...])
    equipment_by_source = {}
    for eq in all_equip:
        source = getattr(eq, 'acquisition_source', None)
        if source:
            equipment_by_source.setdefault(source, []).append(eq.item_id)
    logger.info(f"Loaded equipment_by_source: {len(equipment_by_source)} sources")

    # SetItemMember -> SetItem: item_id -> set_name
    all_sets = await SetItem.all()
    set_name_map = {s.id: s.name for s in all_sets}

    all_members = await SetItemMember.all()
    # equipment_item_id(PK) -> item_id 역매핑
    equip_pk_to_item_id = {eq.id: eq.item_id for eq in all_equip}

    for member in all_members:
        item_id = equip_pk_to_item_id.get(member.equipment_item_id)
        set_name = set_name_map.get(member.set_item_id)
        if item_id and set_name:
            set_name_by_item_id[item_id] = set_name

    logger.info(f"Loaded {len(set_name_by_item_id)} set memberships into cache")


def get_equipment_ids_by_source(source: str) -> list[int]:
    """획득처 이름으로 장비 아이템 ID 리스트 조회"""
    return equipment_by_source.get(source, [])


def get_equipment_info(item_id: int) -> dict:
    """장비 아이템 캐시 정보 조회"""
    eq = equipment_cache.get(item_id)
    if not eq:
        return {}
    return {
        "require_level": eq.require_level or 1,
        "equip_pos": EQUIP_POS_NAMES.get(eq.equip_pos, ""),
        "attack": eq.attack,
        "ap_attack": eq.ap_attack,
        "hp": eq.hp,
        "ad_defense": eq.ad_defense,
        "ap_defense": eq.ap_defense,
        "speed": eq.speed,
        "set_name": set_name_by_item_id.get(item_id, ""),
        "require_str": eq.require_str or 0,
        "require_int": eq.require_int or 0,
        "require_dex": eq.require_dex or 0,
        "require_vit": eq.require_vit or 0,
        "require_luk": eq.require_luk or 0,
        "config": eq.config,  # 특수 효과 정보
    }


async def load_box_drop_table():
    """상자 드랍 테이블 CSV 로드"""
    import csv
    global box_drop_table

    csv_path = "data/box_drop_table.csv"
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                monster_type = row['monster_type']
                box_id = int(row['box_id'])
                weight = float(row['weight'])

                if monster_type not in box_drop_table:
                    box_drop_table[monster_type] = []
                box_drop_table[monster_type].append((box_id, weight))

        logger.info(f"Loaded box drop table: {len(box_drop_table)} monster types")
    except FileNotFoundError:
        logger.warning(f"Box drop table not found: {csv_path}")
        box_drop_table = {}


def get_box_pool_by_monster_type(monster_type: str) -> list[tuple[int, float]]:
    """몬스터 타입별 상자 풀 조회"""
    return box_drop_table.get(monster_type, [])


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


def get_previous_dungeon_level(current_level: int) -> int:
    """현재 던전 렙제의 바로 이전 단계 던전 렙제 반환"""
    for i, lvl in enumerate(_dungeon_levels_sorted):
        if lvl >= current_level:
            return _dungeon_levels_sorted[i - 1] if i > 0 else 0
    return _dungeon_levels_sorted[-1] if _dungeon_levels_sorted else 0
