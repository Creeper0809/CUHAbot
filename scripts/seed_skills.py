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
    "일반": 1, "희귀": 3, "영웅": 5, "전설": 6,
}


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
    """스킬 데이터 동기화 (CSV 기준)"""
    from models.skill import Skill_Model
    from models.user_owned_skill import UserOwnedSkill
    from models.user_skill_deck import UserSkillDeck

    all_skills = load_skills_from_csv()
    csv_ids = {s["id"] for s in all_skills}
    print(f"CSV에서 {len(all_skills)}개 스킬 로드")

    # 1. CSV 스킬 생성/갱신
    created_count = 0
    updated_count = 0

    for skill_data in all_skills:
        skill, created = await Skill_Model.get_or_create(
            id=skill_data["id"],
            defaults={
                "name": skill_data["name"],
                "description": skill_data["description"],
                "config": skill_data["config"],
                "attribute": skill_data["attribute"],
                "keyword": skill_data["keyword"],
                "grade": skill_data["grade"],
                "player_obtainable": skill_data["player_obtainable"],
            }
        )

        if created:
            created_count += 1
        else:
            skill.name = skill_data["name"]
            skill.description = skill_data["description"]
            skill.config = skill_data["config"]
            skill.attribute = skill_data["attribute"]
            skill.keyword = skill_data["keyword"]
            skill.grade = skill_data["grade"]
            skill.player_obtainable = skill_data["player_obtainable"]
            await skill.save()
            updated_count += 1

    print(f"  생성: {created_count}, 갱신: {updated_count}")

    # 2. CSV에 없는 DB 스킬 찾기
    db_skills = await Skill_Model.all()
    orphan_skills = [s for s in db_skills if s.id not in csv_ids]

    if not orphan_skills:
        print("\n삭제할 고아 스킬 없음")
        return

    # 3. 영향 받는 유저 정보 출력
    print(f"\n--- CSV에 없는 DB 스킬 {len(orphan_skills)}개 발견 ---")
    for skill in orphan_skills:
        owned_count = await UserOwnedSkill.filter(skill_id=skill.id).count()
        deck_count = await UserSkillDeck.filter(skill_id=skill.id).count()
        print(f"  [{skill.id}] {skill.name} — 소유: {owned_count}명, 덱: {deck_count}건")

    # 4. 삭제 (CASCADE로 user_owned_skill, user_skill_deck 자동 정리)
    orphan_ids = [s.id for s in orphan_skills]
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
