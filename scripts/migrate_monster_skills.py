"""
몬스터 스킬 마이그레이션 스크립트

1. 몬스터 전용 스킬 데이터 추가 (ID 5001~)
2. monster 테이블에 스탯 컬럼 추가:
   - skill_ids: 스킬 ID 목록
   - defense: 물리 방어력
   - ap_attack: 마법 공격력
   - ap_defense: 마법 방어력
   - speed: 속도
   - evasion: 회피율
3. 각 몬스터에 스킬 ID 할당

실행: python scripts/migrate_monster_skills.py
"""
import asyncio
import os
import sys

# 프로젝트 루트를 path에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from tortoise import Tortoise
from tortoise.exceptions import OperationalError

load_dotenv()


# =============================================================================
# 몬스터 전용 스킬 데이터 (ID 5001~)
# docs/Monsters.md 기반
# =============================================================================

MONSTER_SKILLS = [
    # === 초보자 구역 (Lv.1-10) ===
    # 슬라임
    {
        "id": 5100,
        "name": "점액 튀기기",
        "description": "끈적한 점액을 튀겨 물리(0.8AD) 공격을 준다.",
        "config": {"components": [{"tag": "attack", "ad_ratio": 0.8}]}
    },
    {
        "id": 5101,
        "name": "점액 재생",
        "description": "몸을 재구성하여 HP의 10%를 회복한다.",
        "config": {"components": [{"tag": "heal", "percent": 0.1}]}
    },
    # 대왕 슬라임
    {
        "id": 5102,
        "name": "거대 점액포",
        "description": "거대한 점액 덩어리를 발사해 물리(1.3AD) 공격을 준다.",
        "config": {"components": [{"tag": "attack", "ad_ratio": 1.3}]}
    },
    {
        "id": 5103,
        "name": "대재생",
        "description": "거대한 몸을 재구성하여 HP의 15%를 회복한다.",
        "config": {"components": [{"tag": "heal", "percent": 0.15}]}
    },
    # 동굴 박쥐
    {
        "id": 5104,
        "name": "초음파",
        "description": "날카로운 초음파로 물리(0.9AD) 공격을 준다.",
        "config": {"components": [{"tag": "attack", "ad_ratio": 0.9}]}
    },
    {
        "id": 5105,
        "name": "급강하",
        "description": "급강하하여 물리(1.1AD) 공격을 준다.",
        "config": {"components": [{"tag": "attack", "ad_ratio": 1.1}]}
    },
    # 독버섯
    {
        "id": 5106,
        "name": "독포자",
        "description": "독 포자를 뿌려 물리(1.0AD) 공격을 준다.",
        "config": {"components": [{"tag": "attack", "ad_ratio": 1.0}]}
    },
    {
        "id": 5107,
        "name": "마비 가루",
        "description": "마비 가루를 뿌려 물리(0.8AD) 공격, 속도 -20%.",
        "config": {"components": [{"tag": "attack", "ad_ratio": 0.8}, {"tag": "debuff", "duration": 2, "speed": -0.2}]}
    },
    # 고블린
    {
        "id": 5001,
        "name": "난타",
        "description": "2회 물리(0.5AD) 공격을 준다.",
        "config": {"components": [{"tag": "attack", "ad_ratio": 0.5, "hit_count": 2}]}
    },
    # 늑대
    {
        "id": 5002,
        "name": "물어뜯기",
        "description": "물리(1.5AD) 공격을 준다.",
        "config": {"components": [{"tag": "attack", "ad_ratio": 1.5}]}
    },
    # 고블린 궁수
    {
        "id": 5003,
        "name": "연사",
        "description": "3회 물리(0.4AD) 공격을 준다.",
        "config": {"components": [{"tag": "attack", "ad_ratio": 0.4, "hit_count": 3}]}
    },
    # 고블린 주술사
    {
        "id": 5004,
        "name": "저주",
        "description": "3턴간 방어력 -20%.",
        "config": {"components": [{"tag": "debuff", "duration": 3, "defense": -0.2}]}
    },
    # 고블린 족장
    {
        "id": 5005,
        "name": "족장의 명령",
        "description": "아군을 독려한다. 3턴간 공격력 +30%.",
        "config": {"components": [{"tag": "buff", "duration": 3, "attack": 0.3}]}
    },
    {
        "id": 5006,
        "name": "분노의 일격",
        "description": "물리(2.0AD) 공격을 준다.",
        "config": {"components": [{"tag": "attack", "ad_ratio": 2.0}]}
    },

    # === 화염 구역 (Lv.11-15) ===
    # 불 박쥐
    {
        "id": 5108,
        "name": "화염 급강하",
        "description": "불꽃을 두르고 급강하하여 물리(1.2AD) 공격을 준다.",
        "config": {"components": [{"tag": "attack", "ad_ratio": 1.2}]}
    },
    {
        "id": 5109,
        "name": "불꽃 초음파",
        "description": "화염을 담은 초음파로 물리(1.0AD) 공격을 준다.",
        "config": {"components": [{"tag": "attack", "ad_ratio": 1.0}]}
    },
    {
        "id": 5010,
        "name": "화염구",
        "description": "마법(1.3AP) 공격을 준다.",
        "config": {"components": [{"tag": "attack", "ap_ratio": 1.3}]}
    },
    {
        "id": 5011,
        "name": "용암 내뿜기",
        "description": "물리(1.0AD) 공격을 준다.",
        "config": {"components": [{"tag": "attack", "ad_ratio": 1.0}]}
    },
    {
        "id": 5012,
        "name": "불꽃 연쇄",
        "description": "3회 물리(0.5AD) 공격을 준다.",
        "config": {"components": [{"tag": "attack", "ad_ratio": 0.5, "hit_count": 3}]}
    },
    {
        "id": 5013,
        "name": "지옥불",
        "description": "마법(1.5AP) 화염 공격을 준다.",
        "config": {"components": [{"tag": "attack", "ap_ratio": 1.5}]}
    },
    {
        "id": 5014,
        "name": "화염 폭발",
        "description": "마법(2.5AP) 공격을 준다.",
        "config": {"components": [{"tag": "attack", "ap_ratio": 2.5}]}
    },
    {
        "id": 5015,
        "name": "불의 비",
        "description": "마법(0.5AP) 공격을 준다.",
        "config": {"components": [{"tag": "attack", "ap_ratio": 0.5}]}
    },

    # === 냉기 구역 (Lv.11-15) ===
    # 얼어붙은 좀비
    {
        "id": 5110,
        "name": "얼어붙은 손톱",
        "description": "얼어붙은 손톱으로 할퀴어 물리(1.1AD) 공격, 속도 -10%.",
        "config": {"components": [{"tag": "attack", "ad_ratio": 1.1}, {"tag": "debuff", "duration": 2, "speed": -0.1}]}
    },
    {
        "id": 5111,
        "name": "냉기 포옹",
        "description": "차가운 포옹으로 물리(0.9AD) 공격을 준다.",
        "config": {"components": [{"tag": "attack", "ad_ratio": 0.9}]}
    },
    {
        "id": 5020,
        "name": "빙결",
        "description": "마법(1.2AP) 냉기 공격을 준다.",
        "config": {"components": [{"tag": "attack", "ap_ratio": 1.2}]}
    },
    {
        "id": 5021,
        "name": "냉기 송곳니",
        "description": "물리(1.4AD) 공격을 준다.",
        "config": {"components": [{"tag": "attack", "ad_ratio": 1.4}]}
    },
    {
        "id": 5022,
        "name": "절대 영도",
        "description": "마법(1.3AP) 냉기 공격을 준다.",
        "config": {"components": [{"tag": "attack", "ap_ratio": 1.3}]}
    },
    {
        "id": 5023,
        "name": "눈보라",
        "description": "마법(0.4AP) 냉기 공격을 준다.",
        "config": {"components": [{"tag": "attack", "ap_ratio": 0.4}]}
    },
    {
        "id": 5024,
        "name": "얼음 창",
        "description": "마법(2.2AP) 냉기 공격을 준다.",
        "config": {"components": [{"tag": "attack", "ap_ratio": 2.2}]}
    },

    # === 번개 구역 (Lv.15-20) ===
    {
        "id": 5030,
        "name": "낙뢰",
        "description": "마법(1.5AP) 번개 공격을 준다.",
        "config": {"components": [{"tag": "attack", "ap_ratio": 1.5}]}
    },
    {
        "id": 5031,
        "name": "폭풍 날개",
        "description": "물리(1.0AD) 공격을 준다.",
        "config": {"components": [{"tag": "attack", "ad_ratio": 1.0}]}
    },
    {
        "id": 5032,
        "name": "천둥의 심판",
        "description": "마법(1.6AP) 번개 공격을 준다.",
        "config": {"components": [{"tag": "attack", "ap_ratio": 1.6}]}
    },
    {
        "id": 5033,
        "name": "번개 연쇄",
        "description": "마법(1.8AP) 번개 공격을 준다.",
        "config": {"components": [{"tag": "attack", "ap_ratio": 1.8}]}
    },
    {
        "id": 5034,
        "name": "폭풍 소환",
        "description": "마법(1.0AP) 번개 공격을 준다.",
        "config": {"components": [{"tag": "attack", "ap_ratio": 1.0}]}
    },

    # === 수속성 구역 (Lv.15-20) ===
    # 거대 게
    {
        "id": 5112,
        "name": "집게 집기",
        "description": "강력한 집게로 집어 물리(1.4AD) 공격을 준다.",
        "config": {"components": [{"tag": "attack", "ad_ratio": 1.4}]}
    },
    {
        "id": 5113,
        "name": "단단한 껍질",
        "description": "껍질을 세워 3턴간 방어력 +40%.",
        "config": {"components": [{"tag": "buff", "duration": 3, "defense": 0.4}]}
    },
    {
        "id": 5114,
        "name": "거품 분사",
        "description": "거품을 뿜어 물리(1.0AD) 공격, 속도 -15%.",
        "config": {"components": [{"tag": "attack", "ad_ratio": 1.0}, {"tag": "debuff", "duration": 2, "speed": -0.15}]}
    },
    {
        "id": 5040,
        "name": "수류탄",
        "description": "마법(1.2AP) 수속성 공격을 준다.",
        "config": {"components": [{"tag": "attack", "ap_ratio": 1.2}]}
    },
    {
        "id": 5041,
        "name": "치유의 파도",
        "description": "HP의 20%를 회복한다.",
        "config": {"components": [{"tag": "heal", "percent": 0.2}]}
    },
    {
        "id": 5042,
        "name": "해일",
        "description": "마법(1.4AP) 수속성 공격을 준다.",
        "config": {"components": [{"tag": "attack", "ap_ratio": 1.4}]}
    },
    {
        "id": 5043,
        "name": "심해의 축복",
        "description": "HP의 25%를 회복한다.",
        "config": {"components": [{"tag": "heal", "percent": 0.25}]}
    },
    {
        "id": 5044,
        "name": "익사의 저주",
        "description": "마법(0.1AP) 수속성 공격을 준다.",
        "config": {"components": [{"tag": "attack", "ap_ratio": 0.1}]}
    },

    # === 신성 구역 (Lv.21-25) ===
    {
        "id": 5050,
        "name": "심판의 빛",
        "description": "마법(1.5AP) 신성 공격을 준다.",
        "config": {"components": [{"tag": "attack", "ap_ratio": 1.5}]}
    },
    {
        "id": 5051,
        "name": "신성한 일격",
        "description": "물리(1.8AD) 공격, 방어력 무시 30%.",
        "config": {"components": [{"tag": "attack", "ad_ratio": 1.8, "armor_pen": 0.3}]}
    },
    {
        "id": 5052,
        "name": "천벌",
        "description": "마법(1.8AP) 신성 공격을 준다.",
        "config": {"components": [{"tag": "attack", "ap_ratio": 1.8}]}
    },
    {
        "id": 5053,
        "name": "정화의 불꽃",
        "description": "마법(2.5AP) 신성 공격을 준다.",
        "config": {"components": [{"tag": "attack", "ap_ratio": 2.5}]}
    },
    {
        "id": 5054,
        "name": "신성 결계",
        "description": "3턴간 방어력 +50%.",
        "config": {"components": [{"tag": "buff", "duration": 3, "defense": 0.5}]}
    },

    # === 암흑 구역 (Lv.21-25) ===
    # 좀비
    {
        "id": 5115,
        "name": "썩은 손톱",
        "description": "썩은 손톱으로 할퀴어 물리(1.0AD) 공격을 준다.",
        "config": {"components": [{"tag": "attack", "ad_ratio": 1.0}]}
    },
    {
        "id": 5116,
        "name": "감염된 물기",
        "description": "썩은 이빨로 물어 물리(1.2AD) 공격, 공격력 -10%.",
        "config": {"components": [{"tag": "attack", "ad_ratio": 1.2}, {"tag": "debuff", "duration": 2, "attack": -0.1}]}
    },
    {
        "id": 5117,
        "name": "시체 돌진",
        "description": "온몸을 던져 물리(1.3AD) 공격을 준다.",
        "config": {"components": [{"tag": "attack", "ad_ratio": 1.3}]}
    },
    {
        "id": 5060,
        "name": "뼈 가르기",
        "description": "물리(1.6AD) 공격, 방어력 -15%.",
        "config": {"components": [{"tag": "attack", "ad_ratio": 1.6}, {"tag": "debuff", "duration": 2, "defense": -0.15}]}
    },
    {
        "id": 5061,
        "name": "빙의",
        "description": "마법(1.0AP) 암흑 공격을 준다.",
        "config": {"components": [{"tag": "attack", "ap_ratio": 1.0}]}
    },
    {
        "id": 5062,
        "name": "생명력 흡수",
        "description": "물리(1.2AD) 공격, 피해량의 50% 회복.",
        "config": {"components": [{"tag": "lifesteal", "ad_ratio": 1.2, "lifesteal": 0.5}]}
    },
    {
        "id": 5063,
        "name": "죽음의 손길",
        "description": "마법(2.0AP) 암흑 공격을 준다.",
        "config": {"components": [{"tag": "attack", "ap_ratio": 2.0}]}
    },
    {
        "id": 5064,
        "name": "언데드 군단",
        "description": "마법(0.5AP) 암흑 공격을 준다.",
        "config": {"components": [{"tag": "attack", "ap_ratio": 0.5}]}
    },
    {
        "id": 5065,
        "name": "영혼 수확",
        "description": "마법(1.5AP) 암흑 공격을 준다.",
        "config": {"components": [{"tag": "attack", "ap_ratio": 1.5}]}
    },

    # === 용의 둥지 (Lv.26-30) ===
    {
        "id": 5070,
        "name": "브레스",
        "description": "마법(1.3AP) 화염/번개 공격을 준다.",
        "config": {"components": [{"tag": "attack", "ap_ratio": 1.3}]}
    },
    {
        "id": 5071,
        "name": "수호자의 일격",
        "description": "물리(1.7AD) 공격을 준다.",
        "config": {"components": [{"tag": "attack", "ad_ratio": 1.7}]}
    },
    {
        "id": 5072,
        "name": "화염 브레스",
        "description": "마법(2.0AP) 화염 공격을 준다.",
        "config": {"components": [{"tag": "attack", "ap_ratio": 2.0}]}
    },
    {
        "id": 5073,
        "name": "뇌격 브레스",
        "description": "마법(2.0AP) 번개 공격을 준다.",
        "config": {"components": [{"tag": "attack", "ap_ratio": 2.0}]}
    },
    {
        "id": 5074,
        "name": "드래곤 클로",
        "description": "물리(3.0AD) 공격, 방어력 70% 무시.",
        "config": {"components": [{"tag": "attack", "ad_ratio": 3.0, "armor_pen": 0.7}]}
    },
    {
        "id": 5075,
        "name": "용의 포효",
        "description": "2턴간 공격력/방어력 -30%.",
        "config": {"components": [{"tag": "debuff", "duration": 2, "attack": -0.3, "defense": -0.3}]}
    },

    # === 엘리트/최종 보스 (Lv.31+) ===
    {
        "id": 5080,
        "name": "혼돈의 일격",
        "description": "물리(1.5AD) 혼돈 공격을 준다.",
        "config": {"components": [{"tag": "attack", "ad_ratio": 1.5}]}
    },
    {
        "id": 5081,
        "name": "공허 이동",
        "description": "물리(1.5AD) 공격, 회피 불가.",
        "config": {"components": [{"tag": "attack", "ad_ratio": 1.5}]}
    },
    {
        "id": 5082,
        "name": "혼돈의 물결",
        "description": "마법(1.8AP) 혼돈 공격을 준다.",
        "config": {"components": [{"tag": "attack", "ap_ratio": 1.8}]}
    },
    {
        "id": 5083,
        "name": "차원 분열",
        "description": "마법(3.0AP) 공격을 준다.",
        "config": {"components": [{"tag": "attack", "ap_ratio": 3.0}]}
    },

    # === 심연/신계 (Lv.41+) ===
    {
        "id": 5090,
        "name": "심연의 나락",
        "description": "마법(2.0AP) 암흑 공격을 준다.",
        "config": {"components": [{"tag": "attack", "ap_ratio": 2.0}]}
    },
    {
        "id": 5091,
        "name": "생명 착취",
        "description": "물리(2.5AD) 공격, 피해량의 100% 회복.",
        "config": {"components": [{"tag": "lifesteal", "ad_ratio": 2.5, "lifesteal": 1.0}]}
    },
    {
        "id": 5092,
        "name": "신의 심판",
        "description": "최대 HP의 50% 고정 데미지.",
        "config": {"components": [{"tag": "attack", "ad_ratio": 0.5}]}
    },
    {
        "id": 5093,
        "name": "정화의 광선",
        "description": "마법(2.5AP) 신성 공격을 준다.",
        "config": {"components": [{"tag": "attack", "ap_ratio": 2.5}]}
    },
]


# =============================================================================
# 몬스터별 스킬 ID 매핑
# 형식: "몬스터이름": [스킬ID1, 스킬ID2, ...]
# 빈 슬롯은 0으로 채움 (최대 10개)
# =============================================================================

MONSTER_SKILL_MAPPING = {
    # === 초보자 구역 ===
    "슬라임": [5100, 5101, 0, 0, 0, 0, 0, 0, 0, 0],  # 점액 튀기기, 탄성 돌진
    "고블린": [5001, 5001, 0, 0, 0, 0, 0, 0, 0, 0],  # 난타 x2
    "늑대": [5002, 5002, 0, 0, 0, 0, 0, 0, 0, 0],  # 물어뜯기 x2
    "고블린 궁수": [5003, 5003, 0, 0, 0, 0, 0, 0, 0, 0],  # 연사 x2
    "고블린 주술사": [5004, 5004, 0, 0, 0, 0, 0, 0, 0, 0],  # 저주 x2
    "동굴 박쥐": [5104, 5105, 0, 0, 0, 0, 0, 0, 0, 0],  # 초음파, 급강하
    "대왕 슬라임": [5102, 5103, 5102, 0, 0, 0, 0, 0, 0, 0],  # 거대 점액포 x2, 압살
    "독버섯": [5106, 5107, 5106, 0, 0, 0, 0, 0, 0, 0],  # 독포자 x2, 마비 가루

    # === 초보자 구역 보스 ===
    "고블린 족장": [5005, 5006, 5006, 5006, 0, 0, 0, 0, 0, 0],  # 족장의 명령 x1, 분노의 일격 x3

    # === 화염 구역 ===
    "화염 정령": [5010, 5010, 5010, 0, 0, 0, 0, 0, 0, 0],  # 화염구 x3
    "마그마 골렘": [5011, 5011, 0, 0, 0, 0, 0, 0, 0, 0],  # 용암 내뿜기 x2
    "화염 임프": [5012, 5012, 5012, 0, 0, 0, 0, 0, 0, 0],  # 불꽃 연쇄 x3
    "불 박쥐": [5108, 5109, 0, 0, 0, 0, 0, 0, 0, 0],  # 화염 급강하, 불꽃 초음파

    # === 화염 구역 보스 ===
    "화염의 군주": [5013, 5014, 5015, 5013, 5014, 0, 0, 0, 0, 0],  # 지옥불, 화염 폭발, 불의 비

    # === 냉기 구역 ===
    "얼음 정령": [5020, 5020, 5020, 0, 0, 0, 0, 0, 0, 0],  # 빙결 x3
    "서리 늑대": [5021, 5021, 0, 0, 0, 0, 0, 0, 0, 0],  # 냉기 송곳니 x2
    "얼어붙은 좀비": [5110, 5111, 5110, 0, 0, 0, 0, 0, 0, 0],  # 얼어붙은 손톱 x2, 냉기 포옹
    "눈보라 하피": [5023, 5023, 0, 0, 0, 0, 0, 0, 0, 0],  # 눈보라 x2

    # === 냉기 구역 보스 ===
    "서리 마녀": [5022, 5023, 5024, 5022, 5024, 0, 0, 0, 0, 0],  # 절대 영도, 눈보라, 얼음 창

    # === 번개 구역 ===
    "천둥 정령": [5030, 5030, 5030, 0, 0, 0, 0, 0, 0, 0],  # 낙뢰 x3
    "폭풍 하피": [5031, 5031, 0, 0, 0, 0, 0, 0, 0, 0],  # 폭풍 날개 x2
    "번개 늑대": [5030, 5030, 0, 0, 0, 0, 0, 0, 0, 0],  # 낙뢰 x2
    "번개 요정": [5030, 0, 0, 0, 0, 0, 0, 0, 0, 0],  # 낙뢰 x1

    # === 번개 구역 보스 ===
    "천둥의 왕": [5032, 5033, 5034, 5032, 5033, 0, 0, 0, 0, 0],  # 천둥의 심판, 번개 연쇄, 폭풍 소환

    # === 수속성 구역 ===
    "물 정령": [5040, 5040, 5040, 0, 0, 0, 0, 0, 0, 0],  # 수류탄 x3
    "바다뱀": [5040, 5040, 0, 0, 0, 0, 0, 0, 0, 0],  # 수류탄 x2
    "익사한 사제": [5041, 5041, 5041, 0, 0, 0, 0, 0, 0, 0],  # 치유의 파도 x3
    "거대 게": [5112, 5113, 5114, 0, 0, 0, 0, 0, 0, 0],  # 집게 집기, 단단한 껍질, 거품 분사

    # === 수속성 구역 보스 ===
    "심해의 사제": [5042, 5043, 5044, 5042, 5043, 0, 0, 0, 0, 0],  # 해일, 심해의 축복, 익사의 저주

    # === 신성 구역 ===
    "타락한 사제": [5050, 5050, 5050, 0, 0, 0, 0, 0, 0, 0],  # 심판의 빛 x3
    "타락한 기사": [5051, 5051, 0, 0, 0, 0, 0, 0, 0, 0],  # 신성한 일격 x2
    "신성 가고일": [5050, 5050, 0, 0, 0, 0, 0, 0, 0, 0],  # 심판의 빛 x2
    "빛의 정령": [5050, 5050, 5050, 0, 0, 0, 0, 0, 0, 0],  # 심판의 빛 x3

    # === 신성 구역 보스 ===
    "타락한 대주교": [5052, 5053, 5054, 5052, 5053, 0, 0, 0, 0, 0],  # 천벌, 정화의 불꽃, 신성 결계

    # === 암흑 구역 ===
    "스켈레톤 전사": [5060, 5060, 0, 0, 0, 0, 0, 0, 0, 0],  # 뼈 가르기 x2
    "좀비": [5115, 5116, 5117, 0, 0, 0, 0, 0, 0, 0],  # 썩은 손톱, 감염된 물기, 시체 돌진
    "유령": [5061, 5061, 0, 0, 0, 0, 0, 0, 0, 0],  # 빙의 x2
    "망령": [5062, 5062, 5062, 0, 0, 0, 0, 0, 0, 0],  # 생명력 흡수 x3

    # === 암흑 구역 보스 ===
    "리치 킹": [5063, 5064, 5065, 5063, 5065, 0, 0, 0, 0, 0],  # 죽음의 손길, 언데드 군단, 영혼 수확

    # === 용의 둥지 ===
    "어린 드래곤": [5070, 5070, 5070, 0, 0, 0, 0, 0, 0, 0],  # 브레스 x3
    "드래곤 가드": [5071, 5071, 0, 0, 0, 0, 0, 0, 0, 0],  # 수호자의 일격 x2
    "화염 드레이크": [5072, 5072, 5072, 0, 0, 0, 0, 0, 0, 0],  # 화염 브레스 x3
    "번개 드레이크": [5073, 5073, 5073, 0, 0, 0, 0, 0, 0, 0],  # 뇌격 브레스 x3

    # === 용의 둥지 보스 ===
    "고대 드래곤": [5072, 5073, 5074, 5075, 5072, 5073, 0, 0, 0, 0],  # 화염/뇌격 브레스, 드래곤 클로, 용의 포효

    # === 엘리트 던전 ===
    "혼돈의 분신": [5080, 5080, 5080, 0, 0, 0, 0, 0, 0, 0],  # 혼돈의 일격 x3
    "공허의 보행자": [5081, 5081, 0, 0, 0, 0, 0, 0, 0, 0],  # 공허 이동 x2
    "차원의 공포": [5082, 5082, 0, 0, 0, 0, 0, 0, 0, 0],  # 혼돈의 물결 x2
    "엔트로피 위스프": [5080, 0, 0, 0, 0, 0, 0, 0, 0, 0],  # 혼돈의 일격 x1

    # === 엘리트 던전 보스 ===
    "혼돈의 화신": [5082, 5083, 5082, 5083, 0, 0, 0, 0, 0, 0],  # 혼돈의 물결, 차원 분열

    # === 최종 던전 보스 ===
    "심연의 군주": [5090, 5091, 5090, 5091, 0, 0, 0, 0, 0, 0],  # 심연의 나락, 생명 착취
    "심판자": [5092, 5093, 5092, 5093, 0, 0, 0, 0, 0, 0],  # 신의 심판, 정화의 광선
}


async def init_db():
    """데이터베이스 연결 초기화"""
    db_url = f"postgres://{os.getenv('DATABASE_USER')}:{os.getenv('DATABASE_PASSWORD')}@{os.getenv('DATABASE_URL')}:{os.getenv('DATABASE_PORT')}/{os.getenv('DATABASE_TABLE')}"
    await Tortoise.init(
        db_url=db_url,
        modules={"models": ["models"]}
    )


async def add_monster_columns():
    """monster 테이블에 필요한 컬럼들 추가"""
    conn = Tortoise.get_connection("default")

    columns_to_add = [
        ("skill_ids", "JSONB DEFAULT '[]'"),
        ("defense", "INTEGER DEFAULT 0"),
        ("ap_attack", "INTEGER DEFAULT 0"),
        ("ap_defense", "INTEGER DEFAULT 0"),
        ("speed", "INTEGER DEFAULT 10"),
        ("evasion", "INTEGER DEFAULT 0"),
    ]

    for col_name, col_type in columns_to_add:
        try:
            # PostgreSQL: 컬럼 존재 여부 확인
            result = await conn.execute_query(
                "SELECT column_name FROM information_schema.columns "
                f"WHERE table_name = 'monster' AND column_name = '{col_name}'"
            )
            if result[1]:
                print(f"  {col_name} 컬럼이 이미 존재합니다.")
                continue

            # 컬럼 추가
            await conn.execute_query(
                f"ALTER TABLE monster ADD COLUMN {col_name} {col_type}"
            )
            print(f"  {col_name} 컬럼 추가 완료!")

        except Exception as e:
            print(f"  {col_name} 컬럼 추가 중 오류: {e}")
            raise


async def seed_monster_skills():
    """몬스터 전용 스킬 데이터 시드"""
    from models.skill import Skill_Model

    print("\n몬스터 스킬 데이터 시드 시작...")
    created_count = 0
    updated_count = 0

    for skill_data in MONSTER_SKILLS:
        skill, created = await Skill_Model.get_or_create(
            id=skill_data["id"],
            defaults={
                "name": skill_data["name"],
                "description": skill_data["description"],
                "config": skill_data["config"],
            }
        )

        if created:
            created_count += 1
            print(f"  [생성] {skill_data['id']}: {skill_data['name']}")
        else:
            skill.name = skill_data["name"]
            skill.description = skill_data["description"]
            skill.config = skill_data["config"]
            await skill.save()
            updated_count += 1
            print(f"  [갱신] {skill_data['id']}: {skill_data['name']}")

    print(f"완료! 생성: {created_count}, 갱신: {updated_count}, 총: {len(MONSTER_SKILLS)}")


async def update_monster_skills():
    """각 몬스터에 스킬 ID 할당"""
    from models.monster import Monster
    import json

    print("\n몬스터 스킬 할당 시작...")
    conn = Tortoise.get_connection("default")

    updated_count = 0
    not_found = []

    for monster_name, skill_ids in MONSTER_SKILL_MAPPING.items():
        # skill_ids가 비어있으면 빈 배열로
        skill_ids_json = json.dumps(skill_ids if skill_ids else [])

        try:
            # PostgreSQL: $1, $2 형식 사용
            result = await conn.execute_query(
                "UPDATE monster SET skill_ids = $1 WHERE name = $2",
                [skill_ids_json, monster_name]
            )
            # result[0]은 영향받은 행 수
            if result[0] > 0:
                skill_desc = f"{len([s for s in skill_ids if s != 0])}개 스킬" if skill_ids else "스킬 없음"
                print(f"  [갱신] {monster_name}: {skill_desc}")
                updated_count += 1
            else:
                not_found.append(monster_name)
        except Exception as e:
            print(f"  [오류] {monster_name}: {e}")

    print(f"\n완료! 갱신: {updated_count}")
    if not_found:
        print(f"DB에서 찾을 수 없는 몬스터: {', '.join(not_found)}")


async def main():
    """메인 실행"""
    try:
        print("=" * 50)
        print("몬스터 스킬 마이그레이션 시작")
        print("=" * 50)

        await init_db()

        # 1. 컬럼 추가
        print("\n[1/3] 몬스터 스탯 컬럼 추가...")
        await add_monster_columns()

        # 2. 몬스터 스킬 시드
        print("\n[2/3] 몬스터 전용 스킬 시드...")
        await seed_monster_skills()

        # 3. 몬스터에 스킬 할당
        print("\n[3/3] 몬스터 스킬 할당...")
        await update_monster_skills()

        print("\n" + "=" * 50)
        print("마이그레이션 완료!")
        print("=" * 50)

    except Exception as e:
        print(f"\n오류 발생: {e}")
        raise
    finally:
        await Tortoise.close_connections()


if __name__ == "__main__":
    asyncio.run(main())
