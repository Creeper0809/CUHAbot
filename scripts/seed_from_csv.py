"""
데이터베이스 초기화 및 CSV 시드 스크립트

모든 테이블을 초기화하고 data/ 폴더의 CSV 파일에서 게임 데이터를 불러옵니다.

실행: python scripts/seed_from_csv.py
"""
import asyncio
import csv
import json
import os
import re
import sys
import unicodedata

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv
from tortoise import Tortoise
from config import BALANCE_V2

load_dotenv()

DATA_DIR = os.path.join(PROJECT_ROOT, "data")


# ============================================================
# 매핑 테이블
# ============================================================

GRADE_NAME_TO_ID = {
    "D": 1, "C": 2, "B": 3, "A": 4, "S": 5,
    "SS": 6, "SSS": 7, "Mythic": 8, "신화": 8,
}

SLOT_TO_EQUIP_POS = {
    "검": 4, "도끼": 4, "지팡이": 4, "활": 4, "무기": 4,
    "투구": 1,
    "갑옷": 2, "방어구": 2,
    "신발": 3,
    "방패": 5, "오브": 5,
    "장갑": 6,
    "목걸이": 7,
    "반지": 8,
}

# monsters.csv 던전명 → dungeons.csv 던전명 (불일치 보정)
DUNGEON_NAME_ALIAS = {
    "잊혀진 문명": "잊혀진 문명의 폐허",
    "시련의 탑": "시련의 탑 100층",
    "✨/🌑": None,  # 신성/암흑 복합 → 스킵 (개별 지정 필요)
}


# ============================================================
# CSV 유틸리티
# ============================================================

def read_csv(filename: str) -> list[dict]:
    """CSV 파일을 읽어 dict 리스트로 반환"""
    filepath = os.path.join(DATA_DIR, filename)
    with open(filepath, "r", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def safe_int(value: str, default: int = 0) -> int:
    """문자열을 int로 안전하게 변환"""
    if not value or not value.strip():
        return default
    cleaned = value.strip().lstrip("+")
    try:
        return int(cleaned)
    except ValueError:
        return default


def parse_grade(grade_str: str) -> int | None:
    """등급 문자열 → Grade ID 변환 (범위 등급은 첫 번째 사용)"""
    grade_str = grade_str.strip()
    if grade_str in GRADE_NAME_TO_ID:
        return GRADE_NAME_TO_ID[grade_str]
    if "~" in grade_str:
        return GRADE_NAME_TO_ID.get(grade_str.split("~")[0])
    return None


def parse_hp_amount(effect_str: str) -> int:
    """효과 문자열에서 HP 회복량 추출"""
    if not effect_str:
        return 0
    match = re.search(r"HP\s*(\d+)\s*회복", effect_str)
    if match:
        return int(match.group(1))
    if "완전히 회복" in effect_str or "완전 회복" in effect_str:
        return 9999
    return 0


def parse_level(level_str: str) -> int:
    """레벨 문자열에서 최소 레벨 추출 ('1-5' → 1, '30+' → 30)"""
    if not level_str:
        return 1
    level_str = level_str.strip().rstrip("+")
    if "-" in level_str:
        return safe_int(level_str.split("-")[0], 1)
    return safe_int(level_str, 1)


def nullable_int(value: str) -> int | None:
    """빈 문자열이면 None, 아니면 int"""
    if not value or not value.strip():
        return None
    cleaned = value.strip().lstrip("+")
    try:
        return int(cleaned)
    except ValueError:
        return None


def strip_emoji(text: str) -> str:
    """이모지를 제거하고 이름만 추출 ('🔥 화염' → '화염')"""
    result = []
    for ch in text:
        cat = unicodedata.category(ch)
        if cat not in ("So", "Sk", "Cf", "Mn"):
            result.append(ch)
    return "".join(result).strip()


def safe_float(value: str, default: float = 0.0) -> float:
    """문자열을 float로 안전하게 변환"""
    if not value or not value.strip():
        return default
    try:
        return float(value.strip())
    except ValueError:
        return default


def safe_bool(value: str, default: bool = False) -> bool:
    """문자열을 bool로 안전하게 변환"""
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "t", "y", "yes"}


# ============================================================
# DB 초기화
# ============================================================

async def init_db():
    """데이터베이스 연결 초기화"""
    db_url = (
        f"postgres://{os.getenv('DATABASE_USER')}:{os.getenv('DATABASE_PASSWORD')}@"
        f"{os.getenv('DATABASE_URL')}:{os.getenv('DATABASE_PORT')}/{os.getenv('DATABASE_TABLE')}"
    )
    await Tortoise.init(
        db_url=db_url,
        modules={"models": ["models"]}
    )
    await Tortoise.generate_schemas(safe=True)
    # generate_schemas(safe=True) does not add columns to an existing table.
    # Keep CSV reseeding compatible with pre-V2 isolated databases before any
    # Monster bulk insert references the new fields.
    connection = Tortoise.get_connection("default")
    for statement in (
        "ALTER TABLE monster ADD COLUMN IF NOT EXISTS ap_defense INT NOT NULL DEFAULT 0",
        "ALTER TABLE monster ADD COLUMN IF NOT EXISTS accuracy INT NOT NULL DEFAULT 95",
        "ALTER TABLE monster ADD COLUMN IF NOT EXISTS evasion INT NOT NULL DEFAULT 5",
        "ALTER TABLE monster ADD COLUMN IF NOT EXISTS phase_config JSONB NOT NULL DEFAULT '{}'::jsonb",
        "ALTER TABLE monster ADD COLUMN IF NOT EXISTS action_profile JSONB NOT NULL DEFAULT '{}'::jsonb",
        "ALTER TABLE equipment_item ADD COLUMN IF NOT EXISTS set_key VARCHAR(64) NOT NULL DEFAULT ''",
        "ALTER TABLE monster ALTER COLUMN speed SET DEFAULT 100",
    ):
        await connection.execute_query(statement)


async def reset_all_tables():
    """모든 테이블 데이터 삭제 (TRUNCATE CASCADE)"""
    conn = Tortoise.get_connection("default")

    # FK 의존성 순서대로 삭제 (자식 → 부모)
    tables = [
        # 레이드 시스템
        "raid_boss_skill",
        "raid_gimmick",
        "raid_part",
        "raid_phase_transition",
        "raid_minigame",
        "raid_special_action",
        "raid_targeting_rule",
        "raid",
        # 유저 관련 (세션/장비/인벤토리)
        "dungeon_user_pos",
        "skill_equip",
        "user_equipment",
        "user_inventory",
        "user_skill_deck",
        "user_owned_skill",
        "user_collection",
        "user_deck_presets",
        "user_stats",
        "users",
        # 세트 관련
        "set_item_members",
        "set_effects",
        "set_items",
        # 관계 테이블
        "dungeon_spawn",
        "droptable",
        "item_grade_probability",
        # 아이템 하위
        "equipment_item",
        "consume_item",
        # 기본 게임 데이터
        "item",
        "monster",
        "dungeon",
        "skill",
        "grade",
        "equip_pos",
    ]

    for table in tables:
        try:
            await conn.execute_query(f'TRUNCATE TABLE "{table}" CASCADE;')
            print(f"  ✓ {table}")
        except Exception:
            # 테이블이 존재하지 않을 수 있음
            print(f"  - {table} (스킵)")

    print("✓ 모든 테이블 초기화 완료\n")


# ============================================================
# 기본 설정 데이터 (하드코딩)
# ============================================================

async def seed_grades():
    """등급 데이터 삽입"""
    from models.grade import Grade

    grades = [
        Grade(id=1, name="D", description="일반 등급", shop_price=BALANCE_V2.skill_shop_price(1)),
        Grade(id=2, name="C", description="고급 등급", shop_price=BALANCE_V2.skill_shop_price(2)),
        Grade(id=3, name="B", description="희귀 등급", shop_price=BALANCE_V2.skill_shop_price(3)),
        Grade(id=4, name="A", description="영웅 등급", shop_price=BALANCE_V2.skill_shop_price(4)),
        Grade(id=5, name="S", description="전설 등급", shop_price=BALANCE_V2.skill_shop_price(5)),
        Grade(id=6, name="SS", description="고대 등급", shop_price=BALANCE_V2.skill_shop_price(6)),
        Grade(id=7, name="SSS", description="신화 등급", shop_price=BALANCE_V2.skill_shop_price(7)),
        Grade(id=8, name="Mythic", description="창세 등급", shop_price=BALANCE_V2.skill_shop_price(8)),
    ]

    await Grade.bulk_create(grades)
    print(f"✓ Grade {len(grades)}개 삽입 (상점 가격 포함)")


async def seed_equip_pos():
    """장비 위치 데이터 삽입"""
    from models.equip_pos import EquipPos

    positions = [
        EquipPos(id=1, pos_name="투구", description="머리 장비"),
        EquipPos(id=2, pos_name="갑옷", description="상체 장비"),
        EquipPos(id=3, pos_name="신발", description="신발 장비"),
        EquipPos(id=4, pos_name="무기", description="주무기"),
        EquipPos(id=5, pos_name="보조무기", description="보조 장비"),
        EquipPos(id=6, pos_name="장갑", description="손 장비"),
        EquipPos(id=7, pos_name="목걸이", description="목 장비"),
        EquipPos(id=8, pos_name="반지", description="손가락 장비"),
    ]

    await EquipPos.bulk_create(positions)
    print(f"✓ EquipPos {len(positions)}개 삽입")


async def seed_item_grade_probability():
    """상자 등급 확률 데이터 삽입"""
    from models.item_grade_probability import ItemGradeProbability

    probs_data = [
        # 낡은 상자 (cheat_id=1) - 레거시 (사용 안 함)
        {"cheat_id": 1, "grade": "D", "probability": 55, "grade_idx": 1},
        {"cheat_id": 1, "grade": "C", "probability": 25, "grade_idx": 2},
        {"cheat_id": 1, "grade": "B", "probability": 13, "grade_idx": 3},
        {"cheat_id": 1, "grade": "A", "probability": 6, "grade_idx": 4},
        {"cheat_id": 1, "grade": "S", "probability": 1, "grade_idx": 5},
        # 은빛 상자 (cheat_id=2) - 레거시 (사용 안 함)
        {"cheat_id": 2, "grade": "D", "probability": 35, "grade_idx": 1},
        {"cheat_id": 2, "grade": "C", "probability": 30, "grade_idx": 2},
        {"cheat_id": 2, "grade": "B", "probability": 20, "grade_idx": 3},
        {"cheat_id": 2, "grade": "A", "probability": 10, "grade_idx": 4},
        {"cheat_id": 2, "grade": "S", "probability": 5, "grade_idx": 5},
        # 황금 상자 (cheat_id=3) - 레거시 (사용 안 함)
        {"cheat_id": 3, "grade": "D", "probability": 10, "grade_idx": 1},
        {"cheat_id": 3, "grade": "C", "probability": 20, "grade_idx": 2},
        {"cheat_id": 3, "grade": "B", "probability": 30, "grade_idx": 3},
        {"cheat_id": 3, "grade": "A", "probability": 25, "grade_idx": 4},
        {"cheat_id": 3, "grade": "S", "probability": 15, "grade_idx": 5},

        # 혼합 상자 (하급) - cheat_id=4
        {"cheat_id": 4, "grade": "D", "probability": 50, "grade_idx": 1},
        {"cheat_id": 4, "grade": "C", "probability": 30, "grade_idx": 2},
        {"cheat_id": 4, "grade": "B", "probability": 15, "grade_idx": 3},
        {"cheat_id": 4, "grade": "A", "probability": 4, "grade_idx": 4},
        {"cheat_id": 4, "grade": "S", "probability": 1, "grade_idx": 5},

        # 혼합 상자 (중급) - cheat_id=5
        {"cheat_id": 5, "grade": "D", "probability": 30, "grade_idx": 1},
        {"cheat_id": 5, "grade": "C", "probability": 35, "grade_idx": 2},
        {"cheat_id": 5, "grade": "B", "probability": 20, "grade_idx": 3},
        {"cheat_id": 5, "grade": "A", "probability": 10, "grade_idx": 4},
        {"cheat_id": 5, "grade": "S", "probability": 5, "grade_idx": 5},

        # 혼합 상자 (상급) - cheat_id=6
        {"cheat_id": 6, "grade": "D", "probability": 15, "grade_idx": 1},
        {"cheat_id": 6, "grade": "C", "probability": 25, "grade_idx": 2},
        {"cheat_id": 6, "grade": "B", "probability": 30, "grade_idx": 3},
        {"cheat_id": 6, "grade": "A", "probability": 20, "grade_idx": 4},
        {"cheat_id": 6, "grade": "S", "probability": 10, "grade_idx": 5},

        # 혼합 상자 (최상급) - cheat_id=7
        {"cheat_id": 7, "grade": "D", "probability": 5, "grade_idx": 1},
        {"cheat_id": 7, "grade": "C", "probability": 15, "grade_idx": 2},
        {"cheat_id": 7, "grade": "B", "probability": 30, "grade_idx": 3},
        {"cheat_id": 7, "grade": "A", "probability": 30, "grade_idx": 4},
        {"cheat_id": 7, "grade": "S", "probability": 20, "grade_idx": 5},

        # 럭키 박스 - cheat_id=8
        {"cheat_id": 8, "grade": "D", "probability": 5, "grade_idx": 1},
        {"cheat_id": 8, "grade": "C", "probability": 10, "grade_idx": 2},
        {"cheat_id": 8, "grade": "B", "probability": 25, "grade_idx": 3},
        {"cheat_id": 8, "grade": "A", "probability": 35, "grade_idx": 4},
        {"cheat_id": 8, "grade": "S", "probability": 25, "grade_idx": 5},

        # 신비한 상자 - cheat_id=9
        {"cheat_id": 9, "grade": "B", "probability": 30, "grade_idx": 3},
        {"cheat_id": 9, "grade": "A", "probability": 40, "grade_idx": 4},
        {"cheat_id": 9, "grade": "S", "probability": 30, "grade_idx": 5},
    ]

    probs = [ItemGradeProbability(**entry) for entry in probs_data]
    await ItemGradeProbability.bulk_create(probs)
    print(f"✓ ItemGradeProbability {len(probs)}개 삽입")


# ============================================================
# CSV 기반 시드
# ============================================================

async def seed_skills():
    """스킬 데이터 삽입 (data/skills.csv)"""
    from models.skill import Skill_Model

    rows = read_csv("skills.csv")
    skills = []

    for row in rows:
        config = json.loads(row["config"])
        grade = parse_grade(row.get("등급", ""))

        # 플레이어_획득가능 파싱 (Y/N -> bool)
        obtainable_str = row.get("플레이어_획득가능", "Y").strip().upper()
        player_obtainable = (obtainable_str == "Y")

        skills.append(Skill_Model(
            id=int(row["ID"]),
            name=row["이름"],
            description=row["효과"],
            config=config,
            grade=grade,
            attribute=row.get("속성", "무속성") or "무속성",
            keyword=row.get("키워드", ""),
            player_obtainable=player_obtainable,
            acquisition_source=row.get("획득처", "").strip(),
        ))

    await Skill_Model.bulk_create(skills)
    print(f"✓ Skill {len(skills)}개 삽입 (skills.csv, 플레이어 획득가능 포함)")


async def seed_dungeons():
    """던전 데이터 삽입 (data/dungeons.csv)"""
    from models.dungeon import Dungeon

    rows = read_csv("dungeons.csv")
    dungeons = []

    for row in rows:
        level = parse_level(row.get("권장 레벨", "1"))

        dungeons.append(Dungeon(
            id=int(row["ID"]),
            name=row["이름"],
            require_level=level,
            description=row.get("설명", ""),
        ))

    await Dungeon.bulk_create(dungeons)
    print(f"✓ Dungeon {len(dungeons)}개 삽입 (dungeons.csv)")


async def seed_monsters():
    """몬스터 데이터 삽입 (data/monsters.csv)"""
    from models.monster import Monster

    rows = read_csv("monsters.csv")
    monsters = []

    for row in rows:
        # 이름에서 영문명 제거: "슬라임 (Slime)" → "슬라임"
        name = row["이름"]
        paren_idx = name.find("(")
        if paren_idx > 0:
            name = name[:paren_idx].strip()

        monster_type = row.get("타입", "CommonMob")

        # skill_ids 파싱 (JSON 배열)
        skill_ids = json.loads(row.get("skill_ids", "[]"))

        # drop_skill_ids 파싱 (JSON 배열)
        drop_skill_ids = json.loads(row.get("drop_skill_ids", "[]"))

        # group_ids 파싱 (쉼표 구분 -> 정수 리스트)
        group_str = row.get("그룹", "").strip()
        if group_str:
            group_ids = [int(x.strip()) for x in group_str.split(",") if x.strip()]
        else:
            group_ids = []

        monsters.append(Monster(
            id=int(row["ID"]),
            name=name,
            description=row.get("설명", "") or "",
            type=monster_type,
            hp=safe_int(row.get("HP", "0")),
            attack=safe_int(row.get("Attack", "0")),
            ap_attack=safe_int(row.get("AP_Attack", "0")),
            defense=safe_int(row.get("Defense", "0")),
            ap_defense=safe_int(row.get("AP_Defense", "0")),
            accuracy=safe_int(row.get("Accuracy", "95"), 95),
            evasion=safe_int(row.get("Evasion", "5"), 5),
            speed=safe_int(row.get("Speed", "100"), 100),
            attribute=row.get("속성", "무속성") or "무속성",
            skill_ids=skill_ids,
            drop_skill_ids=drop_skill_ids,
            phase_config=json.loads(row.get("phase_config") or "{}"),
            action_profile=json.loads(row.get("action_profile") or "{}"),
            group_ids=group_ids,
        ))

    await Monster.bulk_create(monsters)
    print(f"✓ Monster {len(monsters)}개 삽입 (monsters.csv, skill_ids/group_ids 포함)")


async def seed_equipment_items():
    """장비 아이템 삽입 (data/items_equipment.csv, items_special.csv 포함)"""
    from models.item import Item
    from models.equipment_item import EquipmentItem
    from resources.item_emoji import ItemType
    from config import BALANCE_V2

    rows = read_csv("items_equipment.csv")
    items = []
    equipments = []

    for row in rows:
        item_id = int(row["ID"])
        slot = row.get("슬롯", "")
        equip_pos = SLOT_TO_EQUIP_POS.get(slot)
        require_level = parse_level(row.get("Lv", "1"))
        budget_slot = {
            1: "helmet", 2: "armor", 3: "boots", 4: "weapon",
            5: "sub_weapon", 6: "gloves", 7: "necklace", 8: "ring1",
        }.get(equip_pos, "weapon")
        purchase_price = BALANCE_V2.equipment_purchase_price(require_level, budget_slot)

        items.append(Item(
            id=item_id,
            name=row["이름"],
            description=row.get("description", "") or row.get("특수 효과", "") or "",
            cost=purchase_price,
            type=ItemType.EQUIP,
        ))

        # config 파싱
        config_str = row.get("config", "").strip()
        config = json.loads(config_str) if config_str else None

        equipments.append(EquipmentItem(
            item_id=item_id,
            attack=nullable_int(row.get("Attack", "")),
            ap_attack=nullable_int(row.get("AP_Attack", "")),
            hp=nullable_int(row.get("HP", "")),
            ad_defense=nullable_int(row.get("AD_Def", "")),
            ap_defense=nullable_int(row.get("AP_Def", "")),
            speed=nullable_int(row.get("Speed", "")),
            equip_pos=equip_pos,
            require_level=require_level,
            require_str=safe_int(row.get("Req_STR", "0")),
            require_int=safe_int(row.get("Req_INT", "0")),
            require_dex=safe_int(row.get("Req_DEX", "0")),
            require_vit=safe_int(row.get("Req_VIT", "0")),
            require_luk=safe_int(row.get("Req_LUK", "0")),
            config=config,
            acquisition_source=row.get("획득처", "").strip(),
            set_key=row.get("set_key", "").strip(),
        ))

    await Item.bulk_create(items)
    await EquipmentItem.bulk_create(equipments)
    print(f"✓ 장비 아이템 {len(items)}개 삽입 (items_equipment.csv)")


async def seed_consumable_items():
    """소비 아이템 삽입 (data/items_consumable.csv)"""
    from models.item import Item
    from models.consume_item import ConsumeItem
    from resources.item_emoji import ItemType

    rows = read_csv("items_consumable.csv")
    items = []
    consumables = []

    for row in rows:
        effect = row.get("효과", "")
        amount = parse_hp_amount(effect)
        cost = safe_int(row.get("가격", "0"))
        item_id = int(row["ID"])

        items.append(Item(
            id=item_id,
            name=row["이름"],
            description=effect,
            cost=cost,
            type=ItemType.CONSUME,
        ))

        consumables.append(ConsumeItem(
            item_id=item_id,
            amount=amount
        ))

    await Item.bulk_create(items)
    await ConsumeItem.bulk_create(consumables)
    print(f"✓ 소비 아이템 {len(items)}개 삽입 (items_consumable.csv)")


async def seed_enhancement_items():
    """강화 아이템 삽입 (data/items_enhancement.csv)"""
    from models.item import Item
    from models.consume_item import ConsumeItem
    from resources.item_emoji import ItemType

    rows = read_csv("items_enhancement.csv")
    items = []
    consumables = []

    for row in rows:
        # 획득처에서 가격 추출: "상점 (200)" → 200
        source = row.get("획득처", "")
        cost_match = re.search(r"\((\d+)\)", source)
        cost = int(cost_match.group(1)) if cost_match else 0
        item_id = int(row["ID"])

        items.append(Item(
            id=item_id,
            name=row["이름"],
            description=row.get("효과", ""),
            cost=cost,
            type=ItemType.CONSUME,
        ))

        consumables.append(ConsumeItem(
            item_id=item_id,
            amount=0
        ))

    await Item.bulk_create(items)
    await ConsumeItem.bulk_create(consumables)
    print(f"✓ 강화 아이템 {len(items)}개 삽입 (items_enhancement.csv)")


async def seed_material_items():
    """재료 아이템 삽입 (data/items_material.csv)"""
    from models.item import Item
    from resources.item_emoji import ItemType

    rows = read_csv("items_material.csv")
    items = []

    for row in rows:
        items.append(Item(
            id=int(row["ID"]),
            name=row["이름"],
            description=row.get("설명", "") or row.get("용도", ""),
            cost=0,
            type=ItemType.ETC,
        ))

    await Item.bulk_create(items)
    print(f"✓ 재료 아이템 {len(items)}개 삽입 (items_material.csv)")


async def seed_dungeon_spawns():
    """던전 스폰 데이터 삽입 (monsters.csv 기반 자동 생성)"""
    from models.dungeon import Dungeon
    from models.dungeon_spawn import DungeonSpawn

    # 던전 이름 → ID 매핑
    dungeons = await Dungeon.all()
    dungeon_map = {d.name: d.id for d in dungeons}

    rows = read_csv("monsters.csv")

    # 던전별 몬스터 그룹핑
    dungeon_monsters: dict[int, list[int]] = {}

    for row in rows:
        dungeon_name = row.get("던전", "").strip()
        if not dungeon_name:
            continue

        # 별칭 보정
        dungeon_name = DUNGEON_NAME_ALIAS.get(dungeon_name, dungeon_name)
        if dungeon_name is None:
            continue

        dungeon_id = dungeon_map.get(dungeon_name)
        if dungeon_id is None:
            print(f"  ⚠ 던전 매핑 실패: '{row.get('던전', '')}' (몬스터: {row['이름']})")
            continue

        monster_id = int(row["ID"])
        dungeon_monsters.setdefault(dungeon_id, []).append(monster_id)

    spawns = []
    for dungeon_id, monsters in dungeon_monsters.items():
        bosses = [m for m in monsters if m >= 101]
        mobs = [m for m in monsters if m < 101]

        for monster_id in monsters:
            if monster_id >= 101:
                # 보스: 10% 고정
                prob = 0.10
            elif bosses:
                # 일반 몹: 나머지 90% 균등 배분
                prob = 0.90 / len(mobs) if mobs else 1.0
            else:
                # 보스 없는 던전: 100% 균등 배분
                prob = 1.0 / len(monsters)

            spawns.append(DungeonSpawn(
                dungeon_id=dungeon_id,
                monster_id=monster_id,
                prob=round(prob, 4),
            ))

    await DungeonSpawn.bulk_create(spawns)
    print(f"✓ DungeonSpawn {len(spawns)}개 삽입 (monsters.csv 기반)")


async def seed_droptable():
    """드롭테이블 데이터 삽입 (data/droptable.csv)"""
    from models.droptable import Droptable

    rows = read_csv("droptable.csv")
    droptables = []

    for row in rows:
        droptables.append(Droptable(
            id=int(row["id"]),
            drop_monster=nullable_int(row.get("drop_monster")),
            probability=safe_float(row.get("probability")),
            item_id=nullable_int(row.get("item_id")),
        ))

    await Droptable.bulk_create(droptables)
    print(f"✓ Droptable {len(droptables)}개 삽입 (droptable.csv)")


async def seed_sets():
    """세트 정의 + 구성원 + 효과 삽입 (set_effects.csv + items_equipment.csv)"""
    from models.set_item import SetItem, SetItemMember, SetEffect
    from models.equipment_item import EquipmentItem

    # 1) set_effects.csv에서 고유 세트 추출 → SetItem 생성
    rows = read_csv("set_effects.csv")
    seen_sets: dict[str, int] = {}  # name → auto ID
    next_id = 1
    set_items = []

    for row in rows:
        name = row["세트이름"]
        if name not in seen_sets:
            set_items.append(SetItem(
                id=next_id,
                name=name,
                description=row.get("설명", ""),
            ))
            seen_sets[name] = next_id
            next_id += 1

    await SetItem.bulk_create(set_items)
    print(f"  SetItem {len(set_items)}개 삽입")

    # 2) items_equipment.csv '세트' 컬럼 → SetItemMember 생성
    equip_items = await EquipmentItem.all()
    item_fk_to_pk = {ei.item_id: ei.id for ei in equip_items}

    equip_rows = read_csv("items_equipment.csv")
    members = []

    for row in equip_rows:
        set_name = row.get("set_key", "").strip()
        if not set_name:
            continue
        set_id = seen_sets.get(set_name)
        if set_id is None:
            continue

        item_id = int(row["ID"])
        equip_pk = item_fk_to_pk.get(item_id)
        if equip_pk is None:
            continue

        members.append(SetItemMember(
            set_item_id=set_id,
            equipment_item_id=equip_pk,
        ))

    await SetItemMember.bulk_create(members)
    print(f"  SetItemMember {len(members)}개 삽입")

    # 3) set_effects.csv → SetEffect 생성
    effects = []
    for row in rows:
        set_id = seen_sets[row["세트이름"]]
        effect_config = json.loads(row["효과config"])

        effects.append(SetEffect(
            set_item_id=set_id,
            pieces_required=int(row["필요수"]),
            effect_description=row["효과설명"],
            effect_config=effect_config,
        ))

    await SetEffect.bulk_create(effects)
    print(f"  SetEffect {len(effects)}개 삽입")
    print(f"✓ 세트 데이터 삽입 완료 (set_effects.csv)")


async def seed_raids():
    """레이드 데이터 삽입 (raid_*.csv)"""
    from models.raid import (
        Raid,
        RaidTargetingRule,
        RaidSpecialAction,
        RaidMinigame,
        RaidPhaseTransition,
        RaidPart,
        RaidGimmick,
        RaidBossSkill,
    )

    # raids.csv
    raid_rows = read_csv("raids.csv")
    raids = []
    for row in raid_rows:
        raids.append(Raid(
            raid_id=safe_int(row["raid_id"]),
            dungeon_id=safe_int(row["dungeon_id"]),
            raid_key=row["raid_key"],
            raid_name=row["raid_name"],
            recommended_level=safe_int(row["recommended_level"], 1),
            max_party_size=safe_int(row["max_party_size"], 3),
            boss_code=row["boss_code"],
            boss_name=row["boss_name"],
            main_attribute=row.get("main_attribute", "all"),
            phase_count=safe_int(row.get("phase_count", "3"), 3),
            phase_hp_triggers=row.get("phase_hp_triggers", "70|35"),
            enrage_turn_limit=safe_int(row.get("enrage_turn_limit", "20"), 20),
            default_priority_1=row.get("default_priority_1", "body"),
            default_priority_2=row.get("default_priority_2", "body"),
            default_priority_3=row.get("default_priority_3", "body"),
            notes=row.get("notes", ""),
        ))
    await Raid.bulk_create(raids)
    print(f"  Raid {len(raids)}개 삽입")

    # raid_targeting_rules.csv
    targeting_rows = read_csv("raid_targeting_rules.csv")
    targeting_rules = []
    for row in targeting_rows:
        targeting_rules.append(RaidTargetingRule(
            raid_id=safe_int(row["raid_id"]),
            dropbox_enabled=safe_bool(row.get("dropbox_enabled", "true"), True),
            apply_delay_turns=safe_int(row.get("apply_delay_turns", "1"), 1),
            team_priority_slots=safe_int(row.get("team_priority_slots", "3"), 3),
            personal_override_enabled=safe_bool(row.get("personal_override_enabled", "true"), True),
            personal_override_slots=safe_int(row.get("personal_override_slots", "1"), 1),
            persist_selection=safe_bool(row.get("persist_selection", "true"), True),
            single_target_rule=row.get("single_target_rule", "selected_priority_first"),
            aoe_target_rule=row.get("aoe_target_rule", "body_plus_active_parts"),
            destroyed_part_fallback=row.get("destroyed_part_fallback", "next_valid_priority"),
            notes=row.get("notes", ""),
        ))
    await RaidTargetingRule.bulk_create(targeting_rules)
    print(f"  RaidTargetingRule {len(targeting_rules)}개 삽입")

    # raid_special_actions.csv
    action_rows = read_csv("raid_special_actions.csv")
    actions = []
    for row in action_rows:
        actions.append(RaidSpecialAction(
            action_key=row["action_key"],
            action_name=row["action_name"],
            cooldown_rounds=safe_int(row.get("cooldown_rounds", "0"), 0),
            max_uses_per_round=safe_int(row.get("max_uses_per_round", "1"), 1),
            target_type=row.get("target_type", "boss"),
            effect_type=row.get("effect_type", "none"),
            base_value=safe_int(row.get("base_value", "0"), 0),
            scaling_stat=row.get("scaling_stat", "none"),
            description=row.get("description", ""),
        ))
    await RaidSpecialAction.bulk_create(actions)
    print(f"  RaidSpecialAction {len(actions)}개 삽입")

    # raid_minigames.csv
    minigame_rows = read_csv("raid_minigames.csv")
    minigames = []
    for row in minigame_rows:
        minigames.append(RaidMinigame(
            minigame_id=safe_int(row["minigame_id"]),
            raid_id=safe_int(row["raid_id"]),
            minigame_key=row["minigame_key"],
            minigame_name=row["minigame_name"],
            minigame_type=row["minigame_type"],
            time_limit_sec=safe_int(row.get("time_limit_sec", "20"), 20),
            input_count=safe_int(row.get("input_count", "3"), 3),
            success_effect=row.get("success_effect", "none"),
            fail_effect=row.get("fail_effect", "none"),
        ))
    await RaidMinigame.bulk_create(minigames)
    print(f"  RaidMinigame {len(minigames)}개 삽입")

    # raid_phase_transitions.csv
    transition_rows = read_csv("raid_phase_transitions.csv")
    transitions = []
    for row in transition_rows:
        transitions.append(RaidPhaseTransition(
            transition_id=safe_int(row["transition_id"]),
            raid_id=safe_int(row["raid_id"]),
            from_phase=safe_int(row.get("from_phase", "1"), 1),
            to_phase=safe_int(row.get("to_phase", "2"), 2),
            trigger_type=row.get("trigger_type", "hp_lte"),
            trigger_value=row.get("trigger_value", "70"),
            minigame_id=safe_int(row.get("minigame_id", "0"), 0),
            success_buff_key=row.get("success_buff_key", "none"),
            fail_penalty_key=row.get("fail_penalty_key", "none"),
        ))
    await RaidPhaseTransition.bulk_create(transitions)
    print(f"  RaidPhaseTransition {len(transitions)}개 삽입")

    # raid_parts.csv
    part_rows = read_csv("raid_parts.csv")
    parts = []
    for row in part_rows:
        parts.append(RaidPart(
            part_id=safe_int(row["part_id"]),
            raid_id=safe_int(row["raid_id"]),
            part_key=row["part_key"],
            part_name=row["part_name"],
            max_hp_ratio=safe_float(row.get("max_hp_ratio", "0.2"), 0.2),
            defense_multiplier=safe_float(row.get("defense_multiplier", "1.0"), 1.0),
            targetable_from_turn=safe_int(row.get("targetable_from_turn", "1"), 1),
            destructible=safe_bool(row.get("destructible", "true"), True),
            on_destroy_effect=row.get("on_destroy_effect", "none"),
            on_destroy_value=safe_float(row.get("on_destroy_value", "0"), 0.0),
            disabled_boss_skill_keys=row.get("disabled_boss_skill_keys", None) or None,
            skill_lock_duration_turns=safe_int(row.get("skill_lock_duration_turns", "-1"), -1),
            priority_hint=row.get("priority_hint", "mid"),
        ))
    await RaidPart.bulk_create(parts)
    print(f"  RaidPart {len(parts)}개 삽입")

    # raid_gimmicks.csv
    gimmick_rows = read_csv("raid_gimmicks.csv")
    gimmicks = []
    for row in gimmick_rows:
        gimmicks.append(RaidGimmick(
            gimmick_id=safe_int(row["gimmick_id"]),
            raid_id=safe_int(row["raid_id"]),
            phase=safe_int(row.get("phase", "1"), 1),
            gimmick_key=row["gimmick_key"],
            gimmick_name=row["gimmick_name"],
            trigger_type=row.get("trigger_type", "interval_turn"),
            trigger_value=row.get("trigger_value", "0"),
            duration_turns=safe_int(row.get("duration_turns", "0"), 0),
            target_scope=row.get("target_scope", "boss"),
            success_condition_type=row.get("success_condition_type", "none"),
            success_condition_value=row.get("success_condition_value", ""),
            success_effect=row.get("success_effect", "none"),
            fail_effect=row.get("fail_effect", "none"),
            cooldown_turns=safe_int(row.get("cooldown_turns", "0"), 0),
        ))
    await RaidGimmick.bulk_create(gimmicks)
    print(f"  RaidGimmick {len(gimmicks)}개 삽입")

    # raid_boss_skills.csv (CSV에는 PK가 없어서 순차 ID 생성)
    boss_skill_rows = read_csv("raid_boss_skills.csv")
    boss_skills = []
    for idx, row in enumerate(boss_skill_rows, start=1):
        boss_skills.append(RaidBossSkill(
            id=idx,
            raid_id=safe_int(row["raid_id"]),
            skill_key=row["skill_key"],
            skill_name=row["skill_name"],
            skill_id=nullable_int(row.get("skill_id", "")),
            phase=safe_int(row.get("phase", "1"), 1),
            removable_by_part=safe_bool(row.get("removable_by_part", "false"), False),
            remove_source_part_key=row.get("remove_source_part_key", None) or None,
            notes=row.get("notes", ""),
        ))
    await RaidBossSkill.bulk_create(boss_skills)
    print(f"  RaidBossSkill {len(boss_skills)}개 삽입")

    print("✓ 레이드 데이터 삽입 완료 (raid_*.csv)")


# ============================================================
# 메인
# ============================================================

async def main(*, fresh=False):
    if not fresh:
        raise RuntimeError("Fresh installation only: pass --fresh. Existing databases must use scripts/update_beginner_static.py")
    print("=" * 60)
    print("CUHABot 데이터베이스 초기화 및 CSV 시드")
    print("=" * 60)

    await init_db()

    # Refuse to touch populated databases. Normal updates never truncate or
    # delete static definitions (their cascading FKs contain user progress).
    from models import User, Skill_Model, Item, Monster, Dungeon
    for model in (User, Skill_Model, Item, Monster, Dungeon):
        if await model.all().exists():
            await Tortoise.close_connections()
            raise RuntimeError("Database is not empty; fresh installation refused")

    # 2. 기본 설정 데이터
    print("[2/3] 기본 설정 데이터 삽입")
    await seed_grades()
    await seed_equip_pos()
    await seed_item_grade_probability()

    # 3. CSV 게임 데이터
    print("\n[3/5] CSV 게임 데이터 삽입")
    await seed_skills()
    await seed_dungeons()
    await seed_monsters()
    await seed_equipment_items()
    await seed_consumable_items()
    await seed_enhancement_items()
    await seed_material_items()
    await seed_dungeon_spawns()

    # 4. 드롭 테이블
    print("\n[4/5] 드롭 테이블 데이터 삽입")
    await seed_droptable()

    # 5. 세트 데이터 (장비 데이터 의존)
    print("\n[5/5] 세트 아이템 데이터 삽입")
    await seed_sets()

    # 6. 레이드 데이터
    print("\n[6/6] 레이드 데이터 삽입")
    await seed_raids()

    await Tortoise.close_connections()

    print("\n" + "=" * 60)
    print("데이터베이스 초기화 및 시드 완료!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main(fresh="--fresh" in sys.argv))
