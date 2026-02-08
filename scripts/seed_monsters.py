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


def load_monsters_from_csv() -> list[dict]:
    """CSV 파일에서 몬스터 데이터 로드"""
    monsters = []
    with open(CSV_PATH, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # skill_ids는 JSON 배열로 저장되어 있음
            skill_ids = json.loads(row.get("skill_ids", "[]"))

            # group_ids 파싱 (쉼표 구분 -> 정수 리스트)
            group_str = row.get("그룹", "").strip()
            if group_str:
                group_ids = [int(x.strip()) for x in group_str.split(",") if x.strip()]
            else:
                group_ids = []

            monsters.append({
                "id": int(row["ID"]),
                "name": row["이름"],
                "description": row.get("드롭", ""),  # 설명 필드가 없으므로 드롭 정보 사용
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
    db_url = f"postgres://{os.getenv('DATABASE_USER')}:{os.getenv('DATABASE_PASSWORD')}@{os.getenv('DATABASE_URL')}:{os.getenv('DATABASE_PORT')}/{os.getenv('DATABASE_TABLE')}"
    await Tortoise.init(
        db_url=db_url,
        modules={"models": ["models"]}
    )


async def seed_monsters():
    """몬스터 데이터 시드"""
    from models.monster import Monster

    all_monsters = load_monsters_from_csv()
    print(f"몬스터 데이터 시드 시작... (CSV에서 {len(all_monsters)}개 로드)")
    created_count = 0
    updated_count = 0

    for monster_data in all_monsters:
        monster, created = await Monster.get_or_create(
            id=monster_data["id"],
            defaults={
                "name": monster_data["name"],
                "description": monster_data["description"],
                "type": monster_data["type"],
                "hp": monster_data["hp"],
                "attack": monster_data["attack"],
                "defense": monster_data["defense"],
                "speed": monster_data["speed"],
                "attribute": monster_data["attribute"],
                "skill_ids": monster_data["skill_ids"],
                "group_ids": monster_data["group_ids"],
            }
        )

        if created:
            created_count += 1
            skill_count = len(monster_data["skill_ids"])
            group_count = len(monster_data["group_ids"])
            group_str = f", 그룹 {group_count}종" if group_count > 0 else ", 솔로 전용"
            print(f"  [생성] {monster_data['id']}: {monster_data['name']} (Lv{monster_data['level']}, 스킬 {skill_count}개{group_str})")
        else:
            # 기존 몬스터 업데이트
            monster.name = monster_data["name"]
            monster.description = monster_data["description"]
            monster.type = monster_data["type"]
            monster.hp = monster_data["hp"]
            monster.attack = monster_data["attack"]
            monster.defense = monster_data["defense"]
            monster.speed = monster_data["speed"]
            monster.attribute = monster_data["attribute"]
            monster.skill_ids = monster_data["skill_ids"]
            monster.group_ids = monster_data["group_ids"]
            await monster.save()

            updated_count += 1
            skill_count = len(monster_data["skill_ids"])
            group_count = len(monster_data["group_ids"])
            group_str = f", 그룹 {group_count}종" if group_count > 0 else ", 솔로"
            print(f"  [업데이트] {monster_data['id']}: {monster_data['name']} (스킬 {skill_count}개{group_str})")

    print(f"\n✅ 몬스터 시드 완료!")
    print(f"  - 생성: {created_count}개")
    print(f"  - 업데이트: {updated_count}개")
    print(f"  - 총: {created_count + updated_count}개")


async def main():
    """메인 실행 함수"""
    await init_db()
    await seed_monsters()
    await Tortoise.close_connections()


if __name__ == "__main__":
    asyncio.run(main())
