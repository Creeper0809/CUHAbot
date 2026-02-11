"""
장비 아이템 기본 스탯 마이그레이션

CSV에서 수정된 기본 스탯(attack, ap_attack, hp, defense, speed)을 
DB에 반영하고 config를 업데이트합니다.
"""
import asyncio
import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from tortoise import Tortoise
from models import Item, EquipmentItem

load_dotenv()


async def init_db():
    await Tortoise.init(
        db_url=f"postgres://{os.getenv('DATABASE_USER')}:{os.getenv('DATABASE_PASSWORD')}@"
               f"{os.getenv('DATABASE_URL')}:{os.getenv('DATABASE_PORT')}/{os.getenv('DATABASE_TABLE')}",
        modules={"models": ["models"]}
    )


def parse_stat_value(value_str):
    """스탯 값 파싱 (범위 값은 건너뜀)"""
    if not value_str:
        return None
    
    value_str = value_str.strip()
    if not value_str:
        return None
    
    # 범위 값(30~200)이면 None 반환 (DB에서 그대로 유지)
    if '~' in value_str:
        return None
    
    # +10 형식 처리
    if value_str.startswith('+'):
        return int(value_str[1:])
    
    return int(value_str)


async def migrate_equipment():
    """CSV에서 읽어서 DB 업데이트"""
    csv_path = "data/items_equipment.csv"
    
    updated_count = 0
    skipped_count = 0
    
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            item_id = int(row['ID'])
            
            # EquipmentItem 조회
            equip = await EquipmentItem.get_or_none(item_id=item_id)
            if not equip:
                continue
            
            # 베이스 스탯 업데이트
            modified = False
            
            # Attack
            attack_val = parse_stat_value(row.get('Attack', ''))
            if attack_val is not None:
                if equip.attack != attack_val:
                    equip.attack = attack_val
                    modified = True
            
            # AP_Attack
            ap_attack_val = parse_stat_value(row.get('AP_Attack', ''))
            if ap_attack_val is not None:
                if equip.ap_attack != ap_attack_val:
                    equip.ap_attack = ap_attack_val
                    modified = True
            
            # HP
            hp_val = parse_stat_value(row.get('HP', ''))
            if hp_val is not None:
                if equip.hp != hp_val:
                    equip.hp = hp_val
                    modified = True
            
            # AD_Defense
            ad_def_val = parse_stat_value(row.get('AD_Def', ''))
            if ad_def_val is not None:
                if equip.ad_defense != ad_def_val:
                    equip.ad_defense = ad_def_val
                    modified = True
            
            # AP_Defense
            ap_def_val = parse_stat_value(row.get('AP_Def', ''))
            if ap_def_val is not None:
                if equip.ap_defense != ap_def_val:
                    equip.ap_defense = ap_def_val
                    modified = True
            
            # Speed
            speed_val = parse_stat_value(row.get('Speed', ''))
            if speed_val is not None:
                if equip.speed != speed_val:
                    equip.speed = speed_val
                    modified = True
            
            # Config 업데이트
            config_str = row.get('config', '').strip()
            if config_str:
                try:
                    config = json.loads(config_str)
                    if equip.config != config:
                        equip.config = config
                        modified = True
                except:
                    pass
            else:
                if equip.config:
                    equip.config = None
                    modified = True
            
            if modified:
                await equip.save()
                updated_count += 1
                print(f"✓ {row['이름']} 업데이트")
            else:
                skipped_count += 1
    
    print(f"\n총 {updated_count}개 장비 아이템 업데이트 완료")
    if skipped_count > 0:
        print(f"변경사항 없음: {skipped_count}개")


async def main():
    print("=" * 60)
    print("장비 아이템 기본 스탯 마이그레이션")
    print("=" * 60)
    
    await init_db()
    await migrate_equipment()
    await Tortoise.close_connections()
    
    print("\n" + "=" * 60)
    print("완료!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
