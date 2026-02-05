"""
시드 데이터 삽입 스크립트

docs 문서에 정의된 게임 데이터를 데이터베이스에 삽입합니다.
실행: python scripts/seed_data.py
"""
import asyncio
import os
import sys

# 프로젝트 루트 경로 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from tortoise import Tortoise

load_dotenv()


async def init_db():
    """데이터베이스 연결 초기화"""
    await Tortoise.init(
        db_url=f"postgres://{os.getenv('DATABASE_USER')}:{os.getenv('DATABASE_PASSWORD')}@"
               f"{os.getenv('DATABASE_URL')}:{os.getenv('DATABASE_PORT')}/{os.getenv('DATABASE_TABLE')}",
        modules={"models": ["models"]}
    )
    await Tortoise.generate_schemas()


async def seed_grades():
    """등급 데이터 삽입"""
    from models.grade import Grade

    grades = [
        {"id": 1, "name": "D", "description": "일반 등급"},
        {"id": 2, "name": "C", "description": "고급 등급"},
        {"id": 3, "name": "B", "description": "희귀 등급"},
        {"id": 4, "name": "A", "description": "영웅 등급"},
        {"id": 5, "name": "S", "description": "전설 등급"},
        {"id": 6, "name": "SS", "description": "고대 등급 (Lv.51+)"},
        {"id": 7, "name": "SSS", "description": "신화 등급 (Lv.71+)"},
        {"id": 8, "name": "Mythic", "description": "창세 등급 (Lv.91+)"},
    ]

    for grade in grades:
        await Grade.update_or_create(id=grade["id"], defaults=grade)

    print(f"✓ Grade 데이터 {len(grades)}개 삽입 완료")


async def seed_dungeons():
    """던전 데이터 삽입"""
    from models.dungeon import Dungeon

    dungeons = [
        # 초보자 던전 (Lv.1-10)
        {"id": 1, "name": "잊혀진 숲", "require_level": 1, "description": "마을 근처의 안전한 숲. 초보 모험가들이 처음 경험을 쌓는 곳."},
        {"id": 2, "name": "고블린 동굴", "require_level": 5, "description": "고블린들이 점거한 어두운 동굴. 함정에 주의하라."},

        # 화염/냉기 지역 (Lv.11-15)
        {"id": 3, "name": "불타는 광산", "require_level": 11, "description": "용암이 흐르는 위험한 광산. 화상에 주의."},
        {"id": 4, "name": "얼어붙은 호수", "require_level": 11, "description": "영원히 얼어붙은 호수. 동결 위험이 있다."},

        # 번개/물 지역 (Lv.15-20)
        {"id": 5, "name": "폭풍의 봉우리", "require_level": 15, "description": "끊임없이 번개가 치는 산봉우리. 감전 피해 주의."},
        {"id": 6, "name": "수몰된 신전", "require_level": 15, "description": "바다 밑에 가라앉은 고대 신전. 익사 타이머 주의."},

        # 신성/암흑 지역 (Lv.21-25)
        {"id": 7, "name": "성스러운 대성당", "require_level": 21, "description": "타락한 성직자들이 점거한 대성당."},
        {"id": 8, "name": "어둠의 묘지", "require_level": 21, "description": "언데드가 들끓는 저주받은 묘지."},

        # 고급 던전 (Lv.26-50)
        {"id": 9, "name": "용의 둥지", "require_level": 26, "description": "드래곤들이 서식하는 위험한 영역."},
        {"id": 10, "name": "혼돈의 균열", "require_level": 31, "description": "차원의 틈새에서 쏟아지는 혼돈의 존재들."},
        {"id": 11, "name": "잊혀진 왕국", "require_level": 35, "description": "멸망한 고대 왕국의 폐허."},
        {"id": 12, "name": "심연의 궁전", "require_level": 41, "description": "심연의 지배자가 통치하는 어둠의 궁전."},
        {"id": 13, "name": "천상의 탑", "require_level": 45, "description": "천상에 닿은 고대의 탑."},

        # 고레벨 던전 (Lv.51+)
        {"id": 14, "name": "시공의 틈새", "require_level": 51, "description": "시간의 흐름이 뒤틀린 차원의 틈새."},
        {"id": 15, "name": "공허의 심연", "require_level": 55, "description": "모든 빛이 사라진 공허의 끝."},
        {"id": 16, "name": "깊은 심해", "require_level": 61, "description": "빛조차 닿지 않는 심해의 최심부."},
        {"id": 17, "name": "각성의 제단", "require_level": 65, "description": "잠든 힘을 깨우는 고대의 제단."},
        {"id": 18, "name": "잊혀진 문명의 폐허", "require_level": 71, "description": "신들조차 잊은 초고대 문명의 유적."},
        {"id": 19, "name": "시련의 탑", "require_level": 75, "description": "매 층마다 다른 시련이 기다리는 무한의 탑."},
        {"id": 20, "name": "붕괴하는 차원", "require_level": 81, "description": "존재 자체가 붕괴하고 있는 차원."},
        {"id": 21, "name": "초월자의 영역", "require_level": 85, "description": "한계를 초월한 자들만이 도달할 수 있는 영역."},
        {"id": 22, "name": "신들의 전장", "require_level": 91, "description": "신들이 전쟁을 벌인 전설의 전장."},
        {"id": 23, "name": "창세의 정원", "require_level": 95, "description": "세계가 시작된 곳. 모든 것의 기원."},
    ]

    for dungeon in dungeons:
        await Dungeon.update_or_create(id=dungeon["id"], defaults=dungeon)

    print(f"✓ Dungeon 데이터 {len(dungeons)}개 삽입 완료")


async def seed_monsters():
    """몬스터 데이터 삽입"""
    from models.monster import Monster

    monsters = [
        # === 초보자 지역 몬스터 (Lv.1-10) ===
        {"id": 1, "name": "슬라임", "description": "끈적한 액체로 이루어진 기초 몬스터", "hp": 65, "attack": 8},
        {"id": 2, "name": "고블린", "description": "작지만 교활한 녹색 생물", "hp": 80, "attack": 11},
        {"id": 3, "name": "늑대", "description": "날카로운 이빨을 가진 야생 늑대", "hp": 95, "attack": 14},
        {"id": 4, "name": "동굴 박쥐", "description": "어둠 속에서 날아다니는 박쥐", "hp": 110, "attack": 12},
        {"id": 5, "name": "고블린 궁수", "description": "활을 쏘는 고블린", "hp": 125, "attack": 20},
        {"id": 6, "name": "고블린 주술사", "description": "저주를 거는 고블린", "hp": 140, "attack": 18},
        {"id": 7, "name": "대왕 슬라임", "description": "거대하게 성장한 슬라임", "hp": 200, "attack": 22},
        {"id": 8, "name": "독버섯", "description": "독을 내뿜는 거대 버섯", "hp": 130, "attack": 15},

        # === 화염 지역 몬스터 (Lv.11-15) ===
        {"id": 10, "name": "화염 정령", "description": "불꽃으로 이루어진 정령", "hp": 215, "attack": 38},
        {"id": 11, "name": "마그마 골렘", "description": "용암으로 이루어진 거인", "hp": 280, "attack": 42},
        {"id": 12, "name": "화염 임프", "description": "불을 다루는 작은 악마", "hp": 180, "attack": 45},
        {"id": 13, "name": "불 박쥐", "description": "화염을 두른 박쥐", "hp": 160, "attack": 35},

        # === 냉기 지역 몬스터 (Lv.11-15) ===
        {"id": 14, "name": "얼음 정령", "description": "얼음으로 이루어진 정령", "hp": 200, "attack": 35},
        {"id": 15, "name": "서리 늑대", "description": "냉기를 뿜는 늑대", "hp": 220, "attack": 40},
        {"id": 16, "name": "얼어붙은 좀비", "description": "동결된 언데드", "hp": 260, "attack": 35},
        {"id": 17, "name": "눈보라 하피", "description": "눈보라를 일으키는 하피", "hp": 190, "attack": 45},

        # === 번개 지역 몬스터 (Lv.15-20) ===
        {"id": 18, "name": "천둥 정령", "description": "전기로 이루어진 정령", "hp": 275, "attack": 55},
        {"id": 19, "name": "폭풍 하피", "description": "번개를 부르는 하피", "hp": 250, "attack": 60},
        {"id": 20, "name": "번개 늑대", "description": "전기를 두른 늑대", "hp": 240, "attack": 58},
        {"id": 21, "name": "번개 요정", "description": "번개를 다루는 요정", "hp": 180, "attack": 50},

        # === 물 지역 몬스터 (Lv.15-20) ===
        {"id": 22, "name": "물 정령", "description": "물로 이루어진 정령", "hp": 300, "attack": 45},
        {"id": 23, "name": "바다뱀", "description": "바다에서 온 거대한 뱀", "hp": 280, "attack": 55},
        {"id": 24, "name": "익사한 사제", "description": "물에 빠져 죽은 언데드 사제", "hp": 260, "attack": 50},
        {"id": 25, "name": "거대 게", "description": "단단한 껍질의 거대 게", "hp": 350, "attack": 40},

        # === 신성 지역 몬스터 (Lv.21-25) ===
        {"id": 26, "name": "타락한 사제", "description": "타락한 성직자", "hp": 380, "attack": 70},
        {"id": 27, "name": "타락한 기사", "description": "타락한 성기사", "hp": 450, "attack": 80},
        {"id": 28, "name": "신성 가고일", "description": "신전을 지키는 석상", "hp": 420, "attack": 75},
        {"id": 29, "name": "빛의 정령", "description": "빛으로 이루어진 정령", "hp": 280, "attack": 85},

        # === 암흑 지역 몬스터 (Lv.21-25) ===
        {"id": 30, "name": "스켈레톤 전사", "description": "무장한 해골 전사", "hp": 400, "attack": 75},
        {"id": 31, "name": "좀비", "description": "느리지만 강인한 언데드", "hp": 500, "attack": 60},
        {"id": 32, "name": "유령", "description": "떠도는 원혼", "hp": 300, "attack": 90},
        {"id": 33, "name": "망령", "description": "강력한 원혼", "hp": 350, "attack": 100},

        # === 용의 둥지 몬스터 (Lv.26-30) ===
        {"id": 34, "name": "어린 드래곤", "description": "아직 성장 중인 드래곤", "hp": 500, "attack": 100},
        {"id": 35, "name": "드래곤 가드", "description": "드래곤을 섬기는 전사", "hp": 600, "attack": 110},
        {"id": 36, "name": "화염 드레이크", "description": "불을 뿜는 용족", "hp": 550, "attack": 120},
        {"id": 37, "name": "번개 드레이크", "description": "번개를 뿜는 용족", "hp": 520, "attack": 115},

        # === 엘리트 몬스터 (Lv.31+) ===
        {"id": 38, "name": "혼돈의 분신", "description": "혼돈에서 태어난 존재", "hp": 700, "attack": 140},
        {"id": 39, "name": "공허의 보행자", "description": "공허를 걷는 존재", "hp": 650, "attack": 160},
        {"id": 40, "name": "차원의 공포", "description": "차원의 틈에서 온 괴물", "hp": 800, "attack": 170},
        {"id": 41, "name": "엔트로피 위스프", "description": "무질서의 정령", "hp": 400, "attack": 180},

        # === 보스 몬스터 ===
        {"id": 101, "name": "고블린 족장", "description": "고블린들의 우두머리", "hp": 600, "attack": 45},
        {"id": 102, "name": "화염의 군주", "description": "불타는 광산의 지배자", "hp": 1200, "attack": 85},
        {"id": 103, "name": "서리 마녀", "description": "얼어붙은 호수의 지배자", "hp": 1000, "attack": 90},
        {"id": 104, "name": "천둥의 왕", "description": "폭풍의 봉우리를 다스리는 자", "hp": 1800, "attack": 120},
        {"id": 105, "name": "심해의 사제", "description": "수몰된 신전의 지배자", "hp": 1600, "attack": 100},
        {"id": 106, "name": "타락한 대주교", "description": "성스러운 대성당의 타락한 지배자", "hp": 2500, "attack": 150},
        {"id": 107, "name": "리치 킹", "description": "어둠의 묘지를 다스리는 왕", "hp": 2200, "attack": 160},
        {"id": 108, "name": "고대 드래곤", "description": "용의 둥지의 최강자", "hp": 4000, "attack": 200},
    ]

    for monster in monsters:
        await Monster.update_or_create(id=monster["id"], defaults=monster)

    print(f"✓ Monster 데이터 {len(monsters)}개 삽입 완료")


async def seed_skills():
    """스킬 데이터 삽입"""
    from models.skill import Skill_Model

    skills = [
        # === 기본 공격 스킬 ===
        {"id": 1, "name": "강타", "description": "100% 물리 데미지", "config": {"attack": {"damage": 1.0}}},
        {"id": 2, "name": "연속 베기", "description": "60% 데미지로 2회 공격", "config": {"attack": {"damage": 0.6, "hits": 2}}},
        {"id": 3, "name": "급소 찌르기", "description": "120% 데미지, 치명타 확률 +30%", "config": {"attack": {"damage": 1.2, "crit_bonus": 0.3}}},
        {"id": 4, "name": "회전 참격", "description": "70% 데미지로 전체 공격", "config": {"attack": {"damage": 0.7, "aoe": True}}},
        {"id": 5, "name": "파워 스트라이크", "description": "150% 데미지, 방어력 20% 무시", "config": {"attack": {"damage": 1.5, "armor_pen": 0.2}}},

        # === 화염 스킬 ===
        {"id": 101, "name": "화염구", "description": "100% 화염 데미지, 30% 확률로 화상", "config": {"attack": {"damage": 1.0, "element": "fire", "burn_chance": 0.3}}},
        {"id": 102, "name": "화염 폭발", "description": "120% 화염 데미지, 100% 화상", "config": {"attack": {"damage": 1.2, "element": "fire", "burn_chance": 1.0}}},
        {"id": 103, "name": "불기둥", "description": "130% 메인 + 60% 스플래시", "config": {"attack": {"damage": 1.3, "element": "fire", "splash": 0.6}}},
        {"id": 104, "name": "메테오", "description": "180% 전체 화염 데미지, 화상 4턴", "config": {"attack": {"damage": 1.8, "element": "fire", "aoe": True, "burn_duration": 4}}},

        # === 냉기 스킬 ===
        {"id": 201, "name": "얼음 화살", "description": "90% 냉기 데미지, 30% 둔화", "config": {"attack": {"damage": 0.9, "element": "ice", "slow_chance": 0.3}}},
        {"id": 202, "name": "빙결", "description": "80% 데미지, 50% 동결", "config": {"attack": {"damage": 0.8, "element": "ice", "freeze_chance": 0.5}}},
        {"id": 203, "name": "눈보라", "description": "80% 전체 냉기 데미지, 100% 둔화", "config": {"attack": {"damage": 0.8, "element": "ice", "aoe": True, "slow_chance": 1.0}}},

        # === 번개 스킬 ===
        {"id": 301, "name": "전격", "description": "100% 번개 데미지, 20% 마비", "config": {"attack": {"damage": 1.0, "element": "lightning", "paralyze_chance": 0.2}}},
        {"id": 302, "name": "번개 연쇄", "description": "90% 데미지, 50% 연쇄", "config": {"attack": {"damage": 0.9, "element": "lightning", "chain_chance": 0.5}}},
        {"id": 303, "name": "낙뢰", "description": "220% 번개 데미지, 방어 무시", "config": {"attack": {"damage": 2.2, "element": "lightning", "armor_pen": 1.0}}},

        # === 물 스킬 ===
        {"id": 401, "name": "물의 창", "description": "90% 물 데미지", "config": {"attack": {"damage": 0.9, "element": "water"}}},
        {"id": 402, "name": "치유의 비", "description": "3턴간 턴당 8% HP 회복", "config": {"heal": {"percent": 0.08, "duration": 3}}},
        {"id": 403, "name": "해일", "description": "160% 전체 물 데미지, 15% HP 회복", "config": {"attack": {"damage": 1.6, "element": "water", "aoe": True}, "heal": {"percent": 0.15}}},

        # === 신성 스킬 ===
        {"id": 501, "name": "빛의 화살", "description": "90% 신성 데미지, 언데드에 +50%", "config": {"attack": {"damage": 0.9, "element": "holy", "bonus_vs_undead": 0.5}}},
        {"id": 502, "name": "치유의 빛", "description": "25% HP 회복", "config": {"heal": {"percent": 0.25}}},
        {"id": 503, "name": "정화", "description": "디버프 해제, 10% HP 회복", "config": {"heal": {"percent": 0.1, "cleanse": True}}},
        {"id": 504, "name": "축복", "description": "3턴간 공방 +20%", "config": {"buff": {"attack": 0.2, "defense": 0.2, "duration": 3}}},

        # === 암흑 스킬 ===
        {"id": 601, "name": "암흑 화살", "description": "90% 암흑 데미지, 20% 저주", "config": {"attack": {"damage": 0.9, "element": "dark", "curse_chance": 0.2}}},
        {"id": 602, "name": "생명력 흡수", "description": "110% 암흑 데미지, 30% 흡혈", "config": {"attack": {"damage": 1.1, "element": "dark", "lifesteal": 0.3}}},
        {"id": 603, "name": "저주", "description": "3턴간 방어 -25%, 회복 -50%", "config": {"debuff": {"defense": -0.25, "healing": -0.5, "duration": 3}}},

        # === 회복 스킬 ===
        {"id": 1001, "name": "응급 처치", "description": "15% HP 회복", "config": {"heal": {"percent": 0.15}}},
        {"id": 1002, "name": "재생", "description": "3턴간 턴당 6% HP 회복", "config": {"heal": {"percent": 0.06, "duration": 3}}},
        {"id": 1003, "name": "치유", "description": "30% HP 회복", "config": {"heal": {"percent": 0.30}}},
        {"id": 1004, "name": "대치유", "description": "50% HP 회복, 디버프 1개 제거", "config": {"heal": {"percent": 0.50, "cleanse_one": True}}},

        # === 버프 스킬 ===
        {"id": 2001, "name": "집중", "description": "3턴간 치명타 +15%", "config": {"buff": {"crit": 0.15, "duration": 3}}},
        {"id": 2002, "name": "분노", "description": "3턴간 공격 +25%, 방어 -10%", "config": {"buff": {"attack": 0.25, "defense": -0.1, "duration": 3}}},
        {"id": 2003, "name": "수비 태세", "description": "3턴간 방어 +30%", "config": {"buff": {"defense": 0.3, "duration": 3}}},
        {"id": 2004, "name": "가속", "description": "2턴간 같은 스킬 2회 발동", "config": {"buff": {"double_cast": True, "duration": 2}}},

        # === 디버프 스킬 ===
        {"id": 3001, "name": "약점 노출", "description": "3턴간 적 방어 -15%", "config": {"debuff": {"defense": -0.15, "duration": 3}}},
        {"id": 3002, "name": "둔화", "description": "3턴간 적 속도 -30%", "config": {"debuff": {"speed": -0.3, "duration": 3}}},
        {"id": 3003, "name": "공포", "description": "2턴간 적 공방 -20%", "config": {"debuff": {"attack": -0.2, "defense": -0.2, "duration": 2}}},
    ]

    for skill in skills:
        await Skill_Model.update_or_create(id=skill["id"], defaults=skill)

    print(f"✓ Skill 데이터 {len(skills)}개 삽입 완료")


async def seed_items():
    """아이템 데이터 삽입"""
    from models.item import Item
    from models.equipment_item import EquipmentItem
    from models.consume_item import ConsumeItem
    from resources.item_emoji import ItemType

    # === 장비 아이템 ===
    equipment_items = [
        # 무기 (equip_pos=4)
        {"item": {"id": 1001, "name": "나무 검", "description": "초보자용 나무 검", "cost": 100, "type": ItemType.EQUIP},
         "equipment": {"attack": 5, "grade": 1, "equip_pos": 4}},
        {"item": {"id": 1002, "name": "철검", "description": "기본적인 철제 검", "cost": 500, "type": ItemType.EQUIP},
         "equipment": {"attack": 12, "grade": 1, "equip_pos": 4}},
        {"item": {"id": 1003, "name": "강철검", "description": "고급 강철로 만든 검", "cost": 1500, "type": ItemType.EQUIP},
         "equipment": {"attack": 25, "speed": 3, "grade": 2, "equip_pos": 4}},
        {"item": {"id": 1004, "name": "화염검", "description": "불꽃이 타오르는 검", "cost": 3000, "type": ItemType.EQUIP},
         "equipment": {"attack": 35, "grade": 2, "equip_pos": 4}},
        {"item": {"id": 1005, "name": "얼음검", "description": "냉기를 뿜는 검", "cost": 3000, "type": ItemType.EQUIP},
         "equipment": {"attack": 35, "grade": 2, "equip_pos": 4}},
        {"item": {"id": 1006, "name": "번개검", "description": "번개가 감도는 검", "cost": 5000, "type": ItemType.EQUIP},
         "equipment": {"attack": 50, "speed": 5, "grade": 3, "equip_pos": 4}},
        {"item": {"id": 1007, "name": "용의 검", "description": "드래곤의 비늘로 만든 검", "cost": 15000, "type": ItemType.EQUIP},
         "equipment": {"attack": 80, "hp": 100, "grade": 4, "equip_pos": 4}},
        {"item": {"id": 1008, "name": "전설의 검", "description": "전설에 나오는 명검", "cost": 50000, "type": ItemType.EQUIP},
         "equipment": {"attack": 120, "speed": 10, "grade": 5, "equip_pos": 4}},

        # 투구 (equip_pos=1)
        {"item": {"id": 2001, "name": "천 두건", "description": "가벼운 천으로 만든 두건", "cost": 80, "type": ItemType.EQUIP},
         "equipment": {"hp": 20, "grade": 1, "equip_pos": 1}},
        {"item": {"id": 2002, "name": "가죽 모자", "description": "튼튼한 가죽 모자", "cost": 300, "type": ItemType.EQUIP},
         "equipment": {"hp": 40, "grade": 1, "equip_pos": 1}},
        {"item": {"id": 2003, "name": "철 투구", "description": "단단한 철제 투구", "cost": 1000, "type": ItemType.EQUIP},
         "equipment": {"hp": 80, "grade": 2, "equip_pos": 1}},
        {"item": {"id": 2004, "name": "강철 투구", "description": "고급 강철 투구", "cost": 2500, "type": ItemType.EQUIP},
         "equipment": {"hp": 120, "grade": 3, "equip_pos": 1}},
        {"item": {"id": 2005, "name": "용의 투구", "description": "드래곤 비늘로 만든 투구", "cost": 12000, "type": ItemType.EQUIP},
         "equipment": {"hp": 200, "attack": 15, "grade": 4, "equip_pos": 1}},

        # 갑옷 (equip_pos=2)
        {"item": {"id": 2101, "name": "천 옷", "description": "기본적인 천 의복", "cost": 100, "type": ItemType.EQUIP},
         "equipment": {"hp": 30, "grade": 1, "equip_pos": 2}},
        {"item": {"id": 2102, "name": "가죽 갑옷", "description": "튼튼한 가죽 갑옷", "cost": 500, "type": ItemType.EQUIP},
         "equipment": {"hp": 60, "grade": 1, "equip_pos": 2}},
        {"item": {"id": 2103, "name": "사슬 갑옷", "description": "쇠사슬로 엮은 갑옷", "cost": 1500, "type": ItemType.EQUIP},
         "equipment": {"hp": 100, "grade": 2, "equip_pos": 2}},
        {"item": {"id": 2104, "name": "판금 갑옷", "description": "철판으로 만든 갑옷", "cost": 4000, "type": ItemType.EQUIP},
         "equipment": {"hp": 180, "grade": 3, "equip_pos": 2}},
        {"item": {"id": 2105, "name": "용의 갑옷", "description": "드래곤 비늘 갑옷", "cost": 15000, "type": ItemType.EQUIP},
         "equipment": {"hp": 300, "attack": 20, "grade": 4, "equip_pos": 2}},

        # 신발 (equip_pos=3)
        {"item": {"id": 2301, "name": "천 신발", "description": "가벼운 천 신발", "cost": 80, "type": ItemType.EQUIP},
         "equipment": {"speed": 2, "grade": 1, "equip_pos": 3}},
        {"item": {"id": 2302, "name": "가죽 부츠", "description": "튼튼한 가죽 부츠", "cost": 400, "type": ItemType.EQUIP},
         "equipment": {"speed": 4, "grade": 1, "equip_pos": 3}},
        {"item": {"id": 2303, "name": "철 장화", "description": "단단한 철제 장화", "cost": 1200, "type": ItemType.EQUIP},
         "equipment": {"speed": 6, "hp": 30, "grade": 2, "equip_pos": 3}},
        {"item": {"id": 2304, "name": "바람의 부츠", "description": "바람을 담은 부츠", "cost": 3500, "type": ItemType.EQUIP},
         "equipment": {"speed": 12, "grade": 3, "equip_pos": 3}},
        {"item": {"id": 2305, "name": "용의 부츠", "description": "드래곤 가죽 부츠", "cost": 10000, "type": ItemType.EQUIP},
         "equipment": {"speed": 18, "hp": 80, "grade": 4, "equip_pos": 3}},

        # 보조무기 (equip_pos=5) - 방패
        {"item": {"id": 4001, "name": "나무 방패", "description": "가벼운 나무 방패", "cost": 150, "type": ItemType.EQUIP},
         "equipment": {"hp": 25, "grade": 1, "equip_pos": 5}},
        {"item": {"id": 4002, "name": "철 방패", "description": "튼튼한 철제 방패", "cost": 800, "type": ItemType.EQUIP},
         "equipment": {"hp": 50, "grade": 2, "equip_pos": 5}},
        {"item": {"id": 4003, "name": "기사의 방패", "description": "기사단의 방패", "cost": 3000, "type": ItemType.EQUIP},
         "equipment": {"hp": 100, "grade": 3, "equip_pos": 5}},
        {"item": {"id": 4004, "name": "용의 방패", "description": "드래곤 비늘 방패", "cost": 12000, "type": ItemType.EQUIP},
         "equipment": {"hp": 180, "attack": 15, "grade": 4, "equip_pos": 5}},
    ]

    for item_data in equipment_items:
        item_dict = item_data["item"]
        equip_dict = item_data["equipment"]

        item, _ = await Item.update_or_create(id=item_dict["id"], defaults=item_dict)
        equip_dict["item"] = item
        await EquipmentItem.update_or_create(
            item=item,
            defaults=equip_dict
        )

    print(f"✓ 장비 아이템 {len(equipment_items)}개 삽입 완료")

    # === 소비 아이템 ===
    consume_items = [
        {"item": {"id": 5001, "name": "초급 HP 포션", "description": "HP를 100 회복", "cost": 50, "type": ItemType.CONSUME}, "amount": 100},
        {"item": {"id": 5002, "name": "중급 HP 포션", "description": "HP를 300 회복", "cost": 150, "type": ItemType.CONSUME}, "amount": 300},
        {"item": {"id": 5003, "name": "고급 HP 포션", "description": "HP를 700 회복", "cost": 400, "type": ItemType.CONSUME}, "amount": 700},
        {"item": {"id": 5004, "name": "최상급 HP 포션", "description": "HP를 1500 회복", "cost": 1000, "type": ItemType.CONSUME}, "amount": 1500},
        {"item": {"id": 5005, "name": "완전 HP 포션", "description": "HP를 완전히 회복", "cost": 2500, "type": ItemType.CONSUME}, "amount": 9999},
        {"item": {"id": 5101, "name": "힘의 물약", "description": "공격력 +20% (5분)", "cost": 300, "type": ItemType.CONSUME}, "amount": 0},
        {"item": {"id": 5102, "name": "마력의 물약", "description": "마법 공격력 +20% (5분)", "cost": 300, "type": ItemType.CONSUME}, "amount": 0},
        {"item": {"id": 5103, "name": "민첩의 물약", "description": "속도 +30% (5분)", "cost": 300, "type": ItemType.CONSUME}, "amount": 0},
        {"item": {"id": 5104, "name": "수호의 물약", "description": "방어력 +25% (5분)", "cost": 300, "type": ItemType.CONSUME}, "amount": 0},
        {"item": {"id": 5201, "name": "해독제", "description": "독 상태 해제", "cost": 100, "type": ItemType.CONSUME}, "amount": 0},
        {"item": {"id": 5202, "name": "해동제", "description": "동결/둔화 해제", "cost": 100, "type": ItemType.CONSUME}, "amount": 0},
        {"item": {"id": 5203, "name": "정화수", "description": "모든 디버프 해제", "cost": 500, "type": ItemType.CONSUME}, "amount": 0},
        {"item": {"id": 5301, "name": "화염병", "description": "100 화염 데미지 + 화상", "cost": 150, "type": ItemType.CONSUME}, "amount": 100},
        {"item": {"id": 5302, "name": "냉기 구슬", "description": "80 냉기 데미지 + 둔화", "cost": 150, "type": ItemType.CONSUME}, "amount": 80},
        {"item": {"id": 5303, "name": "번개 부적", "description": "120 번개 데미지 + 마비", "cost": 200, "type": ItemType.CONSUME}, "amount": 120},
    ]

    for consume_data in consume_items:
        item_dict = consume_data["item"]
        amount = consume_data["amount"]

        item, _ = await Item.update_or_create(id=item_dict["id"], defaults=item_dict)
        await ConsumeItem.update_or_create(
            item=item,
            defaults={"amount": amount}
        )

    print(f"✓ 소비 아이템 {len(consume_items)}개 삽입 완료")


async def seed_dungeon_spawns():
    """던전 스폰 데이터 삽입"""
    from models.dungeon_spawn import DungeonSpawn

    spawns = [
        # 잊혀진 숲 (던전 1)
        {"dungeon_id": 1, "monster_id": 1, "prob": 0.40},  # 슬라임
        {"dungeon_id": 1, "monster_id": 2, "prob": 0.30},  # 고블린
        {"dungeon_id": 1, "monster_id": 3, "prob": 0.20},  # 늑대
        {"dungeon_id": 1, "monster_id": 101, "prob": 0.10},  # 보스: 고블린 족장

        # 고블린 동굴 (던전 2)
        {"dungeon_id": 2, "monster_id": 2, "prob": 0.30},  # 고블린
        {"dungeon_id": 2, "monster_id": 4, "prob": 0.20},  # 동굴 박쥐
        {"dungeon_id": 2, "monster_id": 5, "prob": 0.20},  # 고블린 궁수
        {"dungeon_id": 2, "monster_id": 6, "prob": 0.15},  # 고블린 주술사
        {"dungeon_id": 2, "monster_id": 101, "prob": 0.15},  # 보스: 고블린 족장

        # 불타는 광산 (던전 3)
        {"dungeon_id": 3, "monster_id": 10, "prob": 0.30},  # 화염 정령
        {"dungeon_id": 3, "monster_id": 11, "prob": 0.25},  # 마그마 골렘
        {"dungeon_id": 3, "monster_id": 12, "prob": 0.20},  # 화염 임프
        {"dungeon_id": 3, "monster_id": 13, "prob": 0.15},  # 불 박쥐
        {"dungeon_id": 3, "monster_id": 102, "prob": 0.10},  # 보스: 화염의 군주

        # 얼어붙은 호수 (던전 4)
        {"dungeon_id": 4, "monster_id": 14, "prob": 0.30},  # 얼음 정령
        {"dungeon_id": 4, "monster_id": 15, "prob": 0.25},  # 서리 늑대
        {"dungeon_id": 4, "monster_id": 16, "prob": 0.20},  # 얼어붙은 좀비
        {"dungeon_id": 4, "monster_id": 17, "prob": 0.15},  # 눈보라 하피
        {"dungeon_id": 4, "monster_id": 103, "prob": 0.10},  # 보스: 서리 마녀

        # 폭풍의 봉우리 (던전 5)
        {"dungeon_id": 5, "monster_id": 18, "prob": 0.30},  # 천둥 정령
        {"dungeon_id": 5, "monster_id": 19, "prob": 0.25},  # 폭풍 하피
        {"dungeon_id": 5, "monster_id": 20, "prob": 0.20},  # 번개 늑대
        {"dungeon_id": 5, "monster_id": 21, "prob": 0.15},  # 번개 요정
        {"dungeon_id": 5, "monster_id": 104, "prob": 0.10},  # 보스: 천둥의 왕

        # 수몰된 신전 (던전 6)
        {"dungeon_id": 6, "monster_id": 22, "prob": 0.30},  # 물 정령
        {"dungeon_id": 6, "monster_id": 23, "prob": 0.25},  # 바다뱀
        {"dungeon_id": 6, "monster_id": 24, "prob": 0.20},  # 익사한 사제
        {"dungeon_id": 6, "monster_id": 25, "prob": 0.15},  # 거대 게
        {"dungeon_id": 6, "monster_id": 105, "prob": 0.10},  # 보스: 심해의 사제

        # 성스러운 대성당 (던전 7)
        {"dungeon_id": 7, "monster_id": 26, "prob": 0.30},  # 타락한 사제
        {"dungeon_id": 7, "monster_id": 27, "prob": 0.25},  # 타락한 기사
        {"dungeon_id": 7, "monster_id": 28, "prob": 0.25},  # 신성 가고일
        {"dungeon_id": 7, "monster_id": 29, "prob": 0.10},  # 빛의 정령
        {"dungeon_id": 7, "monster_id": 106, "prob": 0.10},  # 보스: 타락한 대주교

        # 어둠의 묘지 (던전 8)
        {"dungeon_id": 8, "monster_id": 30, "prob": 0.30},  # 스켈레톤 전사
        {"dungeon_id": 8, "monster_id": 31, "prob": 0.25},  # 좀비
        {"dungeon_id": 8, "monster_id": 32, "prob": 0.20},  # 유령
        {"dungeon_id": 8, "monster_id": 33, "prob": 0.15},  # 망령
        {"dungeon_id": 8, "monster_id": 107, "prob": 0.10},  # 보스: 리치 킹

        # 용의 둥지 (던전 9)
        {"dungeon_id": 9, "monster_id": 34, "prob": 0.30},  # 어린 드래곤
        {"dungeon_id": 9, "monster_id": 35, "prob": 0.25},  # 드래곤 가드
        {"dungeon_id": 9, "monster_id": 36, "prob": 0.20},  # 화염 드레이크
        {"dungeon_id": 9, "monster_id": 37, "prob": 0.15},  # 번개 드레이크
        {"dungeon_id": 9, "monster_id": 108, "prob": 0.10},  # 보스: 고대 드래곤

        # 혼돈의 균열 (던전 10)
        {"dungeon_id": 10, "monster_id": 38, "prob": 0.30},  # 혼돈의 분신
        {"dungeon_id": 10, "monster_id": 39, "prob": 0.25},  # 공허의 보행자
        {"dungeon_id": 10, "monster_id": 40, "prob": 0.25},  # 차원의 공포
        {"dungeon_id": 10, "monster_id": 41, "prob": 0.20},  # 엔트로피 위스프
    ]

    # 기존 데이터 삭제 후 새로 삽입
    await DungeonSpawn.all().delete()

    for spawn in spawns:
        await DungeonSpawn.create(**spawn)

    print(f"✓ DungeonSpawn 데이터 {len(spawns)}개 삽입 완료")


async def main():
    """메인 함수"""
    print("=" * 50)
    print("CUHABot 시드 데이터 삽입 시작")
    print("=" * 50)

    await init_db()

    await seed_grades()
    await seed_dungeons()
    await seed_monsters()
    await seed_skills()
    await seed_items()
    await seed_dungeon_spawns()

    await Tortoise.close_connections()

    print("=" * 50)
    print("모든 시드 데이터 삽입 완료!")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
