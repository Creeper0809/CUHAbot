"""
기존 스킬 config 수정 스크립트

기존 스킬 데이터의 config 형식을 새 형식으로 업데이트합니다.
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from tortoise import Tortoise

load_dotenv()


async def init_db():
    await Tortoise.init(
        db_url=f"postgres://{os.getenv('DATABASE_USER')}:{os.getenv('DATABASE_PASSWORD')}@{os.getenv('DATABASE_URL')}:{os.getenv('DATABASE_PORT')}/{os.getenv('DATABASE_TABLE')}",
        modules={"models": ["models"]}
    )


async def fix_skills():
    from models.skill import Skill_Model

    print("스킬 config 확인 중...")

    skills = await Skill_Model.all()
    for skill in skills:
        print(f"\nID: {skill.id}, Name: {skill.name}")
        print(f"  Current config: {skill.config}")

        # components가 없거나 비어있으면 기본 공격 스킬로 설정
        if not skill.config or not skill.config.get("components"):
            new_config = {
                "components": [
                    {"tag": "attack", "damage": 1.0}
                ]
            }
            print(f"  -> Fixing config to: {new_config}")
            skill.config = new_config
            await skill.save()
            print(f"  -> Saved!")
        else:
            print(f"  -> Config OK (has {len(skill.config.get('components', []))} components)")

    print("\n완료!")


async def main():
    try:
        await init_db()
        await fix_skills()
    except Exception as e:
        print(f"오류 발생: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await Tortoise.close_connections()


if __name__ == "__main__":
    asyncio.run(main())
