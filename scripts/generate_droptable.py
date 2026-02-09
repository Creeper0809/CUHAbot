"""
모든 몬스터에 드롭 데이터 생성
"""
import asyncio
import csv
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from tortoise import Tortoise

# 프로젝트 루트 경로 설정
project_root = Path(__file__).parent.parent
os.chdir(project_root)
sys.path.insert(0, str(project_root))

load_dotenv()


async def generate_droptable():
    """모든 몬스터에 대한 드롭테이블 생성"""
    db_url = (
        f'postgres://{os.getenv("DATABASE_USER")}:{os.getenv("DATABASE_PASSWORD")}@'
        f'{os.getenv("DATABASE_URL")}:{os.getenv("DATABASE_PORT")}/{os.getenv("DATABASE_TABLE")}'
    )
    await Tortoise.init(db_url=db_url, modules={'models': ['models']})

    from models import Monster, Item

    # 모든 몬스터 가져오기
    monsters = await Monster.all()

    # 재료 아이템 가져오기 (7001-7010)
    materials = await Item.filter(id__gte=7001, id__lte=7010).all()
    material_map = {item.id: item.name for item in materials}

    print(f"몬스터: {len(monsters)}개")
    print(f"재료 아이템: {len(materials)}개")
    print()

    # 몬스터 타입/속성별 재료 매핑
    # 7001: 슬라임 젤리
    # 7002: 늑대 가죽
    # 7003: 고블린 토템
    # 7004: 화염 정수
    # 7005: 냉기 정수
    # 7006: 번개 정수
    # 7007: 드래곤 비늘
    # 7008: 영혼석
    # 7009: 정화된 성수
    # 7010: 혼돈의 파편

    droptable_entries = []
    entry_id = 1

    for monster in monsters:
        # 몬스터 타입에 따른 드롭률
        if monster.type.name == 'COMMON':
            base_prob = 0.25  # 25%
        elif monster.type.name == 'ELITE':
            base_prob = 0.40  # 40%
        elif monster.type.name == 'BOSS':
            base_prob = 0.60  # 60%
        else:
            base_prob = 0.20

        # 몬스터 이름/속성에 따라 재료 결정
        material_id = None

        # 이름 기반 매칭
        name_lower = monster.name.lower()

        if '슬라임' in name_lower or '젤리' in name_lower:
            material_id = 7001
        elif '늑대' in name_lower or '울프' in name_lower or '야수' in name_lower:
            material_id = 7002
        elif '고블린' in name_lower or '오크' in name_lower:
            material_id = 7003
        elif '드래곤' in name_lower or '용' in name_lower or '와이번' in name_lower:
            material_id = 7007
        elif '영혼' in name_lower or '언데드' in name_lower or '스켈레톤' in name_lower or '좀비' in name_lower:
            material_id = 7008
        elif '성' in name_lower or '빛' in name_lower or '천사' in name_lower:
            material_id = 7009
        elif '암흑' in name_lower or '악마' in name_lower or '혼돈' in name_lower:
            material_id = 7010
        else:
            # 속성 기반 매칭
            attribute_lower = monster.attribute.lower() if monster.attribute else ''

            if '화염' in attribute_lower or '불' in attribute_lower or 'fire' in attribute_lower:
                material_id = 7004
            elif '냉기' in attribute_lower or '얼음' in attribute_lower or 'ice' in attribute_lower:
                material_id = 7005
            elif '번개' in attribute_lower or '전기' in attribute_lower or 'lightning' in attribute_lower:
                material_id = 7006
            else:
                # 기본값: HP 기준으로 재료 선택
                if monster.hp < 300:
                    material_id = 7001  # 슬라임 젤리
                elif monster.hp < 1000:
                    material_id = 7002  # 늑대 가죽
                else:
                    material_id = 7003  # 고블린 토템

        # 드롭테이블 항목 추가
        droptable_entries.append({
            'id': entry_id,
            'drop_monster': monster.id,
            'probability': base_prob,
            'item_id': material_id
        })

        material_name = material_map.get(material_id, '알 수 없음')
        print(f"{entry_id:3}. {monster.name:20} → {material_name:15} ({base_prob*100:.0f}%)")

        entry_id += 1

    # CSV 파일로 저장
    output_path = Path('data/droptable.csv')

    with open(output_path, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['id', 'drop_monster', 'probability', 'item_id'])
        writer.writeheader()
        writer.writerows(droptable_entries)

    print()
    print(f"✅ 드롭테이블 생성 완료: {len(droptable_entries)}개 항목")
    print(f"   저장 위치: {output_path}")
    print()
    print("다음 명령으로 DB에 적용하세요:")
    print("   python scripts/seed_droptable_only.py")

    await Tortoise.close_connections()


if __name__ == "__main__":
    asyncio.run(generate_droptable())
