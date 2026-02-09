"""
Droptable만 시드하는 스크립트
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
from models import Droptable


async def seed_droptable():
    """droptable.csv에서 드롭 테이블 시드"""
    print("🔄 Droptable 시드 시작...")

    csv_path = project_root / "data" / "droptable.csv"
    if not csv_path.exists():
        print(f"❌ {csv_path} 파일이 없습니다.")
        return

    # 기존 데이터 삭제
    await Droptable.all().delete()
    print("✅ 기존 Droptable 데이터 삭제 완료")

    # CSV 읽기 및 삽입
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        count = 0

        for row in reader:
            await Droptable.create(
                id=int(row['id']),
                drop_monster=int(row['drop_monster']) if row['drop_monster'] else None,
                probability=float(row['probability']) if row['probability'] else None,
                item_id=int(row['item_id']) if row['item_id'] else None,
            )
            count += 1

    print(f"✅ Droptable 시드 완료: {count}개 항목")


async def main():
    """메인 함수"""
    # 환경 변수 로드
    from dotenv import load_dotenv
    load_dotenv()

    # DB 연결
    db_url = (
        f'postgres://{os.getenv("DATABASE_USER")}:{os.getenv("DATABASE_PASSWORD")}@'
        f'{os.getenv("DATABASE_URL")}:{os.getenv("DATABASE_PORT")}/{os.getenv("DATABASE_TABLE")}'
    )

    print(f"📡 DB 연결 중...")

    await Tortoise.init(
        db_url=db_url,
        modules={"models": ["models"]}
    )

    try:
        await seed_droptable()
        print("\n🎉 시드 완료!")
    except Exception as e:
        print(f"\n❌ 에러 발생: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await Tortoise.close_connections()


if __name__ == "__main__":
    asyncio.run(main())
