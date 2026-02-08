"""
몬스터 데이터 CSV → DB 동기화

DB의 몬스터 레코드를 CSV 기준으로 업데이트합니다.
skill_ids, drop_skill_ids, 스탯 등 모든 필드를 동기화합니다.
"""
import asyncio
import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def safe_int(val, default=0):
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


async def main():
    from tortoise import Tortoise
    from dotenv import load_dotenv

    load_dotenv()

    db_host = os.getenv("DATABASE_URL")
    db_user = os.getenv("DATABASE_USER")
    db_pass = os.getenv("DATABASE_PASSWORD")
    db_port = os.getenv("DATABASE_PORT", "5432")
    db_name = os.getenv("DATABASE_TABLE")

    await Tortoise.init(
        db_url=f"postgres://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}",
        modules={"models": ["models"]},
    )

    from models.monster import Monster

    csv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "monsters.csv")

    with open(csv_path, "r", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    print(f"CSV에서 {len(rows)}개 몬스터 로드")

    updated = 0
    created = 0
    errors = []

    for row in rows:
        monster_id = int(row["ID"])

        # 이름 정리
        name = row["이름"]
        paren_idx = name.find("(")
        if paren_idx > 0:
            name = name[:paren_idx].strip()

        monster_type = row.get("타입", "CommonMob")
        skill_ids = json.loads(row.get("skill_ids", "[]"))
        drop_skill_ids = json.loads(row.get("drop_skill_ids", "[]"))

        group_str = row.get("그룹", "").strip()
        if group_str:
            group_ids = [int(x.strip()) for x in group_str.split(",") if x.strip()]
        else:
            group_ids = []

        update_data = {
            "name": name,
            "description": row.get("드롭", "") or "",
            "type": monster_type,
            "hp": safe_int(row.get("HP", "0")),
            "attack": safe_int(row.get("Attack", "0")),
            "defense": safe_int(row.get("Defense", "0")),
            "speed": safe_int(row.get("Speed", "10"), 10),
            "attribute": row.get("속성", "무속성") or "무속성",
            "skill_ids": skill_ids,
            "drop_skill_ids": drop_skill_ids,
            "group_ids": group_ids,
        }

        try:
            monster = await Monster.get_or_none(id=monster_id)
            if monster:
                # 변경 사항 감지
                changes = []
                old_skill_ids = getattr(monster, "skill_ids", []) or []
                if old_skill_ids != skill_ids:
                    changes.append(f"skill_ids: {old_skill_ids} → {skill_ids}")

                old_drop = getattr(monster, "drop_skill_ids", []) or []
                if old_drop != drop_skill_ids:
                    changes.append(f"drop_skill_ids: {old_drop} → {drop_skill_ids}")

                for field, value in update_data.items():
                    setattr(monster, field, value)
                await monster.save()
                updated += 1

                if changes:
                    print(f"  [UPDATE] #{monster_id} {name}: {', '.join(changes)}")
            else:
                await Monster.create(id=monster_id, **update_data)
                created += 1
                print(f"  [CREATE] #{monster_id} {name}")
        except Exception as e:
            errors.append(f"#{monster_id} {name}: {e}")
            print(f"  [ERROR] #{monster_id} {name}: {e}")

    print(f"\n완료: {updated}개 업데이트, {created}개 생성, {len(errors)}개 오류")
    if errors:
        print("오류 목록:")
        for err in errors:
            print(f"  - {err}")

    await Tortoise.close_connections()


if __name__ == "__main__":
    asyncio.run(main())
