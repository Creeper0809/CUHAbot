"""
config에서 기본 스탯을 베이스 컬럼으로 이동하는 스크립트

Attack, AP_Attack, HP, AD_Def, AP_Def, Speed는 베이스 컬럼이 있으므로
config의 passive_buff에서 제거하고 베이스 컬럼으로 이동합니다.
"""
import csv
import json
import os

csv_path = "data/items_equipment.csv"
backup_path = "data/items_equipment.csv.backup3"

# CSV 백업
os.system(f"cp {csv_path} {backup_path}")

# 기본 스탯 매핑 (config key -> CSV column name)
STAT_MAPPING = {
    "attack": "Attack",
    "ap_attack": "AP_Attack",
    "hp": "HP",
    "ad_defense": "AD_Def",
    "ap_defense": "AP_Def",
    "speed": "Speed",
}

updated_items = []
total_updated = 0

with open(csv_path, 'r', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    fieldnames = [fn for fn in reader.fieldnames if fn is not None]
    rows = []
    
    for row in reader:
        # None 키 제거
        clean_row = {k: v for k, v in row.items() if k is not None}
        rows.append(clean_row)

for row in rows:
    config_val = row.get('config')
    if config_val is None:
        continue
    
    config_str = config_val.strip()
    
    if not config_str:
        continue
    
    try:
        config = json.loads(config_str)
    except:
        continue
    
    if 'components' not in config:
        continue
    
    modified = False
    new_components = []
    
    for component in config['components']:
        if component.get('tag') != 'passive_buff':
            new_components.append(component)
            continue
        
        # passive_buff 컴포넌트에서 기본 스탯 추출
        new_component = {'tag': 'passive_buff'}
        has_other_stats = False
        
        for key, value in component.items():
            if key == 'tag':
                continue
            
            # 기본 스탯인 경우 베이스 컬럼으로 이동
            if key in STAT_MAPPING:
                csv_col = STAT_MAPPING[key]
                current_val = row.get(csv_col, '').strip() if row.get(csv_col) else ''
                
                # 현재 베이스 값에 추가
                if current_val:
                    new_val = int(current_val) + int(value)
                else:
                    new_val = int(value)
                
                row[csv_col] = str(new_val)
                modified = True
                print(f"  {row['이름']}: {key} {value} → {csv_col} 컬럼으로 이동")
            else:
                # 기본 스탯이 아닌 경우 (crit_rate, accuracy 등) config에 유지
                new_component[key] = value
                has_other_stats = True
        
        # passive_buff에 다른 스탯이 남아있으면 유지
        if has_other_stats and len(new_component) > 1:
            new_components.append(new_component)
    
    if modified:
        # config 업데이트
        if new_components:
            config['components'] = new_components
            row['config'] = json.dumps(config, ensure_ascii=False)
        else:
            # 모든 컴포넌트가 제거되었으면 config 비우기
            row['config'] = ''
        
        updated_items.append(row['이름'])
        total_updated += 1

# CSV 다시 쓰기
with open(csv_path, 'w', encoding='utf-8', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    
    writer.writeheader()
    writer.writerows(rows)

print(f"\n총 {total_updated}개 아이템 업데이트 완료")
print(f"백업 파일: {backup_path}")

if updated_items:
    print("\n업데이트된 아이템:")
    for name in updated_items[:30]:  # 처음 30개만 출력
        print(f"  - {name}")
    if len(updated_items) > 30:
        print(f"  ... 외 {len(updated_items) - 30}개")
