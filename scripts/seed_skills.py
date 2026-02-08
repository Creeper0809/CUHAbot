"""
스킬 데이터 시드 스크립트

data/skills.csv에서 스킬 데이터를 읽어 데이터베이스에 추가합니다.
몬스터 전용 스킬(카테고리=monster)은 제외합니다.

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


def load_skills_from_csv() -> list[dict]:
    """CSV 파일에서 스킬 데이터 로드 (모든 스킬 포함)"""
    skills = []
    with open(CSV_PATH, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            config = json.loads(row["config"])

            # 플레이어_획득가능 파싱 (Y/N -> bool)
            obtainable_str = row.get("플레이어_획득가능", "Y").strip().upper()
            player_obtainable = (obtainable_str == "Y")

            skills.append({
                "id": int(row["ID"]),
                "name": row["이름"],
                "description": row["효과"],
                "config": config,
                "attribute": row.get("속성", "무속성") or "무속성",
                "keyword": row.get("키워드", ""),
                "player_obtainable": player_obtainable,
            })
    return skills


async def init_db():
    """데이터베이스 연결 초기화"""
    db_url = f"postgres://{os.getenv('DATABASE_USER')}:{os.getenv('DATABASE_PASSWORD')}@{os.getenv('DATABASE_URL')}:{os.getenv('DATABASE_PORT')}/{os.getenv('DATABASE_TABLE')}"
    await Tortoise.init(
        db_url=db_url,
        modules={"models": ["models"]}
    )


async def seed_skills():
    """스킬 데이터 시드"""
    from models.skill import Skill_Model

    all_skills = load_skills_from_csv()
    print(f"스킬 데이터 시드 시작... (CSV에서 {len(all_skills)}개 로드)")
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
                "player_obtainable": skill_data["player_obtainable"],
            }
        )

        if created:
            created_count += 1
            obtainable_mark = "✅" if skill_data["player_obtainable"] else "❌"
            print(f"  [생성] {skill_data['id']}: {skill_data['name']} ({skill_data['attribute']}) {obtainable_mark}")
        else:
            skill.name = skill_data["name"]
            skill.description = skill_data["description"]
            skill.config = skill_data["config"]
            skill.attribute = skill_data["attribute"]
            skill.keyword = skill_data["keyword"]
            skill.player_obtainable = skill_data["player_obtainable"]
            await skill.save()
            updated_count += 1
            obtainable_mark = "✅" if skill_data["player_obtainable"] else "❌"
            print(f"  [갱신] {skill_data['id']}: {skill_data['name']} ({skill_data['attribute']}) {obtainable_mark}")

    print(f"\n완료! 생성: {created_count}, 갱신: {updated_count}, 총: {len(all_skills)}")


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
