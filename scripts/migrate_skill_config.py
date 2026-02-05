"""
스킬 config 마이그레이션 스크립트

기존 형식:
  {'attack': {'damage': 1.0}}

새 형식:
  {'components': [{'tag': 'attack', 'damage': 1.0}]}

실행: python scripts/migrate_skill_config.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from tortoise import Tortoise

load_dotenv()


def convert_old_config_to_new(old_config: dict) -> dict:
    """
    기존 config 형식을 새 형식으로 변환

    기존: {'attack': {...}, 'heal': {...}, 'buff': {...}}
    새로운: {'components': [{'tag': 'attack', ...}, {'tag': 'heal', ...}]}
    """
    if not old_config:
        return {"components": [{"tag": "attack", "damage": 1.0}]}

    # 이미 새 형식이면 그대로 반환
    if "components" in old_config:
        return old_config

    components = []

    # attack 변환
    if "attack" in old_config:
        attack_data = old_config["attack"]
        component = {"tag": "attack"}

        # damage 필드
        if "damage" in attack_data:
            component["damage"] = attack_data["damage"]
        else:
            component["damage"] = 1.0  # 기본값

        # hit_count (hits -> hit_count)
        if "hits" in attack_data:
            component["hit_count"] = attack_data["hits"]
        if "hit_count" in attack_data:
            component["hit_count"] = attack_data["hit_count"]

        # crit_bonus
        if "crit_bonus" in attack_data:
            component["crit_bonus"] = attack_data["crit_bonus"]

        # armor_pen
        if "armor_pen" in attack_data:
            component["armor_pen"] = attack_data["armor_pen"]

        components.append(component)

    # heal 변환
    if "heal" in old_config:
        heal_data = old_config["heal"]
        component = {"tag": "heal"}

        if "percent" in heal_data:
            component["percent"] = heal_data["percent"]
        elif "amount" in heal_data:
            component["amount"] = heal_data["amount"]
        else:
            component["percent"] = 0.15  # 기본값

        components.append(component)

    # buff 변환
    if "buff" in old_config:
        buff_data = old_config["buff"]
        component = {"tag": "buff"}

        if "duration" in buff_data:
            component["duration"] = buff_data["duration"]
        else:
            component["duration"] = 3  # 기본값

        if "attack" in buff_data:
            component["attack"] = buff_data["attack"]
        if "defense" in buff_data:
            component["defense"] = buff_data["defense"]
        if "speed" in buff_data:
            component["speed"] = buff_data["speed"]
        if "crit" in buff_data:
            component["crit"] = buff_data["crit"]

        components.append(component)

    # debuff 변환
    if "debuff" in old_config:
        debuff_data = old_config["debuff"]
        component = {"tag": "debuff"}

        if "duration" in debuff_data:
            component["duration"] = debuff_data["duration"]
        else:
            component["duration"] = 3  # 기본값

        if "attack" in debuff_data:
            component["attack"] = debuff_data["attack"]
        if "defense" in debuff_data:
            component["defense"] = debuff_data["defense"]
        if "speed" in debuff_data:
            component["speed"] = debuff_data["speed"]

        components.append(component)

    # 아무 컴포넌트도 없으면 기본 공격
    if not components:
        components.append({"tag": "attack", "damage": 1.0})

    return {"components": components}


async def init_db():
    await Tortoise.init(
        db_url=f"postgres://{os.getenv('DATABASE_USER')}:{os.getenv('DATABASE_PASSWORD')}@{os.getenv('DATABASE_URL')}:{os.getenv('DATABASE_PORT')}/{os.getenv('DATABASE_TABLE')}",
        modules={"models": ["models"]}
    )


async def migrate_skills():
    from models.skill import Skill_Model

    print("=" * 60)
    print("스킬 config 마이그레이션 시작")
    print("=" * 60)

    skills = await Skill_Model.all()
    migrated = 0
    skipped = 0

    for skill in skills:
        old_config = skill.config

        # 이미 새 형식이면 스킵
        if old_config and "components" in old_config:
            print(f"[SKIP] ID {skill.id} ({skill.name}): 이미 새 형식")
            skipped += 1
            continue

        new_config = convert_old_config_to_new(old_config)

        print(f"\n[MIGRATE] ID {skill.id} ({skill.name})")
        print(f"  Old: {old_config}")
        print(f"  New: {new_config}")

        skill.config = new_config
        await skill.save()
        migrated += 1
        print(f"  -> 저장 완료!")

    print("\n" + "=" * 60)
    print(f"마이그레이션 완료!")
    print(f"  변환됨: {migrated}")
    print(f"  스킵됨: {skipped}")
    print(f"  총: {len(skills)}")
    print("=" * 60)


async def main():
    try:
        await init_db()
        await migrate_skills()
    except Exception as e:
        print(f"오류 발생: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await Tortoise.close_connections()


if __name__ == "__main__":
    asyncio.run(main())
