"""
몬스터 데이터 시드 스크립트

data/monsters.csv에서 몬스터 데이터를 읽어 데이터베이스에 추가합니다.

실행: python scripts/seed_monsters.py
"""
import asyncio
import csv
import json
import os
import sys

# 프로젝트 루트를 path에 추가
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv
from tortoise import Tortoise

load_dotenv()

CSV_PATH = os.path.join(PROJECT_ROOT, "data", "monsters.csv")

MONSTER_FIELDS = [
    "name", "description", "type", "hp", "attack",
    "defense", "speed", "attribute", "skill_ids", "group_ids",
]


def load_monsters_from_csv() -> list[dict]:
    """CSV 파일에서 몬스터 데이터 로드"""
    monsters = []
    with open(CSV_PATH, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            skill_ids = json.loads(row.get("skill_ids", "[]"))

            group_str = row.get("그룹", "").strip()
            if group_str:
                group_ids = [int(x.strip()) for x in group_str.split(",") if x.strip()]
            else:
                group_ids = []

            monsters.append({
                "id": int(row["ID"]),
                "name": row["이름"],
                "description": row.get("드롭", ""),
                "type": row.get("타입", "CommonMob"),
                "hp": int(row["HP"]),
                "attack": int(row["Attack"]),
                "defense": int(row.get("Defense", 0)),
                "speed": int(row.get("Speed", 10)),
                "attribute": row.get("속성", "무속성") or "무속성",
                "skill_ids": skill_ids,
                "group_ids": group_ids,
                "level": int(row.get("레벨", 1)),
            })
    return monsters


async def init_db():
    """데이터베이스 연결 초기화"""
    db_url = (
        f"postgres://{os.getenv('DATABASE_USER')}:{os.getenv('DATABASE_PASSWORD')}"
        f"@{os.getenv('DATABASE_URL')}:{os.getenv('DATABASE_PORT')}"
        f"/{os.getenv('DATABASE_TABLE')}"
    )
    await Tortoise.init(
        db_url=db_url,
        modules={"models": ["models"]}
    )


async def seed_monsters():
    """몬스터 데이터 시드 (bulk 연산)"""
    from models.monster import Monster

    all_monsters = load_monsters_from_csv()
    csv_map = {m["id"]: m for m in all_monsters}
    csv_ids = set(csv_map.keys())
    print(f"몬스터 데이터 시드 시작... (CSV에서 {len(all_monsters)}개 로드)")

    # 1. 기존 DB 몬스터 ID 조회 (단일 쿼리)
    existing_ids = set(
        await Monster.all().values_list("id", flat=True)
    )

    # 2. 신규/갱신 분리
    new_ids = csv_ids - existing_ids
    update_ids = csv_ids & existing_ids

    # 3. 신규 몬스터 bulk_create
    if new_ids:
        new_monsters = [
            Monster(
                id=csv_map[mid]["id"],
                name=csv_map[mid]["name"],
                description=csv_map[mid]["description"],
                type=csv_map[mid]["type"],
                hp=csv_map[mid]["hp"],
                attack=csv_map[mid]["attack"],
                defense=csv_map[mid]["defense"],
                speed=csv_map[mid]["speed"],
                attribute=csv_map[mid]["attribute"],
                skill_ids=csv_map[mid]["skill_ids"],
                group_ids=csv_map[mid]["group_ids"],
            )
            for mid in new_ids
        ]
        await Monster.bulk_create(new_monsters)

    # 4. 기존 몬스터 bulk_update
    if update_ids:
        existing_monsters = await Monster.filter(id__in=update_ids)
        for monster in existing_monsters:
            data = csv_map[monster.id]
            monster.name = data["name"]
            monster.description = data["description"]
            monster.type = data["type"]
            monster.hp = data["hp"]
            monster.attack = data["attack"]
            monster.defense = data["defense"]
            monster.speed = data["speed"]
            monster.attribute = data["attribute"]
            monster.skill_ids = data["skill_ids"]
            monster.group_ids = data["group_ids"]
        await Monster.bulk_update(existing_monsters, fields=MONSTER_FIELDS)

    print(f"  생성: {len(new_ids)}, 갱신: {len(update_ids)}")


async def main():
    """메인 실행 함수"""
    try:
        await init_db()
        await seed_monsters()
    except Exception as e:
        print(f"오류 발생: {e}")
        raise
    finally:
        await Tortoise.close_connections()


if __name__ == "__main__":
    asyncio.run(main())
