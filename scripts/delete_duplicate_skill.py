"""
중복 스킬 삭제 스크립트

ID 602 (생명력 흡수) 중복 스킬을 삭제합니다.
seed_skills.py 기준 ID 2004가 정식 스킬입니다.

실행: python scripts/delete_duplicate_skill.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from tortoise import Tortoise

load_dotenv()


async def init_db():
    """데이터베이스 연결 초기화"""
    db_url = f"postgres://{os.getenv('DATABASE_USER')}:{os.getenv('DATABASE_PASSWORD')}@{os.getenv('DATABASE_URL')}:{os.getenv('DATABASE_PORT')}/{os.getenv('DATABASE_TABLE')}"
    await Tortoise.init(
        db_url=db_url,
        modules={"models": ["models"]}
    )


async def delete_skill(skill_id: int):
    """스킬 삭제"""
    from models.skill import Skill_Model

    skill = await Skill_Model.get_or_none(id=skill_id)
    if skill:
        print(f"삭제할 스킬: ID={skill.id}, 이름={skill.name}")
        await skill.delete()
        print(f"✅ 스킬 ID {skill_id} 삭제 완료")
    else:
        print(f"❌ 스킬 ID {skill_id}을 찾을 수 없습니다")


async def main():
    try:
        await init_db()
        await delete_skill(602)
    except Exception as e:
        print(f"오류 발생: {e}")
        raise
    finally:
        await Tortoise.close_connections()


if __name__ == "__main__":
    asyncio.run(main())
