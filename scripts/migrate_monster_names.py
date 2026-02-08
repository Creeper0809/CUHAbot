"""
몬스터 이름 마이그레이션 스크립트

몬스터 이름에서 영어 괄호 표기 제거
예: "슬라임 (Slime)" -> "슬라임"

실행: python scripts/migrate_monster_names.py
"""
import asyncio
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from tortoise import Tortoise

load_dotenv()


# 영어 괄호를 제거하는 매핑 (old_name -> new_name)
NAME_MAPPING = {
    "슬라임 (Slime)": "슬라임",
    "고블린 (Goblin)": "고블린",
    "늑대 (Wolf)": "늑대",
    "독버섯 (Poison Mushroom)": "독버섯",
    "대왕 슬라임 (King Slime)": "대왕 슬라임",
    "숲의 정령왕 (Forest Spirit King)": "숲의 정령왕",
    "동굴 박쥐 (Cave Bat)": "동굴 박쥐",
    "고블린 궁수 (Goblin Archer)": "고블린 궁수",
    "고블린 주술사 (Goblin Shaman)": "고블린 주술사",
    "고블린 족장 (Goblin Chief)": "고블린 족장",
    "불 박쥐 (Fire Bat)": "불 박쥐",
    "화염 정령 (Fire Elemental)": "화염 정령",
    "화염 임프 (Flame Imp)": "화염 임프",
    "얼음 정령 (Ice Elemental)": "얼음 정령",
    "얼어붙은 좀비 (Frozen Zombie)": "얼어붙은 좀비",
    "서리 늑대 (Frost Wolf)": "서리 늑대",
    "마그마 골렘 (Magma Golem)": "마그마 골렘",
    "눈보라 하피 (Snow Harpy)": "눈보라 하피",
    "화염의 군주 (Flame Lord)": "화염의 군주",
    "서리 마녀 (Frost Witch)": "서리 마녀",
    "번개 요정 (Spark Sprite)": "번개 요정",
    "거대 게 (Giant Crab)": "거대 게",
    "천둥 정령 (Thunder Elemental)": "천둥 정령",
    "번개 늑대 (Lightning Wolf)": "번개 늑대",
    "물 정령 (Water Elemental)": "물 정령",
    "폭풍 하피 (Storm Harpy)": "폭풍 하피",
    "바다뱀 (Sea Serpent)": "바다뱀",
    "익사한 사제 (Drowned Priest)": "익사한 사제",
    "폭풍 그리폰 (Storm Griffon)": "폭풍 그리폰",
    "심해 거북 (Abyssal Turtle)": "심해 거북",
    "천둥의 왕 (Thunder King)": "천둥의 왕",
    "심해의 사제 (Abyssal Priest)": "심해의 사제",
    "빛의 정령 (Light Wisp)": "빛의 정령",
    "좀비 (Zombie)": "좀비",
    "타락한 사제 (Corrupted Priest)": "타락한 사제",
    "신성 가고일 (Holy Gargoyle)": "신성 가고일",
    "스켈레톤 전사 (Skeleton Warrior)": "스켈레톤 전사",
    "타락한 기사 (Fallen Knight)": "타락한 기사",
    "유령 (Ghost)": "유령",
    "망령 (Wraith)": "망령",
    "신성 수호상 (Holy Guardian Statue)": "신성 수호상",
    "죽음의 기사 (Death Knight)": "죽음의 기사",
    "타락한 대주교 (Corrupted Archbishop)": "타락한 대주교",
    "리치 킹 (Lich King)": "리치 킹",
    "어린 드래곤 (Dragon Whelp)": "어린 드래곤",
    "화염 드레이크 (Fire Drake)": "화염 드레이크",
    "번개 드레이크 (Thunder Drake)": "번개 드레이크",
    "드래곤 가드 (Dragon Guard)": "드래곤 가드",
    "용의 현자 (Dragon Sage)": "용의 현자",
    "고대 드래곤 (Ancient Dragon)": "고대 드래곤",
    "세계수의 수호자 (Guardian of Yggdrasil)": "세계수의 수호자",
    "엔트로피 위스프 (Entropy Wisp)": "엔트로피 위스프",
    "혼돈의 분신 (Chaos Spawn)": "혼돈의 분신",
    "공허의 보행자 (Void Walker)": "공허의 보행자",
    "차원의 공포 (Dimension Horror)": "차원의 공포",
    "혼돈의 화신 (Avatar of Chaos)": "혼돈의 화신",
    "몰락한 왕 (Fallen King)": "몰락한 왕",
    "마왕 발더스 (Demon King Valdeus)": "마왕 발더스",
    "심연의 군주 (Abyssal Lord)": "심연의 군주",
    "심판자 (The Arbiter)": "심판자",
    "창세의 관찰자 (The Observer of Genesis)": "창세의 관찰자",
    "시간의 망령 (Temporal Wraith)": "시간의 망령",
    "시간 포식자 (Time Eater)": "시간 포식자",
    "시간 골렘 (Chrono Golem)": "시간 골렘",
    "역설 정령 (Paradox Elemental)": "역설 정령",
    "시간의 감시자 (Temporal Watcher)": "시간의 감시자",
    "시간의 수호자 (Temporal Guardian)": "시간의 수호자",
    "공허의 선봉 (Void Harbinger)": "공허의 선봉",
    "엔트로피 야수 (Entropy Beast)": "엔트로피 야수",
    "무(無) 보행자 (Null Walker)": "무(無) 보행자",
    "허무의 화신 (Emptiness Incarnate)": "허무의 화신",
    "공허의 포식자 (Void Predator)": "공허의 포식자",
    "공허의 지배자 (Void Overlord)": "공허의 지배자",
    "차원의 구현체 (Dimensional Incarnation)": "차원의 구현체",
    "심해 리바이어던 (Deep Sea Leviathan)": "심해 리바이어던",
    "생체발광 공포 (Bioluminescent Horror)": "생체발광 공포",
    "심연의 크라켄 새끼 (Kraken Spawn)": "심연의 크라켄 새끼",
    "압력 골렘 (Pressure Golem)": "압력 골렘",
    "심해 아귀 (Abyssal Anglerfish)": "심해 아귀",
    "심해의 크라켄 (Kraken of the Depths)": "심해의 크라켄",
    "각성한 용사 (Awakened Champion)": "각성한 용사",
    "정수 포식자 (Essence Devourer)": "정수 포식자",
    "원소의 아바타 (Elemental Avatar)": "원소의 아바타",
    "원시 수호자 (Primal Guardian)": "원시 수호자",
    "각성의 현자 (Sage of Awakening)": "각성의 현자",
    "깨어난 고대신 (Awakened Ancient God)": "깨어난 고대신",
    "용신 티아마트 (Dragon God Tiamat)": "용신 티아마트",
    "고대 자동인형 (Ancient Automaton)": "고대 자동인형",
    "마법 구조물 (Arcane Construct)": "마법 구조물",
    "폐허의 감시자 (Ruin Sentinel)": "폐허의 감시자",
    "잊힌 문명의 망령 (Lost Civilization Ghost)": "잊힌 문명의 망령",
    "고대 집행자 (Ancient Executor)": "고대 집행자",
    "고대 문명의 수호자 (Guardian of the Lost)": "고대 문명의 수호자",
    "시련의 용사 (Trial Champion)": "시련의 용사",
    "탑의 감시자 (Tower Sentinel)": "탑의 감시자",
    "층 수호자 (Floor Guardian)": "층 수호자",
    "시련의 정령 (Trial Elemental)": "시련의 정령",
    "시련의 검투사 (Trial Gladiator)": "시련의 검투사",
    "탑의 최종 수호자 (Final Keeper of the Tower)": "탑의 최종 수호자",
    "죽음의 지배자 (Lord of Death)": "죽음의 지배자",
    "현실 파편 (Reality Shatter)": "현실 파편",
    "불안정한 존재 (Unstable Entity)": "불안정한 존재",
    "차원 붕괴자 (Dimension Collapser)": "차원 붕괴자",
    "혼돈의 현신 (Chaos Incarnation)": "혼돈의 현신",
    "차원의 균열체 (Dimensional Rift Entity)": "차원의 균열체",
    "차원의 파괴자 (Dimension Destroyer)": "차원의 파괴자",
    "초월한 기사 (Transcendent Knight)": "초월한 기사",
    "승천한 정령 (Ascended Elemental)": "승천한 정령",
    "한계를 넘은 자 (Beyond Champion)": "한계를 넘은 자",
    "한계 돌파자 (Limit Breaker)": "한계 돌파자",
    "초월의 문지기 (Transcendence Gatekeeper)": "초월의 문지기",
    "초월한 자 (The Transcendent One)": "초월한 자",
    "태양신 라 (Sun God Ra)": "태양신 라",
    "몰락한 반신 (Fallen Demigod)": "몰락한 반신",
    "천상의 잔재 (Celestial Remnant)": "천상의 잔재",
    "신성 전사 (Divine Warrior)": "신성 전사",
    "신 살해자 야수 (God Slayer Beast)": "신 살해자 야수",
    "전쟁의 심판관 (War Arbiter)": "전쟁의 심판관",
    "전쟁의 신 아레스 (Ares, God of War)": "전쟁의 신 아레스",
    "원초의 타이탄 (Primordial Titan)": "원초의 타이탄",
    "창조의 아바타 (Creation Avatar)": "창조의 아바타",
    "창세의 뱀 (Genesis Serpent)": "창세의 뱀",
    "기원의 정령 (Origin Elemental)": "기원의 정령",
    "원초의 사자 (Primordial Herald)": "원초의 사자",
    "창조신의 그림자 (Shadow of the Creator)": "창조신의 그림자",
    "원초의 신 (Primordial God)": "원초의 신",
    "창조신 (The Creator)": "창조신",
}


async def init_db():
    """데이터베이스 연결 초기화"""
    db_url = (
        f"postgres://{os.getenv('DATABASE_USER')}:{os.getenv('DATABASE_PASSWORD')}"
        f"@{os.getenv('DATABASE_URL')}:{os.getenv('DATABASE_PORT')}/{os.getenv('DATABASE_TABLE')}"
    )
    await Tortoise.init(
        db_url=db_url,
        modules={"models": ["models"]}
    )


async def migrate_monster_names():
    """몬스터 이름에서 영어 괄호 표기 제거"""
    conn = Tortoise.get_connection("default")

    updated_count = 0
    not_found = []

    for old_name, new_name in NAME_MAPPING.items():
        try:
            result = await conn.execute_query(
                "UPDATE monster SET name = $1 WHERE name = $2",
                [new_name, old_name]
            )
            if result[0] > 0:
                print(f"  [갱신] {old_name} -> {new_name}")
                updated_count += 1
            else:
                not_found.append(old_name)
        except Exception as e:
            print(f"  [오류] {old_name}: {e}")

    print(f"\n갱신: {updated_count}개")
    if not_found:
        print(f"DB에서 찾을 수 없는 몬스터 ({len(not_found)}개):")
        for name in not_found:
            print(f"  - {name}")


async def main():
    """메인 실행"""
    try:
        print("=" * 50)
        print("몬스터 이름 마이그레이션")
        print("영어 괄호 표기 제거")
        print("=" * 50)

        await init_db()
        await migrate_monster_names()

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
