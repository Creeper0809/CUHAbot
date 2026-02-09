"""
장비 컴포넌트 검증 스크립트
"""
import asyncio
import json
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv
from tortoise import Tortoise

load_dotenv()


async def init_db():
    """데이터베이스 연결"""
    db_url = (
        f"postgres://{os.getenv('DATABASE_USER')}:{os.getenv('DATABASE_PASSWORD')}"
        f"@{os.getenv('DATABASE_URL')}:{os.getenv('DATABASE_PORT')}"
        f"/{os.getenv('DATABASE_TABLE')}"
    )
    await Tortoise.init(db_url=db_url, modules={"models": ["models"]})


async def verify_equipment_components():
    """장비 컴포넌트 검증"""
    from models.equipment_item import EquipmentItem

    # 전체 장비 조회 (item 관계 fetch)
    all_items = await EquipmentItem.all().prefetch_related('item')
    items_with_config = [item for item in all_items if item.config]

    print("=" * 80)
    print(f"📊 전체 장비: {len(all_items)}개")
    print(f"   - config 있음: {len(items_with_config)}개")
    print(f"   - config 없음: {len(all_items) - len(items_with_config)}개")
    print("=" * 80)

    # 컴포넌트 타입별 분류
    component_types = {}
    for eq_item in items_with_config:
        if eq_item.config and "components" in eq_item.config:
            for comp in eq_item.config["components"]:
                tag = comp.get("tag", "unknown")
                if tag not in component_types:
                    component_types[tag] = []
                component_types[tag].append((eq_item.id, eq_item.item.name))

    print("\n📦 컴포넌트 타입별 장비 개수:")
    for tag, items in sorted(component_types.items(), key=lambda x: -len(x[1])):
        print(f"  {tag}: {len(items)}개")
        for item_id, name in items[:3]:
            print(f"    [{item_id}] {name}")
        if len(items) > 3:
            print(f"    ... 외 {len(items) - 3}개")

    # 새로 구현된 컴포넌트 검증
    print("\n" + "=" * 80)
    print("✅ 새로 구현된 컴포넌트 검증")
    print("=" * 80)

    new_components = {
        "on_attack_proc": "공격 시 프록 효과",
        "race_bonus": "종족 특효",
        "on_kill_stack": "처치 시 스택"
    }

    for tag, desc in new_components.items():
        # JSON 쿼리로 특정 태그 검색
        items = [item for item in items_with_config
                 if item.config and "components" in item.config
                 and any(c.get("tag") == tag for c in item.config["components"])]

        print(f"\n{tag} ({desc}): {len(items)}개")
        for eq_item in items:
            print(f"  [{eq_item.id}] {eq_item.item.name}")
            # 해당 컴포넌트만 출력
            for comp in eq_item.config["components"]:
                if comp.get("tag") == tag:
                    print(f"      {json.dumps(comp, ensure_ascii=False)}")


async def main():
    try:
        await init_db()
        await verify_equipment_components()
    except Exception as e:
        print(f"❌ 오류: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await Tortoise.close_connections()


if __name__ == "__main__":
    asyncio.run(main())
