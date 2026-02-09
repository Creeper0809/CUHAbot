"""
몬스터 설명만 업데이트하는 스크립트
"""
import asyncio
import csv
import os
import sys
from pathlib import Path

# 프로젝트 루트 경로 설정
project_root = Path(__file__).parent.parent
os.chdir(project_root)
sys.path.insert(0, str(project_root))

from tortoise import Tortoise
from models import Monster
from dotenv import load_dotenv

load_dotenv()

async def update_monster_descriptions():
    """CSV의 설명을 읽어 몬스터 설명 업데이트"""
    print("🔄 몬스터 설명 업데이트 시작...")

    csv_path = project_root / "data" / "monsters.csv"

    # CSV 읽기
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    updated_count = 0
    for row in rows:
        monster_id = int(row['ID'])
        description = row.get('설명', '').strip()

        if not description:
            continue

        # 몬스터 찾기 및 업데이트
        monster = await Monster.get_or_none(id=monster_id)
        if monster:
            monster.description = description
            await monster.save()
            updated_count += 1
            print(f"  {monster_id:>3}. {monster.name}: {description[:50]}...")

    print(f"\n✅ {updated_count}개 몬스터 설명 업데이트 완료!")

async def main():
    """메인 함수"""
    # DB 연결
    db_url = (
        f"postgres://{os.getenv('DATABASE_USER')}:{os.getenv('DATABASE_PASSWORD')}@"
        f"{os.getenv('DATABASE_URL')}:{os.getenv('DATABASE_PORT')}/{os.getenv('DATABASE_TABLE')}"
    )

    print(f"📡 DB 연결 중...")

    await Tortoise.init(
        db_url=db_url,
        modules={"models": ["models"]}
    )

    try:
        await update_monster_descriptions()
        print("\n🎉 업데이트 완료!")
    except Exception as e:
        print(f"\n❌ 에러 발생: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await Tortoise.close_connections()

if __name__ == "__main__":
    asyncio.run(main())
