"""
스킬 데이터 시드 스크립트

data/skills.csv에서 스킬 데이터를 읽어 데이터베이스와 동기화합니다.
- CSV에 있는 스킬: 생성 또는 갱신
- CSV에 없는 DB 스킬: 삭제 (CASCADE로 유저 소유/덱도 정리)

실행: python scripts/seed_skills.py
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

CSV_PATH = os.path.join(PROJECT_ROOT, "data", "skills.csv")

GRADE_MAP = {
    "D": 1, "C": 2, "B": 3, "A": 4,
    "S": 5, "SS": 6, "SSS": 7, "신화": 8,
}

SKILL_FIELDS = ["name", "description", "config", "attribute", "keyword", "grade", "player_obtainable", "acquisition_source"]


def load_skills_from_csv() -> list[dict]:
    """CSV 파일에서 스킬 데이터 로드 (모든 스킬 포함)"""
    skills = []
    with open(CSV_PATH, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            config = json.loads(row["config"])

            obtainable_str = row.get("플레이어_획득가능", "Y").strip().upper()
            player_obtainable = (obtainable_str == "Y")

            grade_str = row.get("등급", "").strip()
            grade = GRADE_MAP.get(grade_str)

            skills.append({
                "id": int(row["ID"]),
                "name": row["이름"],
                "description": row["효과"],
                "config": config,
                "attribute": row.get("속성", "무속성") or "무속성",
                "keyword": row.get("키워드", ""),
                "grade": grade,
                "player_obtainable": player_obtainable,
                "acquisition_source": row.get("획득처", "").strip(),
            })
    return skills


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


async def seed_skills():
    """스킬 데이터 동기화 (CSV 기준, bulk 연산)"""
    from models.skill import Skill_Model
    from models.user_owned_skill import UserOwnedSkill
    from models.user_skill_deck import UserSkillDeck

    all_skills = load_skills_from_csv()
    csv_ids = {s["id"] for s in all_skills}
    csv_map = {s["id"]: s for s in all_skills}
    print(f"CSV에서 {len(all_skills)}개 스킬 로드")

    # 1. 기존 DB 스킬 ID 조회 (단일 쿼리)
    existing_ids = set(
        await Skill_Model.all().values_list("id", flat=True)
    )

    # 2. 신규/갱신 분리
    new_ids = csv_ids - existing_ids
    update_ids = csv_ids & existing_ids

    # 3. 신규 스킬 bulk_create
    if new_ids:
        new_skills = [
            Skill_Model(
                id=csv_map[sid]["id"],
                name=csv_map[sid]["name"],
                description=csv_map[sid]["description"],
                config=csv_map[sid]["config"],
                attribute=csv_map[sid]["attribute"],
                keyword=csv_map[sid]["keyword"],
                grade=csv_map[sid]["grade"],
                player_obtainable=csv_map[sid]["player_obtainable"],
                acquisition_source=csv_map[sid]["acquisition_source"],
            )
            for sid in new_ids
        ]
        await Skill_Model.bulk_create(new_skills)

    # 4. 기존 스킬 bulk_update
    if update_ids:
        existing_skills = await Skill_Model.filter(id__in=update_ids)
        for skill in existing_skills:
            data = csv_map[skill.id]
            skill.name = data["name"]
            skill.description = data["description"]
            skill.config = data["config"]
            skill.attribute = data["attribute"]
            skill.keyword = data["keyword"]
            skill.grade = data["grade"]
            skill.player_obtainable = data["player_obtainable"]
            skill.acquisition_source = data["acquisition_source"]
        await Skill_Model.bulk_update(existing_skills, fields=SKILL_FIELDS)

    print(f"  생성: {len(new_ids)}, 갱신: {len(update_ids)}")

    # 5. CSV에 없는 DB 스킬 삭제
    orphan_ids = existing_ids - csv_ids
    if not orphan_ids:
        print("\n삭제할 고아 스킬 없음")
        return

    print(f"\n--- CSV에 없는 DB 스킬 {len(orphan_ids)}개 발견 ---")
    for sid in orphan_ids:
        owned_count = await UserOwnedSkill.filter(skill_id=sid).count()
        deck_count = await UserSkillDeck.filter(skill_id=sid).count()
        print(f"  [{sid}] 소유: {owned_count}명, 덱: {deck_count}건")

    deleted = await Skill_Model.filter(id__in=orphan_ids).delete()
    print(f"\n삭제 완료: {deleted}개 스킬 (연관 유저 데이터 CASCADE 정리됨)")


async def main():
    """메인 실행"""
    try:
        await init_db()
        await seed_skills()
    except Exception as e:
        print(f"오류 발생: {e}")
        raise
    finally:
        await Tortoise.close_connections()


if __name__ == "__main__":
    asyncio.run(main())
