"""
config은 있지만 특수능력 설명이 없는 장비에 설명 추가

config을 분석하여 자동으로 설명을 생성합니다.
"""
import csv


# ID별 특수능력 설명
DESCRIPTIONS = {
    1801: "HP 80% 이상 시 공격력 +50%",  # 신앙의 검
    1802: "HP 30% 이하 시 공격력 +100%",  # 어둠을 삼킨 검
    1803: "HP 40~60% 시 주문력 +80%",  # 균형의 지팡이
    1806: "HP 80% 이상 시 방어력 +60%",  # 수호자의 방패검
    1951: "전투 중 매 턴 공격력 +5% (최대 10스택)",  # 살아있는 검
    1952: "적 처치 시 HP 20% 회복",  # 영혼 수집 낫
    1953: "전투 중 매 턴 공격/방어 +3% (최대 15스택)",  # 전투 학습 장갑
    2804: "HP 10% 소모하여 3턴간 공격/방어 +40",  # 희생자의 로브
}


def add_descriptions_to_csv(input_path: str, output_path: str, dry_run: bool = True):
    """
    장비 CSV에 누락된 특수능력 설명 추가

    Args:
        input_path: 입력 CSV 경로
        output_path: 출력 CSV 경로
        dry_run: True면 미리보기만
    """
    rows = []
    stats = {
        "total": 0,
        "updated": 0,
        "skipped": 0,
    }
    updates = []

    with open(input_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames)

        for row in reader:
            stats["total"] += 1
            item_id = int(row['ID'])

            if item_id in DESCRIPTIONS:
                row['특수 효과'] = DESCRIPTIONS[item_id]
                stats["updated"] += 1
                updates.append(f"[{item_id}] {row['이름']}: {DESCRIPTIONS[item_id]}")
            else:
                stats["skipped"] += 1

            rows.append(row)

    # 결과 출력
    print("=" * 80)
    print("누락된 특수능력 설명 추가 결과")
    print("=" * 80)
    print(f"총 장비: {stats['total']}개")
    print(f"설명 추가: {stats['updated']}개")
    print(f"건너뜀: {stats['skipped']}개")
    print()

    if updates:
        print("업데이트 내역:")
        print("-" * 80)
        for update in updates:
            print(update)
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

    input_path = "data/items_equipment.csv"
    output_path = "data/items_equipment.csv"  # 원본 덮어쓰기

    # --commit 전달 시 실제 변환
    dry_run = "--commit" not in sys.argv

    if dry_run:
        print("=" * 80)
        print("🔍 DRY RUN 모드")
        print("=" * 80)
        print("실제 변환: python scripts/add_missing_descriptions.py --commit")
        print()

    add_descriptions_to_csv(input_path, output_path, dry_run=dry_run)


if __name__ == "__main__":
    main()
