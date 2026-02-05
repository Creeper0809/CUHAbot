"""
스킬 데이터 시드 스크립트

Phase 2 기본 스킬 데이터를 데이터베이스에 추가합니다.
- 무속성 공격 스킬 13개
- 회복 스킬 5개
- 버프 스킬 5개

실행: python scripts/seed_skills.py
"""
import asyncio
import os
import sys

# 프로젝트 루트를 path에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from tortoise import Tortoise

load_dotenv()


# =============================================================================
# 스킬 데이터 정의
# =============================================================================

# 무속성 공격 스킬 (ID 1001~1013)
NEUTRAL_ATTACK_SKILLS = [
    {
        "id": 1001,
        "name": "강타",
        "description": "적에게 100% 물리 데미지를 입힌다.",
        "config": {
            "components": [
                {"tag": "attack", "damage": 1.0}
            ]
        }
    },
    {
        "id": 1002,
        "name": "연속 베기",
        "description": "적에게 60% 데미지를 2회 입힌다.",
        "config": {
            "components": [
                {"tag": "attack", "damage": 0.6, "hit_count": 2}
            ]
        }
    },
    {
        "id": 1003,
        "name": "급소 찌르기",
        "description": "적에게 120% 데미지, 치명타 확률 +30%.",
        "config": {
            "components": [
                {"tag": "attack", "damage": 1.2, "crit_bonus": 0.3}
            ]
        }
    },
    {
        "id": 1004,
        "name": "회전 참격",
        "description": "적에게 70% 데미지를 입힌다. (전체 공격용)",
        "config": {
            "components": [
                {"tag": "attack", "damage": 0.7}
            ]
        }
    },
    {
        "id": 1005,
        "name": "파워 스트라이크",
        "description": "적에게 150% 데미지, 방어력 20% 무시.",
        "config": {
            "components": [
                {"tag": "attack", "damage": 1.5, "armor_pen": 0.2}
            ]
        }
    },
    {
        "id": 1006,
        "name": "일섬",
        "description": "적에게 200% 데미지, 100% 치명타.",
        "config": {
            "components": [
                {"tag": "attack", "damage": 2.0, "crit_bonus": 1.0}
            ]
        }
    },
    {
        "id": 1007,
        "name": "천공검",
        "description": "적에게 350% 데미지, 방어력 완전 무시.",
        "config": {
            "components": [
                {"tag": "attack", "damage": 3.5, "armor_pen": 0.7}
            ]
        }
    },
    {
        "id": 1008,
        "name": "돌진",
        "description": "적에게 80% 데미지를 입히고 선제공격한다.",
        "config": {
            "components": [
                {"tag": "attack", "damage": 0.8}
            ]
        }
    },
    {
        "id": 1009,
        "name": "집중 공격",
        "description": "적에게 130% 데미지를 입힌다.",
        "config": {
            "components": [
                {"tag": "attack", "damage": 1.3}
            ]
        }
    },
    {
        "id": 1010,
        "name": "난무",
        "description": "적에게 40% 데미지를 4회 입힌다.",
        "config": {
            "components": [
                {"tag": "attack", "damage": 0.4, "hit_count": 4}
            ]
        }
    },
    {
        "id": 1011,
        "name": "맹공",
        "description": "적에게 180% 데미지를 입힌다.",
        "config": {
            "components": [
                {"tag": "attack", "damage": 1.8}
            ]
        }
    },
    {
        "id": 1012,
        "name": "처형",
        "description": "적에게 250% 데미지. HP가 낮을수록 위력 증가.",
        "config": {
            "components": [
                {"tag": "attack", "damage": 2.5}
            ]
        }
    },
    {
        "id": 1013,
        "name": "분쇄",
        "description": "적에게 200% 데미지, 방어력 30% 무시.",
        "config": {
            "components": [
                {"tag": "attack", "damage": 2.0, "armor_pen": 0.3}
            ]
        }
    },
]

# 회복 스킬 (ID 2001~2005)
HEAL_SKILLS = [
    {
        "id": 2001,
        "name": "응급 처치",
        "description": "HP의 15%를 회복한다.",
        "config": {
            "components": [
                {"tag": "heal", "percent": 0.15}
            ]
        }
    },
    {
        "id": 2002,
        "name": "재생",
        "description": "HP의 6%를 회복한다. (재생 효과)",
        "config": {
            "components": [
                {"tag": "heal", "percent": 0.06}
            ]
        }
    },
    {
        "id": 2003,
        "name": "치유의 빛",
        "description": "HP의 25%를 회복한다.",
        "config": {
            "components": [
                {"tag": "heal", "percent": 0.25}
            ]
        }
    },
    {
        "id": 2004,
        "name": "생명력 흡수",
        "description": "적에게 80% 데미지를 입히고 피해량의 30%를 회복한다.",
        "config": {
            "components": [
                {"tag": "lifesteal", "ad_ratio": 0.8, "lifesteal": 0.3}
            ]
        }
    },
    {
        "id": 2005,
        "name": "보호막",
        "description": "HP의 20%에 해당하는 보호막(회복)을 얻는다.",
        "config": {
            "components": [
                {"tag": "heal", "percent": 0.2}
            ]
        }
    },
]

# 버프 스킬 (ID 3001~3005)
BUFF_SKILLS = [
    {
        "id": 3001,
        "name": "집중",
        "description": "3턴간 치명타 확률 +15%.",
        "config": {
            "components": [
                {"tag": "buff", "duration": 3, "crit_rate": 0.15}
            ]
        }
    },
    {
        "id": 3002,
        "name": "분노",
        "description": "3턴간 공격력 +25%, 방어력 -10%.",
        "config": {
            "components": [
                {"tag": "buff", "duration": 3, "attack": 0.25, "defense": -0.1}
            ]
        }
    },
    {
        "id": 3003,
        "name": "수비 태세",
        "description": "3턴간 방어력 +30%.",
        "config": {
            "components": [
                {"tag": "buff", "duration": 3, "defense": 0.3}
            ]
        }
    },
    {
        "id": 3004,
        "name": "신속",
        "description": "3턴간 속도 +20%.",
        "config": {
            "components": [
                {"tag": "buff", "duration": 3, "speed": 0.2}
            ]
        }
    },
    {
        "id": 3005,
        "name": "결의",
        "description": "3턴간 공격력 +15%, 방어력 +15%.",
        "config": {
            "components": [
                {"tag": "buff", "duration": 3, "attack": 0.15, "defense": 0.15}
            ]
        }
    },
]

ALL_SKILLS = NEUTRAL_ATTACK_SKILLS + HEAL_SKILLS + BUFF_SKILLS


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

    print("스킬 데이터 시드 시작...")
    created_count = 0
    updated_count = 0

    for skill_data in ALL_SKILLS:
        skill, created = await Skill_Model.get_or_create(
            id=skill_data["id"],
            defaults={
                "name": skill_data["name"],
                "description": skill_data["description"],
                "config": skill_data["config"],
            }
        )

        if created:
            created_count += 1
            print(f"  [생성] {skill_data['id']}: {skill_data['name']}")
        else:
            # 기존 데이터 업데이트
            skill.name = skill_data["name"]
            skill.description = skill_data["description"]
            skill.config = skill_data["config"]
            await skill.save()
            updated_count += 1
            print(f"  [갱신] {skill_data['id']}: {skill_data['name']}")

    print(f"\n완료! 생성: {created_count}, 갱신: {updated_count}, 총: {len(ALL_SKILLS)}")


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
