"""
던전 레벨 구간별 상점 장비 자동 생성 스크립트

각 던전 레벨 구간마다 최소 5개의 상점 장비가 있도록 자동 생성합니다.
실행: python scripts/generate_shop_equipment.py
"""
import asyncio
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from tortoise import Tortoise
from models import Item, EquipmentItem, Dungeon
from models.repos.static_cache import load_static_data, get_previous_dungeon_level
from resources.item_emoji import ItemType

load_dotenv()


# 장비 타입 매핑 (equip_pos ID)
EQUIP_POS = {
    "투구": 1,
    "갑옷": 2,
    "신발": 3,
    "무기": 4,
    "장갑": 6,
    "목걸이": 7,
    "반지": 8,
}

# 레벨 구간별 장비 템플릿
EQUIPMENT_TEMPLATES = [
    # 각 레벨 구간마다 5개의 장비 타입
    {"name": "강화 투구", "pos": "투구", "hp_mult": 20, "ad_def_mult": 5, "ap_def_mult": 5},
    {"name": "강화 갑옷", "pos": "갑옷", "hp_mult": 40, "ad_def_mult": 10, "ap_def_mult": 8},
    {"name": "강화 장갑", "pos": "장갑", "attack_mult": 2, "ad_def_mult": 2},
    {"name": "전투 반지", "pos": "반지", "attack_mult": 3},
    {"name": "방어 목걸이", "pos": "목걸이", "ad_def_mult": 5, "ap_def_mult": 5},
]


def get_equipment_description(pos_name: str, level: int) -> str:
    """레벨과 장비 타입에 따른 설명 생성"""

    # 레벨 구간별 수식어
    if level < 20:
        tier = "초보자용"
        quality = "간단한"
    elif level < 40:
        tier = "모험가용"
        quality = "튼튼한"
    elif level < 60:
        tier = "숙련자용"
        quality = "강화된"
    elif level < 80:
        tier = "전문가용"
        quality = "정교한"
    else:
        tier = "달인용"
        quality = "최상급"

    descriptions = {
        "투구": [
            f"{tier} 투구. {quality} 재질로 머리를 보호한다.",
            f"{quality} 투구. 전투에 적합하게 제작되었다.",
            f"상점에서 판매하는 {quality} 투구. 기본에 충실한 디자인이다.",
        ],
        "갑옷": [
            f"{tier} 갑옷. {quality} 철판으로 만들어졌다.",
            f"{quality} 갑옷. 적당한 방어력과 내구성을 제공한다.",
            f"상점에서 구입 가능한 {quality} 갑옷. 실전에서 검증되었다.",
        ],
        "장갑": [
            f"{tier} 장갑. 공격력과 방어력을 동시에 높여준다.",
            f"{quality} 장갑. 손을 보호하면서도 공격이 자유롭다.",
            f"상점 판매용 {quality} 장갑. 전투에 유용하다.",
        ],
        "반지": [
            f"{tier} 반지. 공격력을 증가시키는 마법이 깃들어 있다.",
            f"{quality} 반지. 착용자의 전투력을 높여준다.",
            f"상점에서 구매 가능한 {quality} 반지. 공격 능력 향상에 도움이 된다.",
        ],
        "목걸이": [
            f"{tier} 목걸이. 방어력을 높여주는 마법 부여가 되어있다.",
            f"{quality} 목걸이. 착용자를 보호하는 힘을 지녔다.",
            f"상점 판매용 {quality} 목걸이. 방어에 특화되어 있다.",
        ],
    }

    import random
    return random.choice(descriptions.get(pos_name, [f"{tier} 장비."]))


async def init_db():
    await Tortoise.init(
        db_url=f"postgres://{os.getenv('DATABASE_USER')}:{os.getenv('DATABASE_PASSWORD')}@"
               f"{os.getenv('DATABASE_URL')}:{os.getenv('DATABASE_PORT')}/{os.getenv('DATABASE_TABLE')}",
        modules={"models": ["models"]}
    )


async def generate_equipment():
    await init_db()
    await load_static_data()

    # 던전 레벨 목록 (중복 제거)
    dungeons = await Dungeon.all().order_by('require_level')
    checked_levels = set()
    level_ranges = []

    for dungeon in dungeons:
        level = dungeon.require_level
        if level in checked_levels:
            continue
        checked_levels.add(level)

        prev_level = get_previous_dungeon_level(level)
        count = await EquipmentItem.filter(
            require_level__gte=prev_level,
            require_level__lte=level,
            acquisition_source='상점',
        ).count()

        if count < 5:
            level_ranges.append((level, prev_level, count))

    print(f"부족한 레벨 구간: {len(level_ranges)}개")

    # 최대 Item ID 조회
    max_item = await Item.all().order_by('-id').first()
    next_id = (max_item.id if max_item else 8962) + 1

    added_items = []

    for level, prev_level, current_count in level_ranges:
        needed = 5 - current_count
        if needed <= 0:
            continue

        print(f"\nLv {level} [{prev_level}-{level}] - {current_count}개 → {needed}개 추가 필요")

        # 중간 레벨 선택 (구간 중간)
        target_level = (prev_level + level) // 2 + 1

        for i in range(needed):
            template = EQUIPMENT_TEMPLATES[i % len(EQUIPMENT_TEMPLATES)]

            item_name = f"{template['name']} Lv{target_level}"
            cost = 100 + target_level * 10
            description = get_equipment_description(template["pos"], target_level)

            # 스탯 계산
            attack = template.get("attack_mult", 0) * target_level if template.get("attack_mult") else 0
            hp = template.get("hp_mult", 0) * target_level if template.get("hp_mult") else 0
            ad_def = template.get("ad_def_mult", 0) * target_level if template.get("ad_def_mult") else 0
            ap_def = template.get("ap_def_mult", 0) * target_level if template.get("ap_def_mult") else 0

            item_data = {
                "id": next_id,
                "name": item_name,
                "description": description,
                "cost": cost,
                "type": ItemType.EQUIP,
                "equip_pos": EQUIP_POS[template["pos"]],
                "require_level": target_level,
                "attack": attack,
                "hp": hp,
                "ad_defense": ad_def,
                "ap_defense": ap_def,
                "acquisition_source": "상점",
                "pos_name": template["pos"],
            }

            # Create Item
            item = await Item.create(
                id=item_data["id"],
                name=item_data["name"],
                description=item_data["description"],
                cost=item_data["cost"],
                type=item_data["type"],
            )

            # Create EquipmentItem
            equip_data = {
                "item_id": item.id,
                "equip_pos": item_data["equip_pos"],
                "require_level": item_data["require_level"],
                "attack": item_data["attack"],
                "hp": item_data["hp"],
                "ad_defense": item_data["ad_defense"],
                "ap_defense": item_data["ap_defense"],
                "acquisition_source": item_data["acquisition_source"],
            }

            await EquipmentItem.create(**equip_data)
            added_items.append((next_id, item_name, target_level, template["pos"], attack, hp, ad_def, ap_def, description))
            print(f"  추가: {item_name} (ID: {next_id})")
            next_id += 1

    print(f"\n총 {len(added_items)}개 아이템 추가 완료")

    # CSV에도 추가
    csv_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data", "items_equipment.csv"
    )

    with open(csv_path, "a", encoding="utf-8") as f:
        # CSV 컬럼: ID,이름,슬롯,계열,Lv,Req_STR,Req_INT,Req_DEX,Req_VIT,Req_LUK,Attack,AP_Attack,HP,AD_Def,AP_Def,Speed,특수 효과,세트,획득처,description,config
        for item_id, item_name, level, pos_name, attack, hp, ad_def, ap_def, desc in added_items:
            # 공격력과 HP는 정수로, 0이면 빈 문자열
            attack_str = str(int(attack)) if attack > 0 else ""
            hp_str = str(int(hp)) if hp > 0 else ""
            ad_def_str = str(int(ad_def)) if ad_def > 0 else ""
            ap_def_str = str(int(ap_def)) if ap_def > 0 else ""

            # ID,이름,슬롯,계열,Lv,Req_STR,Req_INT,Req_DEX,Req_VIT,Req_LUK,Attack,AP_Attack,HP,AD_Def,AP_Def,Speed,특수 효과,세트,획득처,description,config
            f.write(f"{item_id},{item_name},{pos_name},범용,{level},,,,,,{attack_str},,{hp_str},{ad_def_str},{ap_def_str},,,,,상점,{desc},\n")

    print(f"\nCSV 업데이트 완료: {csv_path}")

    await Tortoise.close_connections()


if __name__ == "__main__":
    asyncio.run(generate_equipment())
