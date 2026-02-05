# 던전 시스템 (Dungeon System)

## 개요

던전은 플레이어가 탐험하며 몬스터와 전투하고 보물을 획득하는 핵심 컨텐츠입니다.

---

## 던전 분류

### 던전 타입
| 타입 | 설명 | 특징 |
|------|------|------|
| Normal | 일반 던전 | 자유 입장, 기본 보상 |
| Elite | 엘리트 던전 | 입장권 필요, 강화된 보상 |
| Boss | 보스 던전 | 주간 1회, 보스 직행 |
| Raid | 레이드 던전 | 다인 협동, 최고 보상 |

---

## 던전 목록

### 🌲 초보자 구역 (Lv.1-10)

#### 1. 잊혀진 숲 (Forgotten Forest)
| 속성 | 값 |
|------|-----|
| ID | 1 |
| 권장 레벨 | 1-5 |
| 주요 속성 | 없음 |
| 설명 | 마을 근처의 안전한 숲. 초보 모험가의 첫 발걸음 |

**인카운터 테이블**
| 타입 | 값 | 확률 |
|------|-----|------|
| monster | slime | 40% |
| monster | goblin | 30% |
| monster | wolf | 20% |
| lootbox | wooden_chest | 10% |

**드롭 아이템**: 나무 장비 세트, 초급 포션

---

#### 2. 고블린 동굴 (Goblin Cave)
| 속성 | 값 |
|------|-----|
| ID | 2 |
| 권장 레벨 | 5-10 |
| 주요 속성 | 없음 |
| 설명 | 고블린들이 점거한 어두운 동굴 |

**인카운터 테이블**
| 타입 | 값 | 확률 |
|------|-----|------|
| monster | goblin | 35% |
| monster | goblin_archer | 25% |
| monster | goblin_shaman | 15% |
| monster | cave_bat | 15% |
| lootbox | iron_chest | 10% |

**보스**: 고블린 족장 (Goblin Chief)
**드롭 아이템**: 철제 장비, 고블린 토템

---

### ⚔️ 중급 구역 (Lv.11-20)

#### 3. 불타는 광산 (Burning Mine)
| 속성 | 값 |
|------|-----|
| ID | 3 |
| 권장 레벨 | 11-15 |
| 주요 속성 | 🔥 화염 |
| 설명 | 용암이 흐르는 위험한 광산. 화염 저항 필수 |

**인카운터 테이블**
| 타입 | 값 | 확률 |
|------|-----|------|
| monster | fire_elemental | 30% |
| monster | magma_golem | 25% |
| monster | flame_imp | 20% |
| monster | fire_bat | 15% |
| lootbox | scorched_chest | 10% |

**보스**: 화염의 군주 (Flame Lord)
**드롭 아이템**: 화염 장비 세트, 용암 결정

---

#### 4. 얼어붙은 호수 (Frozen Lake)
| 속성 | 값 |
|------|-----|
| ID | 4 |
| 권장 레벨 | 11-15 |
| 주요 속성 | ❄️ 냉기 |
| 설명 | 영원히 얼어붙은 호수. 냉기 저항 권장 |

**인카운터 테이블**
| 타입 | 값 | 확률 |
|------|-----|------|
| monster | ice_elemental | 30% |
| monster | frost_wolf | 25% |
| monster | frozen_zombie | 20% |
| monster | snow_harpy | 15% |
| lootbox | frozen_chest | 10% |

**보스**: 서리 마녀 (Frost Witch)
**드롭 아이템**: 냉기 장비 세트, 영원의 얼음

---

#### 5. 폭풍의 봉우리 (Storm Peak)
| 속성 | 값 |
|------|-----|
| ID | 5 |
| 권장 레벨 | 15-20 |
| 주요 속성 | ⚡ 번개 |
| 설명 | 끊임없이 번개가 치는 산봉우리 |

**인카운터 테이블**
| 타입 | 값 | 확률 |
|------|-----|------|
| monster | thunder_elemental | 30% |
| monster | storm_harpy | 25% |
| monster | lightning_wolf | 20% |
| monster | spark_sprite | 15% |
| lootbox | storm_chest | 10% |

**보스**: 천둥의 왕 (Thunder King)
**드롭 아이템**: 번개 장비 세트, 뇌전석

---

#### 6. 수몰된 신전 (Sunken Temple)
| 속성 | 값 |
|------|-----|
| ID | 6 |
| 권장 레벨 | 15-20 |
| 주요 속성 | 💧 수속성 |
| 설명 | 바다 밑에 가라앉은 고대 신전 |

**인카운터 테이블**
| 타입 | 값 | 확률 |
|------|-----|------|
| monster | water_elemental | 30% |
| monster | sea_serpent | 25% |
| monster | drowned_priest | 20% |
| monster | giant_crab | 15% |
| lootbox | coral_chest | 10% |

**보스**: 심해의 사제 (Abyssal Priest)
**드롭 아이템**: 수속성 장비 세트, 심해 진주

---

### 🏰 고급 구역 (Lv.21-30)

#### 7. 성스러운 대성당 (Holy Cathedral)
| 속성 | 값 |
|------|-----|
| ID | 7 |
| 권장 레벨 | 21-25 |
| 주요 속성 | ✨ 신성 |
| 설명 | 타락한 성직자들이 점거한 대성당 |

**인카운터 테이블**
| 타입 | 값 | 확률 |
|------|-----|------|
| monster | corrupted_priest | 30% |
| monster | fallen_knight | 25% |
| monster | holy_gargoyle | 20% |
| monster | light_wisp | 15% |
| lootbox | blessed_chest | 10% |

**보스**: 타락한 대주교 (Corrupted Archbishop)
**드롭 아이템**: 신성 장비 세트, 정화된 성수

---

#### 8. 어둠의 묘지 (Dark Cemetery)
| 속성 | 값 |
|------|-----|
| ID | 8 |
| 권장 레벨 | 21-25 |
| 주요 속성 | 🌑 암흑 |
| 설명 | 언데드가 들끓는 저주받은 묘지 |

**인카운터 테이블**
| 타입 | 값 | 확률 |
|------|-----|------|
| monster | skeleton_warrior | 30% |
| monster | zombie | 25% |
| monster | ghost | 20% |
| monster | wraith | 15% |
| lootbox | cursed_chest | 10% |

**보스**: 리치 킹 (Lich King)
**드롭 아이템**: 암흑 장비 세트, 영혼석

---

#### 9. 용의 둥지 (Dragon's Nest)
| 속성 | 값 |
|------|-----|
| ID | 9 |
| 권장 레벨 | 26-30 |
| 주요 속성 | 복합 (화염/번개) |
| 설명 | 드래곤들이 서식하는 위험한 영역 |

**인카운터 테이블**
| 타입 | 값 | 확률 |
|------|-----|------|
| monster | dragon_whelp | 30% |
| monster | dragon_guard | 25% |
| monster | fire_drake | 20% |
| monster | thunder_drake | 15% |
| lootbox | dragon_chest | 10% |

**보스**: 고대 드래곤 (Ancient Dragon)
**드롭 아이템**: 드래곤 장비 세트, 드래곤 비늘

---

### 👑 엘리트 구역 (Lv.31-40)

#### 10. 혼돈의 균열 (Chaos Rift)
| 속성 | 값 |
|------|-----|
| ID | 10 |
| 권장 레벨 | 31-35 |
| 주요 속성 | 복합 (모든 속성) |
| 타입 | Elite |
| 설명 | 차원의 틈새에서 쏟아지는 혼돈의 존재들 |

**인카운터 테이블**
| 타입 | 값 | 확률 |
|------|-----|------|
| monster | chaos_spawn | 30% |
| monster | void_walker | 25% |
| monster | dimension_horror | 20% |
| monster | entropy_wisp | 15% |
| lootbox | void_chest | 10% |

**보스**: 혼돈의 화신 (Avatar of Chaos)
**드롭 아이템**: 혼돈 장비 세트, 차원 파편

---

#### 11. 잊혀진 왕국 (Forgotten Kingdom)
| 속성 | 값 |
|------|-----|
| ID | 11 |
| 권장 레벨 | 35-40 |
| 주요 속성 | 신성/암흑 |
| 타입 | Elite |
| 설명 | 멸망한 고대 왕국의 폐허 |

**인카운터 테이블**
| 타입 | 값 | 확률 |
|------|-----|------|
| monster | ancient_guardian | 30% |
| monster | phantom_knight | 25% |
| monster | cursed_mage | 20% |
| monster | soul_eater | 15% |
| lootbox | royal_chest | 10% |

**보스**: 몰락한 왕 (Fallen King)
**드롭 아이템**: 왕국 장비 세트, 왕의 인장

---

### 🌟 최종 구역 (Lv.41-50)

#### 12. 심연의 궁전 (Palace of the Abyss)
| 속성 | 값 |
|------|-----|
| ID | 12 |
| 권장 레벨 | 41-45 |
| 주요 속성 | 암흑 |
| 타입 | Elite |
| 설명 | 심연의 지배자가 통치하는 어둠의 궁전 |

**인카운터 테이블**
| 타입 | 값 | 확률 |
|------|-----|------|
| monster | abyssal_demon | 30% |
| monster | shadow_assassin | 25% |
| monster | dark_sorcerer | 20% |
| monster | nightmare | 15% |
| lootbox | abyssal_chest | 10% |

**보스**: 심연의 군주 (Abyssal Lord)
**드롭 아이템**: 심연 장비 세트, 심연의 심장

---

#### 13. 천상의 탑 (Celestial Tower)
| 속성 | 값 |
|------|-----|
| ID | 13 |
| 권장 레벨 | 45-50 |
| 주요 속성 | 신성 |
| 타입 | Elite |
| 설명 | 천상에 닿은 고대의 탑. 최강의 시련이 기다린다 |

**인카운터 테이블**
| 타입 | 값 | 확률 |
|------|-----|------|
| monster | celestial_guardian | 30% |
| monster | seraph_knight | 25% |
| monster | divine_construct | 20% |
| monster | light_elemental | 15% |
| lootbox | celestial_chest | 10% |

**보스**: 심판자 (The Arbiter)
**드롭 아이템**: 천상 장비 세트, 심판의 깃털

---

### 🌀 차원 균열 구역 (Lv.51-60)

#### 14. 시공의 틈새 (Temporal Rift)
| 속성 | 값 |
|------|-----|
| ID | 14 |
| 권장 레벨 | 51-55 |
| 주요 속성 | 복합 (시간) |
| 타입 | Elite |
| 설명 | 시간의 흐름이 뒤틀린 차원의 틈새 |

**인카운터 테이블**
| 타입 | 값 | 확률 |
|------|-----|------|
| monster | temporal_wraith | 30% |
| monster | chrono_golem | 25% |
| monster | time_eater | 20% |
| monster | paradox_elemental | 17% |
| lootbox | temporal_chest | 8% |

**환경 효과**: 시간 왜곡 - 버프/디버프 지속시간 ±50% 랜덤 변동
**보스**: 시간의 수호자 (Temporal Guardian)
**드롭 아이템**: 시공 장비 세트, 시간의 결정

---

#### 15. 공허의 심연 (Void Abyss)
| 속성 | 값 |
|------|-----|
| ID | 15 |
| 권장 레벨 | 55-60 |
| 주요 속성 | 암흑/공허 |
| 타입 | Elite |
| 설명 | 모든 빛이 사라진 공허의 끝 |

**인카운터 테이블**
| 타입 | 값 | 확률 |
|------|-----|------|
| monster | void_harbinger | 30% |
| monster | null_walker | 25% |
| monster | emptiness_incarnate | 20% |
| monster | entropy_beast | 17% |
| lootbox | void_essence_chest | 8% |

**환경 효과**: 공허의 잠식 - 매 5턴마다 최대 HP의 5% 흡수
**보스**: 공허의 지배자 (Void Overlord)
**드롭 아이템**: 공허 장비 세트, 공허의 핵

---

### 🌊 심연 구역 (Lv.61-70)

#### 16. 깊은 심해 (Abyssal Depths)
| 속성 | 값 |
|------|-----|
| ID | 16 |
| 권장 레벨 | 61-65 |
| 주요 속성 | 💧 수속성/암흑 |
| 타입 | Elite |
| 설명 | 빛조차 닿지 않는 심해의 최심부 |

**인카운터 테이블**
| 타입 | 값 | 확률 |
|------|-----|------|
| monster | deep_sea_leviathan | 28% |
| monster | abyssal_kraken_spawn | 25% |
| monster | pressure_golem | 22% |
| monster | bioluminescent_horror | 18% |
| lootbox | deep_sea_chest | 7% |

**환경 효과**: 수압 - 물리 방어력 +20%, 이동속도 -30%
**보스**: 심해의 크라켄 (Kraken of the Depths)
**드롭 아이템**: 심해 장비 세트, 심연의 눈동자

---

#### 17. 각성의 제단 (Altar of Awakening)
| 속성 | 값 |
|------|-----|
| ID | 17 |
| 권장 레벨 | 65-70 |
| 주요 속성 | 복합 (모든 속성) |
| 타입 | Elite |
| 설명 | 잠든 힘을 깨우는 고대의 제단 |

**인카운터 테이블**
| 타입 | 값 | 확률 |
|------|-----|------|
| monster | awakened_champion | 28% |
| monster | elemental_avatar | 25% |
| monster | primal_guardian | 22% |
| monster | essence_devourer | 18% |
| lootbox | awakening_chest | 7% |

**환경 효과**: 각성의 기운 - 모든 스킬 데미지 +15%, 받는 피해 +15%
**보스**: 깨어난 고대신 (Awakened Ancient God)
**드롭 아이템**: 각성 장비 세트, 각성의 정수, [각성 스킬북]

---

### 🏛️ 고대 유적 구역 (Lv.71-80)

#### 18. 잊혀진 문명의 폐허 (Ruins of the Lost Civilization)
| 속성 | 값 |
|------|-----|
| ID | 18 |
| 권장 레벨 | 71-75 |
| 주요 속성 | 복합 |
| 타입 | Elite |
| 설명 | 신들조차 잊은 초고대 문명의 유적 |

**인카운터 테이블**
| 타입 | 값 | 확률 |
|------|-----|------|
| monster | ancient_automaton | 28% |
| monster | ruin_sentinel | 25% |
| monster | lost_civilization_ghost | 22% |
| monster | arcane_construct | 18% |
| lootbox | ancient_relic_chest | 7% |

**환경 효과**: 고대의 저주 - 힐 효율 -30%, 경험치 +50%
**보스**: 고대 문명의 수호자 (Guardian of the Lost)
**드롭 아이템**: 고대 유물 장비 세트, 잊혀진 기술의 조각

---

#### 19. 시련의 탑 100층 (Tower of Trials - 100F)
| 속성 | 값 |
|------|-----|
| ID | 19 |
| 권장 레벨 | 75-80 |
| 주요 속성 | 무작위 |
| 타입 | Elite (층별 변동) |
| 설명 | 매 층마다 다른 시련이 기다리는 무한의 탑 |

**인카운터 테이블** (층에 따라 변동)
| 타입 | 값 | 확률 |
|------|-----|------|
| monster | trial_champion | 30% |
| monster | floor_guardian | 25% |
| monster | trial_elemental | 20% |
| monster | tower_sentinel | 18% |
| lootbox | trial_chest | 7% |

**환경 효과**: 시련의 규칙 - 매 10층마다 특수 조건 부여
**보스**: 탑의 최종 수호자 (Final Keeper of the Tower)
**드롭 아이템**: 시련 장비 세트, 시련의 증표, [유물 장비 선택권]

---

### 🔥 혼돈의 영역 (Lv.81-90)

#### 20. 붕괴하는 차원 (Collapsing Dimension)
| 속성 | 값 |
|------|-----|
| ID | 20 |
| 권장 레벨 | 81-85 |
| 주요 속성 | 혼돈 |
| 타입 | Elite |
| 설명 | 존재 자체가 붕괴하고 있는 차원 |

**인카운터 테이블**
| 타입 | 값 | 확률 |
|------|-----|------|
| monster | reality_shatter | 28% |
| monster | dimension_collapser | 25% |
| monster | chaos_incarnation | 22% |
| monster | unstable_entity | 18% |
| lootbox | chaos_fragment_chest | 7% |

**환경 효과**: 차원 붕괴 - 매 턴 랜덤 디버프, 50% 확률로 랜덤 버프
**보스**: 차원의 파괴자 (Dimension Destroyer)
**드롭 아이템**: 혼돈 장비 세트, 차원 붕괴의 핵

---

#### 21. 초월자의 영역 (Realm of Transcendence)
| 속성 | 값 |
|------|-----|
| ID | 21 |
| 권장 레벨 | 85-90 |
| 주요 속성 | 초월 |
| 타입 | Elite |
| 설명 | 한계를 초월한 자들만이 도달할 수 있는 영역 |

**인카운터 테이블**
| 타입 | 값 | 확률 |
|------|-----|------|
| monster | transcendent_knight | 28% |
| monster | beyond_champion | 25% |
| monster | limit_breaker | 22% |
| monster | ascended_elemental | 18% |
| lootbox | transcendence_chest | 7% |

**환경 효과**: 초월의 시험 - 모든 스탯 -10%, 생존 시 영구 버프 획득
**보스**: 초월한 자 (The Transcendent One)
**드롭 아이템**: 초월 장비 세트, 초월의 정수, [초월 시스템 해금]

---

### ⭐ 신계 구역 (Lv.91-100)

#### 22. 신들의 전장 (Battlefield of Gods)
| 속성 | 값 |
|------|-----|
| ID | 22 |
| 권장 레벨 | 91-95 |
| 주요 속성 | 신성/혼돈 |
| 타입 | Elite |
| 설명 | 신들이 전쟁을 벌인 전설의 전장 |

**인카운터 테이블**
| 타입 | 값 | 확률 |
|------|-----|------|
| monster | fallen_demigod | 28% |
| monster | divine_warrior | 25% |
| monster | god_slayer_beast | 22% |
| monster | celestial_remnant | 18% |
| lootbox | divine_chest | 7% |

**환경 효과**: 신성한 전투 - 모든 피해 +30%, 회복량 +30%
**보스**: 전쟁의 신 아레스 (Ares, God of War)
**드롭 아이템**: 신성 장비 세트, 신의 무기 조각

---

#### 23. 창세의 정원 (Garden of Genesis)
| 속성 | 값 |
|------|-----|
| ID | 23 |
| 권장 레벨 | 95-100 |
| 주요 속성 | 창세 |
| 타입 | Elite (최종) |
| 설명 | 세계가 시작된 곳. 모든 것의 기원 |

**인카운터 테이블**
| 타입 | 값 | 확률 |
|------|-----|------|
| monster | primordial_titan | 28% |
| monster | genesis_serpent | 25% |
| monster | origin_elemental | 22% |
| monster | creation_avatar | 18% |
| lootbox | genesis_chest | 7% |

**환경 효과**: 창세의 힘 - 모든 스킬 위력 2배, 모든 피해 2배
**보스**: 창조신의 그림자 (Shadow of the Creator)
**드롭 아이템**: 신화 장비 세트, 창세의 씨앗, [신화 등급 스킬북]

---

## 레이드 던전

### 🐉 레이드 1: 세계수의 뿌리 (Roots of Yggdrasil)
| 속성 | 값 |
|------|-----|
| ID | 101 |
| 권장 레벨 | 30+ |
| 권장 인원 | 4명 |
| 주간 리셋 | 월요일 00:00 |

**페이즈 구성**
1. 페이즈 1: 부패한 뿌리 처치
2. 페이즈 2: 정화의 시련
3. 페이즈 3: 세계수의 수호자

**레이드 보스**: 세계수의 수호자 (Guardian of Yggdrasil)
**드롭 아이템**: 세계수 장비 세트, 세계수의 잎

---

### 👹 레이드 2: 마왕성 (Demon King's Castle)
| 속성 | 값 |
|------|-----|
| ID | 102 |
| 권장 레벨 | 40+ |
| 권장 인원 | 4명 |
| 주간 리셋 | 월요일 00:00 |

**페이즈 구성**
1. 페이즈 1: 성문 돌파 (마왕군 격퇴)
2. 페이즈 2: 사천왕 격파 (4 미니보스)
3. 페이즈 3: 마왕과의 결전

**레이드 보스**: 마왕 발더스 (Demon King Valdeus)
**드롭 아이템**: 마왕 장비 세트, 마왕의 혼

---

### 🌌 레이드 3: 창세의 균열 (Genesis Rift)
| 속성 | 값 |
|------|-----|
| ID | 103 |
| 권장 레벨 | 50 |
| 권장 인원 | 4명 |
| 주간 리셋 | 월요일 00:00 |

**페이즈 구성**
1. 페이즈 1: 차원의 파수꾼
2. 페이즈 2: 시간의 역류
3. 페이즈 3: 창세의 존재

**레이드 보스**: 창세의 관찰자 (The Observer of Genesis)
**드롭 아이템**: 창세 장비 세트 (최고 등급), 창세의 파편

---

### 🌌 레이드 4: 차원의 심장 (Heart of Dimensions)
| 속성 | 값 |
|------|-----|
| ID | 104 |
| 권장 레벨 | 60+ |
| 권장 인원 | 4명 |
| 주간 리셋 | 월요일 00:00 |

**페이즈 구성**
1. 페이즈 1: 차원 문지기 격파 (3명의 미니보스)
2. 페이즈 2: 차원 핵 안정화 (퍼즐 기믹)
3. 페이즈 3: 차원의 심장과 융합한 존재

**레이드 보스**: 차원의 구현체 (Dimensional Incarnation)
**드롭 아이템**: 차원 장비 세트 (SS 등급), 차원의 심장 파편

---

### 🐲 레이드 5: 용신의 무덤 (Tomb of the Dragon God)
| 속성 | 값 |
|------|-----|
| ID | 105 |
| 권장 레벨 | 70+ |
| 권장 인원 | 4명 |
| 주간 리셋 | 월요일 00:00 |

**페이즈 구성**
1. 페이즈 1: 5용의 시련 (5마리 드래곤 순차 격파)
2. 페이즈 2: 용신의 눈 (5속성 동시 공략 퍼즐)
3. 페이즈 3: 부활한 용신과의 결전

**레이드 보스**: 용신 티아마트 (Dragon God Tiamat)
**드롭 아이템**: 용신 장비 세트 (SS~SSS 등급), 용신의 비늘, [각성 스킬 재료]

---

### 💀 레이드 6: 죽음의 왕좌 (Throne of Death)
| 속성 | 값 |
|------|-----|
| ID | 106 |
| 권장 레벨 | 80+ |
| 권장 인원 | 4명 |
| 주간 리셋 | 월요일 00:00 |

**페이즈 구성**
1. 페이즈 1: 불멸의 군단 (무한 언데드 웨이브)
2. 페이즈 2: 4기사 격파 (동시에 2명씩)
3. 페이즈 3: 죽음의 왕

**레이드 보스**: 죽음의 지배자 (Lord of Death)
**드롭 아이템**: 사신 장비 세트 (SSS 등급), 죽음의 왕관 파편, [초월 재료]

---

### ☀️ 레이드 7: 태양신의 궁전 (Palace of the Sun God)
| 속성 | 값 |
|------|-----|
| ID | 107 |
| 권장 레벨 | 90+ |
| 권장 인원 | 4명 |
| 주간 리셋 | 월요일 00:00 |

**페이즈 구성**
1. 페이즈 1: 빛의 시련 (눈부심 기믹 + 잔혹한 DPS 체크)
2. 페이즈 2: 7가지 미덕 (7명의 수호자 연속 격파)
3. 페이즈 3: 태양신의 화신

**레이드 보스**: 태양신 라 (Sun God Ra)
**드롭 아이템**: 태양신 장비 세트 (SSS~신화 등급), 태양의 정수, [신화 등급 재료]

---

### 🌟 레이드 8: 신들의 황혼 (Twilight of the Gods) - 최종 레이드
| 속성 | 값 |
|------|-----|
| ID | 108 |
| 권장 레벨 | 100 |
| 권장 인원 | 4명 |
| 주간 리셋 | 월요일 00:00 |

**페이즈 구성**
1. 페이즈 1: 12신 격파 (3팀으로 나뉘어 동시 격파)
2. 페이즈 2: 신들의 융합 (기믹 파해 + 잔혹한 생존)
3. 페이즈 3: 원초의 신
4. 히든 페이즈: 진정한 창조신 (특수 조건 충족 시)

**레이드 보스**: 원초의 신 (Primordial God) / 히든: 창조신 (The Creator)
**드롭 아이템**: 신화 장비 세트 (신화 등급 확정), 신들의 유산, [최종 신화 무기 선택권]

---

## 보물상자 (Lootbox)

### 일반 상자
| ID | 이름 | 던전 | 등급 확률 |
|----|------|------|-----------|
| 1 | wooden_chest | 잊혀진 숲 | D:60%, C:30%, B:10% |
| 2 | iron_chest | 고블린 동굴 | D:50%, C:35%, B:15% |
| 3 | scorched_chest | 불타는 광산 | D:40%, C:35%, B:20%, A:5% |
| 4 | frozen_chest | 얼어붙은 호수 | D:40%, C:35%, B:20%, A:5% |
| 5 | storm_chest | 폭풍의 봉우리 | D:35%, C:35%, B:22%, A:8% |
| 6 | coral_chest | 수몰된 신전 | D:35%, C:35%, B:22%, A:8% |

### 고급 상자
| ID | 이름 | 던전 | 등급 확률 |
|----|------|------|-----------|
| 7 | blessed_chest | 성스러운 대성당 | D:25%, C:35%, B:28%, A:12% |
| 8 | cursed_chest | 어둠의 묘지 | D:25%, C:35%, B:28%, A:12% |
| 9 | dragon_chest | 용의 둥지 | D:20%, C:30%, B:30%, A:18%, S:2% |
| 10 | void_chest | 혼돈의 균열 | D:15%, C:25%, B:35%, A:20%, S:5% |
| 11 | royal_chest | 잊혀진 왕국 | D:10%, C:25%, B:35%, A:25%, S:5% |

### 최상급 상자 (Lv.41-50)
| ID | 이름 | 던전 | 등급 확률 |
|----|------|------|-----------|
| 12 | abyssal_chest | 심연의 궁전 | C:20%, B:35%, A:35%, S:10% |
| 13 | celestial_chest | 천상의 탑 | C:15%, B:30%, A:40%, S:15% |
| 14 | raid_chest | 레이드 보상 | B:20%, A:50%, S:30% |

### 차원 상자 (Lv.51-70)
| ID | 이름 | 던전 | 등급 확률 |
|----|------|------|-----------|
| 15 | temporal_chest | 시공의 틈새 | B:30%, A:40%, S:25%, SS:5% |
| 16 | void_essence_chest | 공허의 심연 | B:25%, A:40%, S:28%, SS:7% |
| 17 | deep_sea_chest | 깊은 심해 | B:20%, A:40%, S:30%, SS:10% |
| 18 | awakening_chest | 각성의 제단 | B:15%, A:35%, S:35%, SS:15% |

### 고대 상자 (Lv.71-90)
| ID | 이름 | 던전 | 등급 확률 |
|----|------|------|-----------|
| 19 | ancient_relic_chest | 잊혀진 문명 | A:30%, S:40%, SS:25%, SSS:5% |
| 20 | trial_chest | 시련의 탑 | A:25%, S:40%, SS:28%, SSS:7% |
| 21 | chaos_fragment_chest | 붕괴하는 차원 | A:20%, S:35%, SS:35%, SSS:10% |
| 22 | transcendence_chest | 초월자의 영역 | A:15%, S:35%, SS:38%, SSS:12% |

### 신화 상자 (Lv.91-100)
| ID | 이름 | 던전 | 등급 확률 |
|----|------|------|-----------|
| 23 | divine_chest | 신들의 전장 | S:30%, SS:40%, SSS:25%, 신화:5% |
| 24 | genesis_chest | 창세의 정원 | S:20%, SS:35%, SSS:35%, 신화:10% |
| 25 | god_raid_chest | 신계 레이드 | SS:30%, SSS:45%, 신화:25% |

---

## 던전 특수 기믹

### 환경 효과
| 던전 | 효과 | 설명 |
|------|------|------|
| 불타는 광산 | 화상 지대 | 매 턴 HP 2% 소모 (화염 저항 무효화) |
| 얼어붙은 호수 | 동결 | 15% 확률로 행동 불가 (냉기 저항 감소) |
| 폭풍의 봉우리 | 감전 | 공격 시 10% 확률 연쇄 피해 |
| 수몰된 신전 | 익사 | 전투 5턴 초과 시 턴당 HP 5% 소모 |
| 혼돈의 균열 | 차원 불안정 | 랜덤하게 스탯 ±20% 변동 |

### 숨겨진 방 (Hidden Room)
- 각 던전에서 5% 확률로 발견
- 미니 보스 또는 희귀 상자 등장
- 특수 퀘스트 아이템 드롭 가능

---

## DB 연동

```sql
-- Dungeon_info 테이블 예시
INSERT INTO Dungeon_info (id, name, min_level, description) VALUES
(1, '잊혀진 숲', 1, '마을 근처의 안전한 숲'),
(2, '고블린 동굴', 5, '고블린들이 점거한 어두운 동굴'),
(3, '불타는 광산', 11, '용암이 흐르는 위험한 광산'),
-- ... 계속
;

-- Encounter 테이블 예시
INSERT INTO Encounter (dungeon_id, encounter_type, encounter_value, probability) VALUES
(1, 'monster', 'slime', 0.40),
(1, 'monster', 'goblin', 0.30),
(1, 'monster', 'wolf', 0.20),
(1, 'lootbox', 'wooden_chest', 0.10),
-- ... 계속
;
```
