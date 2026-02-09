"""
장비 컴포넌트 DB 마이그레이션

CSV의 config를 DB의 equipment_item 테이블에 동기화합니다.
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

CSV_PATH = os.path.join(PROJECT_ROOT, "data", "items_equipment.csv")


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


def load_equipment_from_csv():
    """CSV에서 장비 데이터 로드"""
    equipment = []
    with open(CSV_PATH, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            config_str = row.get('config', '').strip()
            if not config_str:
                config = None
            else:
                try:
                    config = json.loads(config_str)
                except json.JSONDecodeError:
                    print(f"⚠️  [{row['ID']}] {row['이름']}: JSON 파싱 실패")
                    config = None

            equipment.append({
                "id": int(row['ID']),
                "name": row['이름'],
                "config": config
            })

    return equipment


async def migrate_equipment():
    """장비 config를 DB에 동기화"""
    from models.equipment_item import EquipmentItem

    all_equipment = load_equipment_from_csv()
    print(f"CSV에서 {len(all_equipment)}개 장비 로드")
    print()

    updated_count = 0
    no_change_count = 0

    for eq_data in all_equipment:
        eq = await EquipmentItem.filter(id=eq_data["id"]).first()

        if not eq:
            print(f"⚠️  [{eq_data['id']}] {eq_data['name']}: DB에 없음 (스킵)")
            continue

        # config 비교
        old_config = eq.config
        new_config = eq_data["config"]

        # 변경사항이 없으면 스킵
        if old_config == new_config:
            no_change_count += 1
            continue

        # 업데이트
        eq.config = new_config
        await eq.save()

        updated_count += 1
        print(f"✅ [{eq_data['id']}] {eq_data['name']}")
        if old_config:
            print(f"   기존: {json.dumps(old_config, ensure_ascii=False)}")
        else:
            print(f"   기존: (없음)")
        print(f"   신규: {json.dumps(new_config, ensure_ascii=False)}")
        print()

    print("=" * 80)
    print("마이그레이션 완료")
    print("=" * 80)
    print(f"업데이트: {updated_count}개")
    print(f"변경 없음: {no_change_count}개")


async def main():
    """메인 실행"""
    try:
        await init_db()
        await migrate_equipment()
    except Exception as e:
        print(f"오류 발생: {e}")
        raise
    finally:
        await Tortoise.close_connections()


if __name__ == "__main__":
    asyncio.run(main())
