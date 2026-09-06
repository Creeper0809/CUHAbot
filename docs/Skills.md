# Skill Ecosystem V3

이 문서는 `data/skill_design/`의 수작업 계약과 실행 컴포넌트에서 생성됩니다. `data/skills.csv`는 결과물이며 설계 원본이 아닙니다.

- 전체 스킬: 647 (플레이어 326 / 몬스터 321)
- 몬스터 행동 세트: 128 (일반 72 / 정예 23 / 보스 33)
- 플레이어 셔플백은 순서 보정 없이 유지하며, 생성기/소비기 장수 비율이 조건 성립률을 결정합니다.
- 조건이 먼저 나오면 특수효과는 생략되고 계약에 기록된 기본 피해·회복·방어 효과만 적용됩니다.
- 같은 패시브 ID는 중첩되지 않으므로 두 슬롯에 편성할 수 없습니다.

## 전투 자원 연결

| 계열 | 생성 자원 | 대표 생성기 | 대표 소비기 |
|---|---|---|---|
| 물리 | 기세 | 1001 강타 | 8504 출혈 폭발 |
| 화염 | 불씨 | 1101 화염구, 8001 불씨 키우기 | 8003 화상 폭발 |
| 냉기 | 서리 | 1201 얼음 화살 | 8102 빙결 분쇄 |
| 번개 | 전하 | 1301 전격 | 8121 천둥 낙뢰 |
| 수속성 | 조류 | 1401 물의 창 | 1409 생명의 원천 |
| 신성 | 신념 | 1501 빛의 화살 | 8405 성스러운 폭발 |
| 암흑 | 영혼 | 1601 암흑 화살 | 8303 저주 수확 |

## 역할 분포

| 범위:역할 | 개수 |
|---|---:|
| monster:passive | 33 |
| monster:phase_capstone | 4 |
| monster:pressure | 192 |
| monster:punish | 10 |
| monster:recovery | 52 |
| monster:setup | 20 |
| monster:summon | 10 |
| player:basic | 9 |
| player:bridge | 28 |
| player:converter | 31 |
| player:defender | 12 |
| player:engine | 35 |
| player:finisher | 53 |
| player:payoff | 38 |
| player:primer | 50 |
| player:stacker | 23 |
| player:sustain | 30 |
| player:utility | 17 |

## 계열 분포

| 범위:계열 | 개수 |
|---|---:|
| monster:fire_combustion | 32 |
| monster:frost_shatter | 13 |
| monster:holy_judgement | 39 |
| monster:neutral_technique | 154 |
| monster:neutral_utility | 7 |
| monster:shadow_sacrifice | 44 |
| monster:storm_overload | 13 |
| monster:tide_cycle | 19 |
| player:cross_family | 1 |
| player:fire_combustion | 24 |
| player:frost_shatter | 22 |
| player:holy_judgement | 29 |
| player:neutral_technique | 72 |
| player:neutral_utility | 93 |
| player:shadow_sacrifice | 39 |
| player:storm_overload | 23 |
| player:tide_cycle | 23 |

## 검증 산출물

- `reports/skill_ecosystem_v3.json`: 647개 기존값·신규값·변경 이유·검증 결과
- `reports/skill_ecosystem_v3.md`: ID별 요약 표
- `data/monster_action_profiles.json`: 전조·실행·회복·페이즈 전이 원본

- `data/monster_skill_assignments.json`: 기존 미연결 65개 스킬의 명시적 몬스터·페이즈 배정
