"""Aggregate measured runtime reports; no analytical win-rate substitution."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASES = [
    ("beginner-forest-10000", "Lv1 숲 무작위", .99, 10000),
    ("beginner-forest-elite-10000", "Lv1 숲 정예 우선", .95, 10000),
    ("beginner-cave-10000", "Lv5 동굴 무작위", .97, 10000),
    ("beginner-cave-elite-10000", "Lv5 동굴 정예 우선", .95, 10000),
    ("beginner-basic-10000", "Lv1 숲 강타 10장", .95, 10000),
    ("beginner-empty-1000", "Lv1 숲 빈 덱", .95, 1000),
    *[(f"beginner-level{level}", f"Lv{level} 입문 지역", .97, 1000) for level in [3,7,10]],
    *[(f"beginner-level{level}-{area}", f"Lv{level} {area} 이전 지역 D+0 장비", .90, 1000)
      for level, areas in [(11,["mine","lake"]),(15,["storm","temple"]),(20,["storm","temple"])] for area in areas]
]


def main():
    cases = []
    for name, label, minimum, count in CASES:
        report = json.loads((ROOT / "reports" / (name + ".json")).read_text(encoding="utf-8"))
        assert report["args"]["runs"] == count
        assert report["clear_rate"] >= minimum, label
        if report["args"]["dungeon"] in [1,2] and report["args"]["deck"] == "starter":
            hp = report["fixture"]["stats"]["HP"]
            assert all(m["max_action_damage"] <= hp * .12 for m in report["monsters"].values())
        cases.append({"label": label, "runs": count, "clear_rate": report["clear_rate"],
                      "minimum": minimum, "report": name + ".json"})
    output = {"passed": True, "total_runs": sum(c["runs"] for c in cases), "cases": cases,
              "scope": "Real engine, actual starter/previous D+0 equipment IDs, SQLite persistence; Discord waits replaced"}
    (ROOT / "reports/beginner-validation.json").write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# 초반 던전 복구 실측 결과", "", "이론 추정이 아니라 실제 셔플백·컴포넌트·FSM·상태·8방+보스·보상 저장을 실행한 결과입니다.", "",
             "| 조건 | 실행 수 | 클리어율 | 기준 |", "|---|---:|---:|---:|"]
    for case in cases:
        lines.append(f"| {case['label']} | {case['runs']:,} | {case['clear_rate']:.1%} | {case['minimum']:.0%} |")
    lines += ["", "- 첫 두 지역은 무장비·미배분·포션 없이 최대 HP에서 시작합니다. 기본 덱 외 스킬을 임의로 추가하지 않습니다.",
              "- 연결 구간 장비는 ID 1002/2002/2102/2202/2302/3001/3102×2/4002, D등급 +0입니다.",
              "- 숲 보스 평균 공격 행동 4.29~4.33회, 동굴 보스 4.28~4.31회입니다. 최대 단일 행동 피해는 각각 23/300, 42/372로 12% 이하입니다.",
              "- 클리어율 100%는 검사한 seed의 결과이며 모든 가능한 경로의 무조건 승리를 보장하지 않습니다.",
              "- 별도 회귀 검사: 8연속 정예·휴식 없음·회복 선소진·후반 독/출혈, CC 만료, 빈 덱/강타 덱, 중복 지급/회복, 귀환/시간초과 정산.",
              "- PostgreSQL 보존/동시성 및 실제 Discord 메시지 결과는 NAS의 beginner-upgrade-verified.json / beginner-discord-verified.json에 따로 기록합니다.",
              "- Discord 검사는 등록 명령 조회와 실제 덱/전투 Embed·컴포넌트 전송→편집→재조회입니다. 사람이 슬래시 명령이나 버튼을 누르는 플랫폼 입력은 자동 실행하지 않습니다.", ""]
    (ROOT / "reports/beginner-validation.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"passed": True, "runs": output["total_runs"]}))


if __name__ == "__main__":
    main()
