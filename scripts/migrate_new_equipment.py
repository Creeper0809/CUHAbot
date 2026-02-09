"""
새로운 장비 아이템 마이그레이션 (ID 5001-5108)

기존 DB 데이터를 유지하면서 새 장비만 추가합니다.
실행: python scripts/migrate_new_equipment.py
"""
import asyncio
import csv
import json
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv
from tortoise import Tortoise

load_dotenv()

DATA_DIR = os.path.join(PROJECT_ROOT, "data")

SLOT_TO_EQUIP_POS = {
    "검": 4, "도끼": 4, "지팡이": 4, "활": 4, "무기": 4,
    "투구": 1,
    "갑옷": 2, "방어구": 2, "로브": 2,
    "신발": 3,
    "방패": 5, "오브": 5,
    "장갑": 6, "건틀릿": 6,
    "목걸이": 7,
    "반지": 8,
    "벨트": 9, "장신구": 9, "악세서리": 9,
    "망토": 10,
}


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


def nullable_int(value: str) -> int | None:
    """빈 문자열이면 None, 아니면 int 반환"""
    if not value or not value.strip():
        return None
    return safe_int(value)


def parse_level(level_str: str) -> int:
    """레벨 문자열에서 최소 레벨 추출"""
    if not level_str or not level_str.strip():
        return 1
    level_str = level_str.strip()
    if "-" in level_str:
        return int(level_str.split("-")[0])
    if "+" in level_str:
        return int(level_str.replace("+", ""))
    return int(level_str)


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


async def migrate_new_equipment():
    """새로운 장비 아이템 추가 (ID 5001-5108)"""
    from models.item import Item
    from models.equipment_item import EquipmentItem
    from resources.item_emoji import ItemType

    print("=" * 60)
    print("새로운 장비 아이템 마이그레이션 시작")
    print("=" * 60)

    # CSV에서 ID 5001-5108 읽기
    rows = read_csv("items_equipment.csv")
    new_rows = [row for row in rows if 5001 <= int(row["ID"]) <= 5108]

    if not new_rows:
        print("✓ 추가할 새 장비가 없습니다.")
        return

    print(f"\n추가할 장비: {len(new_rows)}개")

    items = []
    equipments = []

    for row in new_rows:
        item_id = int(row["ID"])
        slot = row.get("슬롯", "")
        equip_pos = SLOT_TO_EQUIP_POS.get(slot)

        if equip_pos is None:
            print(f"⚠️  경고: ID {item_id} - 알 수 없는 슬롯 '{slot}', 기본값 9 사용")
            equip_pos = 9  # 장신구

        require_level = parse_level(row.get("Lv", "1"))

        # Item 엔트리
        items.append(Item(
            id=item_id,
            name=row["이름"],
            description=row.get("특수 효과", "") or "",
            cost=0,
            type=ItemType.EQUIP,
        ))

        # config 파싱
        config_str = row.get("config") or ""
        if config_str:
            config_str = config_str.strip()

        config = None
        if config_str:
            try:
                config = json.loads(config_str)
            except json.JSONDecodeError as e:
                print(f"⚠️  경고: ID {item_id} ({row['이름']}) - JSON 파싱 실패: {e}")
                print(f"     config_str: {config_str[:100]}")
                config = None

        # EquipmentItem 엔트리
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
        ))

    # 기존 아이템 확인 및 삭제
    existing_ids = [item_id for item_id in range(5001, 5109)]
    deleted_items = await Item.filter(id__in=existing_ids).delete()
    if deleted_items:
        print(f"✓ 기존 데이터 {deleted_items}개 삭제 (재삽입 준비)")

    # 삽입
    await Item.bulk_create(items)
    await EquipmentItem.bulk_create(equipments)

    print(f"✓ 새 장비 아이템 {len(items)}개 삽입 완료!")
    print("\n추가된 장비 목록:")
    for item in items[:10]:  # 처음 10개만 표시
        print(f"  - [{item.id}] {item.name}")
    if len(items) > 10:
        print(f"  ... 외 {len(items) - 10}개")

    print("\n" + "=" * 60)
    print("마이그레이션 완료!")
    print("=" * 60)


async def main():
    await init_db()
    try:
        await migrate_new_equipment()
    finally:
        await Tortoise.close_connections()


if __name__ == "__main__":
    asyncio.run(main())
