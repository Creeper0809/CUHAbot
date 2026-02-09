"""
업적 데이터 시딩 스크립트

업적 시스템의 초기 데이터를 생성합니다.
"""
import asyncio
import csv
import json
import logging
import os
import sys

# 프로젝트 루트를 sys.path에 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dotenv import load_dotenv
from tortoise import Tortoise

from models.achievement import Achievement, AchievementCategory

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv('DATABASE_URL')
DATABASE_USER = os.getenv('DATABASE_USER')
DATABASE_PASSWORD = os.getenv('DATABASE_PASSWORD')
DATABASE_PORT = int(os.getenv('DATABASE_PORT') or 0)
DATABASE_TABLE = os.getenv('DATABASE_TABLE')


def load_achievements_from_csv() -> list[dict]:
    """CSV 파일에서 업적 데이터 로드"""
    csv_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'achievements.csv')

    achievements = []

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)

        for row in reader:
            # JSON 필드 파싱
            objective_config = json.loads(row['objective_config'])
            reward_config = json.loads(row['reward_config'])

            # 선행 업적 ID 처리
            prerequisite_id = None
            if row['prerequisite_achievement_id']:
                try:
                    prerequisite_id = int(row['prerequisite_achievement_id'])
                except ValueError:
                    pass

            # 칭호 처리
            title_name = row['title_name'] if row['title_name'] else None

            achievement_data = {
                "name": row['name'],
                "category": AchievementCategory(row['category']),
                "tier": int(row['tier']),
                "description": row['description'],
                "objective_config": objective_config,
                "reward_config": reward_config,
                "prerequisite_achievement_id": prerequisite_id,
                "title_name": title_name,
            }

            achievements.append(achievement_data)

    logger.info(f"CSV에서 {len(achievements)}개 업적 로드 완료")
    return achievements


async def seed_achievements():
    """업적 데이터 시딩"""
    # DB 초기화
    await Tortoise.init(
        db_url=f"postgres://{DATABASE_USER}:{DATABASE_PASSWORD}@{DATABASE_URL}:{DATABASE_PORT}/{DATABASE_TABLE}",
        modules={"models": ["models"]}
    )

    logger.info("업적 데이터 시딩 시작...")

    # CSV에서 업적 데이터 로드
    achievements = load_achievements_from_csv()

    # 기존 업적 삭제 (선택적)
    # await Achievement.all().delete()
    # logger.info("기존 업적 데이터 삭제 완료")

    # prerequisite_achievement_id 매핑을 위한 ID 맵
    id_map = {}

    for idx, ach_data in enumerate(achievements, start=1):
        # prerequisite_achievement_id 해결
        if "prerequisite_achievement_id" in ach_data and ach_data["prerequisite_achievement_id"]:
            original_id = ach_data["prerequisite_achievement_id"]
            ach_data["prerequisite_achievement_id"] = id_map.get(original_id)

        try:
            achievement = await Achievement.create(**ach_data)
            id_map[idx] = achievement.id
            logger.info(f"✅ {achievement.name} {achievement.tier_name} (ID: {achievement.id})")
        except Exception as e:
            logger.error(f"❌ {ach_data['name']} {ach_data['tier']} 생성 실패: {e}")

    logger.info(f"업적 데이터 시딩 완료! 총 {len(achievements)}개 업적 생성")

    await Tortoise.close_connections()


if __name__ == "__main__":
    asyncio.run(seed_achievements())
