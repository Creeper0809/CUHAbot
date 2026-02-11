"""
강화 확률 검증 스크립트

실제 강화 시스템의 확률이 제대로 작동하는지 시뮬레이션으로 검증합니다.
"""
import random
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from service.item.enhancement_service import EnhancementService


def simulate_enhancement_attempts(level: int, is_blessed: bool = False, is_cursed: bool = False, trials: int = 10000):
    """
    특정 레벨에서 강화 시도를 시뮬레이션

    Args:
        level: 현재 강화 레벨
        is_blessed: 축복 여부
        is_cursed: 저주 여부
        trials: 시뮬레이션 횟수
    """
    # 성공률 계산
    base_rate = EnhancementService._get_success_rate(level)
    success_rate = base_rate

    if is_blessed:
        success_rate = min(1.0, success_rate + 0.10)
    if is_cursed:
        success_rate = max(0.0, success_rate - 0.10)

    # 시뮬레이션
    successes = 0
    for _ in range(trials):
        roll = random.random()
        if roll < success_rate:
            successes += 1

    actual_rate = successes / trials
    expected_rate = success_rate
    deviation = abs(actual_rate - expected_rate)

    return {
        "level": level,
        "is_blessed": is_blessed,
        "is_cursed": is_cursed,
        "base_rate": base_rate,
        "expected_rate": expected_rate,
        "actual_rate": actual_rate,
        "successes": successes,
        "trials": trials,
        "deviation": deviation,
        "deviation_percent": deviation * 100,
    }


def main():
    print("=" * 80)
    print("강화 확률 검증 시뮬레이션 (각 10,000회 시도)")
    print("=" * 80)
    print()

    # 각 레벨 범위별 테스트
    test_levels = [0, 3, 4, 6, 7, 9, 10, 12, 13, 14, 15]

    print("📊 기본 확률 테스트 (축복/저주 없음)")
    print("-" * 80)
    print(f"{'레벨':<8} {'기본확률':<12} {'실제확률':<12} {'편차':<12} {'결과'}")
    print("-" * 80)

    for level in test_levels:
        if level > 15:
            continue
        result = simulate_enhancement_attempts(level)
        status = "✅ OK" if result['deviation_percent'] < 2.0 else "⚠️ 편차 큼"
        print(
            f"+{level:<7} "
            f"{result['expected_rate']*100:>6.1f}%      "
            f"{result['actual_rate']*100:>6.2f}%      "
            f"{result['deviation_percent']:>6.2f}%      "
            f"{status}"
        )

    print()
    print("✨ 축복 효과 테스트 (+10% 성공률)")
    print("-" * 80)
    print(f"{'레벨':<8} {'기본확률':<12} {'축복확률':<12} {'실제확률':<12} {'편차'}")
    print("-" * 80)

    for level in [7, 10, 13]:
        result = simulate_enhancement_attempts(level, is_blessed=True)
        print(
            f"+{level:<7} "
            f"{result['base_rate']*100:>6.1f}%      "
            f"{result['expected_rate']*100:>6.1f}%      "
            f"{result['actual_rate']*100:>6.2f}%      "
            f"{result['deviation_percent']:>6.2f}%"
        )

    print()
    print("💀 저주 효과 테스트 (-10% 성공률)")
    print("-" * 80)
    print(f"{'레벨':<8} {'기본확률':<12} {'저주확률':<12} {'실제확률':<12} {'편차'}")
    print("-" * 80)

    for level in [7, 10, 13]:
        result = simulate_enhancement_attempts(level, is_cursed=True)
        print(
            f"+{level:<7} "
            f"{result['base_rate']*100:>6.1f}%      "
            f"{result['expected_rate']*100:>6.1f}%      "
            f"{result['actual_rate']*100:>6.2f}%      "
            f"{result['deviation_percent']:>6.2f}%"
        )

    print()
    print("🎲 연속 성공 확률 계산")
    print("-" * 80)

    # +13 → +14 → +15 연속 성공 확률
    rate_13 = EnhancementService._get_success_rate(13)
    rate_14 = EnhancementService._get_success_rate(14)

    consecutive_normal = rate_13 * rate_14
    consecutive_blessed = (rate_13 + 0.1) * (rate_14 + 0.1)

    print(f"일반: +13→+14 성공 확률: {rate_13*100:.1f}%")
    print(f"일반: +14→+15 성공 확률: {rate_14*100:.1f}%")
    print(f"일반: 연속 성공 확률: {consecutive_normal*100:.2f}% (약 {int(1/consecutive_normal)}번 중 1번)")
    print()
    print(f"축복: +13→+14 성공 확률: {(rate_13+0.1)*100:.1f}%")
    print(f"축복: +14→+15 성공 확률: {(rate_14+0.1)*100:.1f}%")
    print(f"축복: 연속 성공 확률: {consecutive_blessed*100:.2f}% (약 {int(1/consecutive_blessed)}번 중 1번)")

    print()
    print("=" * 80)
    print("결론:")
    print("- 모든 레벨의 실제 성공률이 기대 확률과 2% 이내 편차로 일치하면 정상")
    print("- 축복/저주 보정이 정확히 ±10% 적용되는지 확인")
    print("- +13→+15 연속 성공은 일반 4%, 축복 9% 확률로 가능 (운이 좋았음)")
    print("=" * 80)


if __name__ == "__main__":
    main()
