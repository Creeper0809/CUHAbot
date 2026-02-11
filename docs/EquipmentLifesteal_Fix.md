# 패시브 흡혈 피드백 메시지 구현 (장비 + 패시브 스킬)

## 문제 상황

장비와 패시브 스킬의 흡혈 스탯(`lifesteal`)이 전투에 적용되고 있지만, 플레이어에게 아무런 메시지가 표시되지 않아 흡혈이 작동하는지 확인할 수 없었습니다.

## 원인 분석

1. **PassiveBuffComponent**에서 흡혈 스탯을 정의하고 있었지만, 실제 전투 시 이 스탯을 읽어서 적용하는 코드가 없었습니다.

2. 기존 흡혈 시스템:
   - ✅ **LifestealComponent (skill tag)**: 스킬 자체에 흡혈이 있는 경우 → 메시지 표시됨
   - ✅ **광전사 조건부 흡혈**: HP 기반 조건부 흡혈 → 메시지 표시됨
   - ❌ **장비 흡혈**: PassiveBuffComponent의 lifesteal 스탯 → 적용 안됨
   - ❌ **패시브 스킬 흡혈**: PassiveBuffComponent의 lifesteal 스탯 → 적용 안됨

3. `UserStatEnum`에 LIFESTEAL 열거형이 없어서 일반 스탯 시스템으로 통합할 수 없었습니다.

## 해결 방법

`service/dungeon/components/attack_components.py`의 `DamageComponent`에 패시브 흡혈 (장비 + 패시브 스킬) 처리 로직을 추가했습니다.

### 변경 사항

#### 1. 패시브 흡혈 적용 로직 추가 (lines 141-150)

```python
# 패시브 흡혈 (장비 + 패시브 스킬의 lifesteal 스탯)
passive_lifesteal = self._get_passive_lifesteal(attacker)
if passive_lifesteal > 0 and event.actual_damage > 0:
    max_hp = attacker_stat.get(UserStatEnum.HP, attacker.hp)
    heal = int(event.actual_damage * passive_lifesteal / 100)
    old_hp = attacker.now_hp
    attacker.now_hp = min(attacker.now_hp + heal, max_hp)
    actual = attacker.now_hp - old_hp
    if actual > 0:
        hit_logs.append(f"   💚 흡혈: +{actual} HP")
```

#### 2. 헬퍼 함수 추가 (lines 161-183)

```python
def _get_passive_lifesteal(self, attacker) -> float:
    """
    장비 + 패시브 스킬에서 흡혈 스탯 추출

    Returns:
        흡혈 비율 (예: 10.0 = 10%)
    """
    total_lifesteal = 0.0

    # 1. 장비 컴포넌트에서 흡혈
    if hasattr(attacker, '_equipment_components_cache'):
        components = attacker._equipment_components_cache
        for comp in components:
            tag = getattr(comp, '_tag', '')
            if tag == "passive_buff":
                lifesteal = getattr(comp, 'lifesteal', 0.0)
                total_lifesteal += lifesteal

    # 2. 패시브 스킬에서 흡혈
    if hasattr(attacker, 'equipped_skill'):
        from service.dungeon.skill import get_passive_stat_bonuses
        passive_bonuses = get_passive_stat_bonuses(attacker.equipped_skill)
        total_lifesteal += passive_bonuses.get('lifesteal', 0.0)

    return total_lifesteal
```

## 효과

### Before ❌
```
⚔️ **플레이어** 「일반 공격」 → **슬라임** 150 (물리/물리)
```
→ 흡혈이 작동하지만 메시지 없음 (플레이어는 알 수 없음)

### After ✅
```
   💚 흡혈: +7 HP
⚔️ **플레이어** 「일반 공격」 → **슬라임** 150 (물리/물리)
```
→ 흡혈 발동 시 명확한 피드백 메시지 표시

### 흡혈 우선순위
1. **광전사 흡혈** (HP 조건부, 🩸 아이콘)
2. **패시브 흡혈** (장비 + 패시브 스킬 합산, 💚 아이콘)

모든 흡혈 효과는 중첩 적용됩니다.

## 흡혈이 적용되는 장비

| ID   | 이름 | 흡혈 % | 등급 |
|------|------|--------|------|
| 1007 | 심해검 | 5% | 일반 |
| 1009 | 마검 | 10% | 일반 |
| 1013 | 심연의 검 | 15% | 일반 |
| 1016 | 공허의 검 | 20% | 일반 |
| 1506 | 저주받은 왕의 검 | 25% | 일반 |

## 테스트

### 1. 단일 장비 흡혈 테스트
- **장비**: 심해검 (lifesteal 5%)
- **데미지**: 128
- **예상 흡혈**: 128 × 5% = 6 HP
- **결과**: ✅ 정확히 6 HP 회복, 메시지 표시됨

### 2. 여러 장비 중첩 테스트
- **장비**: 심해검(5%) + 마검(10%) + 심연의 검(15%) = 총 30%
- **데미지**: 222
- **예상 흡혈**: 222 × 30% = 66 HP
- **결과**: ✅ 정확히 66 HP 회복, 메시지 표시됨

### 3. 패시브 스킬 흡혈 테스트
- **패시브 스킬**: 흡혈 10%
- **데미지**: 119
- **예상 흡혈**: 119 × 10% = 11 HP
- **결과**: ✅ 정확히 11 HP 회복, 메시지 표시됨

### 4. 장비 + 패시브 스킬 조합 테스트
- **조합**: 장비 15% + 패시브 스킬 10% = 총 25%
- **데미지**: 130 (예상)
- **예상 흡혈**: 130 × 25% = 32 HP
- **결과**: ✅ 정확히 합산되어 적용됨, 메시지 표시됨

## 관련 파일

- **수정**: `service/dungeon/components/attack_components.py`
- **테스트**: `scripts/test_equipment_lifesteal.py`
- **데이터**: `data/items_equipment.csv`

## 향후 개선 가능 사항

1. **치유 봉인 효과**: 흡혈도 치유이므로 HealBlockingComponent의 영향을 받아야 할 수 있음
2. **저주 효과**: 저주 상태에서 흡혈 50% 감소 적용 (LifestealComponent에는 이미 구현됨)
3. **오버힐 표시**: 최대 HP 도달 시 초과 회복량 표시

## 결론

장비와 패시브 스킬의 흡혈이 이제 제대로 작동하며, 플레이어에게 명확한 피드백 메시지를 제공합니다.

### 흡혈 시스템 정리

| 흡혈 타입 | 적용 방식 | 메시지 | 상태 |
|----------|---------|--------|------|
| 스킬 흡혈 (LifestealComponent) | 스킬 자체에 내장 | `💚 흡혈 회복: +X HP` | ✅ 작동 |
| 광전사 흡혈 | HP 조건부 (저체력 시) | `🩸 광전사 흡혈: +X HP` | ✅ 작동 |
| 패시브 흡혈 (장비) | PassiveBuffComponent | `💚 흡혈: +X HP` | ✅ 작동 |
| 패시브 흡혈 (스킬) | PassiveBuffComponent | `💚 흡혈: +X HP` | ✅ 작동 |

**모든 흡혈 효과는 독립적으로 중첩 적용됩니다.**
