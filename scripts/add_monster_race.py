"""
몬스터 종족(race) 필드 추가 및 자동 할당

몬스터 이름 패턴을 기반으로 종족을 자동 할당합니다.
"""
import csv
from typing import Dict, List, Tuple


# 종족 판별 규칙 (우선순위 순서대로)
RACE_PATTERNS = [
    # 슬라임
    (["슬라임"], "슬라임"),

    # 고블린
    (["고블린"], "고블린"),

    # 드래곤
    (["드래곤", "드레이크", "용"], "드래곤"),

    # 언데드
    (["좀비", "스켈레톤", "유령", "망령", "리치", "언데드", "해골"], "언데드"),

    # 정령
    (["정령", "위스프", "엔트", "트리", "수호자", "아바타", "고대신", "신"], "정령"),

    # 골렘/기계
    (["골렘", "가고일", "수호상", "석상", "큐브", "자동인형", "기계", "로봇", "감시자", "구조물"], "골렘"),

    # 인간형
    (["사제", "기사", "주술사", "궁수", "전사", "족장", "대주교", "왕", "가드", "현자",
     "군주", "마녀", "요정", "점술사", "예언자", "왕비", "귀족", "도적", "암살자",
     "용사", "영웅", "성자", "순교자", "광신도", "심판자", "관찰자", "추종자",
     "집행자", "검투사", "전령", "사도"], "인간형"),

    # 마수 (악마/몬스터)
    (["임프", "하피", "그리폰", "악마", "데몬", "마왕", "드레드", "나이트메어",
     "바포메트", "베히모스", "리바이어던", "공포", "분신", "화신", "보행자",
     "포식자", "파괴자", "지배자", "혼돈", "공허", "심연", "차원"], "마수"),

    # 야수
    (["늑대", "박쥐", "버섯", "곰", "호랑이", "사자", "독사", "전갈", "거미"], "야수"),

    # 수생
    (["게", "뱀", "거북", "상어", "문어", "크라켄", "세이렌", "아귀"], "수생"),
]


def determine_race(monster_name: str) -> str:
    """
    몬스터 이름으로 종족 판별

    Args:
        monster_name: 몬스터 이름

    Returns:
        종족 이름 (슬라임/고블린/언데드/드래곤/마수/정령/골렘/인간형/수생/야수/미지)
    """
    for keywords, race in RACE_PATTERNS:
        for keyword in keywords:
            if keyword in monster_name:
                return race

    # 매칭 실패 시 기본값
    return "미지"


def add_race_to_csv(input_path: str, output_path: str, dry_run: bool = True):
    """
    몬스터 CSV에 종족 컬럼 추가 및 할당

    Args:
        input_path: 입력 CSV 경로
        output_path: 출력 CSV 경로
        dry_run: True면 미리보기만
    """
    rows = []
    stats = {
        "total": 0,
        "슬라임": 0,
        "고블린": 0,
        "드래곤": 0,
        "언데드": 0,
        "정령": 0,
        "골렘": 0,
        "인간형": 0,
        "마수": 0,
        "야수": 0,
        "수생": 0,
        "미지": 0,
    }

    race_examples = {}

    with open(input_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames)

        # 종족 컬럼 추가 (속성 다음에)
        if '종족' not in fieldnames:
            # 속성 컬럼 찾기
            if '속성' in fieldnames:
                idx = fieldnames.index('속성')
                fieldnames.insert(idx + 1, '종족')
            else:
                fieldnames.append('종족')

        for row in reader:
            stats["total"] += 1
            monster_name = row['이름']

            # 종족 자동 할당
            race = determine_race(monster_name)
            row['종족'] = race

            # 통계
            stats[race] += 1

            # 예시 수집 (각 종족당 5개까지)
            if race not in race_examples:
                race_examples[race] = []
            if len(race_examples[race]) < 5:
                race_examples[race].append(monster_name)

            rows.append(row)

    # 결과 출력
    print("=" * 80)
    print("몬스터 종족 할당 결과")
    print("=" * 80)
    print(f"총 몬스터: {stats['total']}마리")
    print()

    # 종족별 통계
    print("종족별 분포:")
    print("-" * 80)
    for race in ["슬라임", "고블린", "드래곤", "언데드", "정령", "골렘", "인간형", "마수", "야수", "수생", "미지"]:
        count = stats[race]
        if count > 0:
            examples = ", ".join(race_examples[race])
            print(f"{race:8s}: {count:3d}마리 - {examples}")
    print()

    # 파일 저장
    if not dry_run:
        with open(output_path, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        print(f"✅ 저장 완료: {output_path}")
    else:
        print("⚠️ Dry run 모드 - 실제 파일은 변경되지 않았습니다.")
        print(f"   실제 변환하려면 --commit 옵션을 사용하세요.")


def main():
    import sys

    input_path = "data/monsters.csv"
    output_path = "data/monsters.csv"  # 원본 덮어쓰기

    # --commit 전달 시 실제 변환
    dry_run = "--commit" not in sys.argv

    if dry_run:
        print("=" * 80)
        print("🔍 DRY RUN 모드")
        print("=" * 80)
        print("실제 변환: python scripts/add_monster_race.py --commit")
        print()

    add_race_to_csv(input_path, output_path, dry_run=dry_run)


if __name__ == "__main__":
    main()
