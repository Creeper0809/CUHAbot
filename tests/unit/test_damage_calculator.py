"""
DamageCalculator 유닛 테스트

데미지 계산 공식, 치명타, 명중률, 방어력 무시 등을 테스트합니다.
"""
import pytest

from config import DAMAGE
from service.combat.damage_calculator import DamageCalculator, DamageResult


class TestPhysicalDamage:
    """물리 데미지 계산 테스트"""

    def test_basic_damage(self):
        """기본 물리 데미지 계산 (방어력 0)"""
        result = DamageCalculator.calculate_physical_damage(
            attack=100,
            defense=0,
            skill_multiplier=1.0,
            critical_rate=0,  # 치명타 비활성화
        )

        # 변동폭 ±10% 허용
        assert 90 <= result.damage <= 110
        assert result.is_critical is False
        assert result.is_hit is True
        assert result.raw_damage == 100

    def test_damage_with_defense(self):
        """방어력 적용 테스트"""
        result = DamageCalculator.calculate_physical_damage(
            attack=100,
            defense=50,
            skill_multiplier=1.0,
            critical_rate=0,
        )

        # V2: 50 / (50 + 100) = 33.33% 감소
        # The runtime rounds mitigation before applying the ±8% variance.
        expected_base = result.raw_damage - result.defense_reduction
        assert int(expected_base * 0.92) <= result.damage <= int(expected_base * 1.08)
        assert result.defense_reduction == 34

    def test_skill_multiplier(self):
        """스킬 배율 테스트"""
        result = DamageCalculator.calculate_physical_damage(
            attack=100,
            defense=0,
            skill_multiplier=1.5,
            critical_rate=0,
        )

        # 기본 데미지 = 100 * 1.5 = 150 (±10% 변동)
        assert 135 <= result.damage <= 165
        assert result.raw_damage == 150

    def test_minimum_damage_guarantee(self):
        """최소 데미지 보장 테스트 (높은 방어력)"""
        result = DamageCalculator.calculate_physical_damage(
            attack=10,
            defense=1000,  # 매우 높은 방어력
            skill_multiplier=1.0,
            critical_rate=0,
        )

        # 최소 데미지는 DAMAGE.MIN_DAMAGE (1)
        assert result.damage >= DAMAGE.MIN_DAMAGE

    def test_armor_penetration_applied(self):
        """방어력 무시 적용 테스트"""
        # 방어력 무시 없이
        result_without_pen = DamageCalculator.calculate_physical_damage(
            attack=100,
            defense=100,
            skill_multiplier=1.0,
            armor_penetration=0.0,
            critical_rate=0,
        )

        # 방어력 50% 무시
        result_with_pen = DamageCalculator.calculate_physical_damage(
            attack=100,
            defense=100,
            skill_multiplier=1.0,
            armor_penetration=0.5,
            critical_rate=0,
        )

        # 방어력 무시 시 더 높은 데미지
        # without: 100 - (100 * 1.0 * 0.5) = 50
        # with: 100 - (100 * 0.5 * 0.5) = 75
        assert result_with_pen.defense_reduction < result_without_pen.defense_reduction

    def test_armor_penetration_cap(self):
        """방어력 무시 최대 50% 제한 테스트"""
        result = DamageCalculator.calculate_physical_damage(
            attack=100,
            defense=100,
            skill_multiplier=1.0,
            armor_penetration=1.0,  # 100% 요청
            critical_rate=0,
        )

        # 유효 방어 50 → 33.33% 감소
        assert result.defense_reduction == 34

    def test_force_critical(self):
        """강제 치명타 테스트"""
        result = DamageCalculator.calculate_physical_damage(
            attack=100,
            defense=0,
            skill_multiplier=1.0,
            critical_rate=0,  # 확률 0
            force_critical=True,  # 강제 치명타
        )

        assert result.is_critical is True
        # 치명타 배율 1.5 적용 (±10% 변동)
        assert 135 <= result.damage <= 165


class TestMagicalDamage:
    """마법 데미지 계산 테스트"""

    def test_basic_magical_damage(self):
        """기본 마법 데미지 계산"""
        result = DamageCalculator.calculate_magical_damage(
            ap_attack=100,
            ap_defense=0,
            skill_multiplier=1.0,
            critical_rate=0,
        )

        assert 90 <= result.damage <= 110
        assert result.raw_damage == 100

    def test_magical_defense_ratio(self):
        """마법 방어력도 공통 V2 완화 곡선을 사용하는지 테스트"""
        result = DamageCalculator.calculate_magical_damage(
            ap_attack=100,
            ap_defense=50,
            skill_multiplier=1.0,
            critical_rate=0,
        )

        expected_base = 100 * (1 - 50 / 150)
        assert int(expected_base * 0.92) <= result.damage <= int(expected_base * 1.08)
        assert result.defense_reduction == 34


class TestCriticalHit:
    """치명타 테스트"""

    def test_critical_multiplier(self):
        """치명타 배율 테스트"""
        result = DamageCalculator.calculate_physical_damage(
            attack=100,
            defense=0,
            skill_multiplier=1.0,
            force_critical=True,
        )

        # 기본 100 * 1.5 = 150 (±10% 변동)
        assert 135 <= result.damage <= 165
        assert result.is_critical is True

    def test_critical_rate_zero(self):
        """치명타 확률 0%일 때"""
        results = [
            DamageCalculator.calculate_physical_damage(
                attack=100,
                defense=0,
                critical_rate=0,
            )
            for _ in range(100)
        ]

        # 모두 치명타가 아니어야 함
        assert all(r.is_critical is False for r in results)

    def test_critical_rate_max_cap(self):
        """치명타 확률 최대 70% 제한"""
        # 100% 확률을 요청해도 70%로 제한
        # 통계적으로 100번 중 일부는 치명타가 아닐 수 있음
        results = [
            DamageCalculator.calculate_physical_damage(
                attack=100,
                defense=0,
                critical_rate=1.0,  # 100% 요청
            )
            for _ in range(100)
        ]

        crit_count = sum(1 for r in results if r.is_critical)
        assert 50 <= crit_count <= 90


class TestHitChance:
    """명중률 테스트"""

    def test_high_accuracy(self):
        """높은 명중률 테스트"""
        hits = sum(
            1 for _ in range(100)
            if DamageCalculator.roll_hit(accuracy=95, evasion=5)
        )
        # 90% 명중률 → 대부분 명중
        assert hits >= 80

    def test_low_accuracy(self):
        """낮은 명중률 테스트"""
        hits = sum(
            1 for _ in range(100)
            if DamageCalculator.roll_hit(accuracy=50, evasion=40)
        )
        # V2 최소 명중률 75%
        assert 60 <= hits <= 90

    def test_minimum_hit_rate(self):
        """최소 75% 명중률 보장"""
        hits = sum(
            1 for _ in range(1000)
            if DamageCalculator.roll_hit(accuracy=0, evasion=100)
        )
        assert 700 <= hits <= 800

    def test_maximum_hit_rate(self):
        """최대 98% 명중률"""
        hits = sum(
            1 for _ in range(100)
            if DamageCalculator.roll_hit(accuracy=200, evasion=0)
        )
        assert 90 <= hits <= 100


class TestDamageVariance:
    """데미지 변동 테스트"""

    def test_variance_range(self):
        """±10% 변동 범위 테스트"""
        damages = [
            DamageCalculator.calculate_physical_damage(
                attack=100,
                defense=0,
                skill_multiplier=1.0,
                critical_rate=0,
            ).damage
            for _ in range(100)
        ]

        # 90 ~ 110 범위 내
        assert min(damages) >= 90
        assert max(damages) <= 110

    def test_variance_distribution(self):
        """변동이 고르게 분포되는지 테스트"""
        damages = [
            DamageCalculator.calculate_physical_damage(
                attack=100,
                defense=0,
                skill_multiplier=1.0,
                critical_rate=0,
            ).damage
            for _ in range(1000)
        ]

        avg = sum(damages) / len(damages)
        # 평균은 100 근처여야 함 (95-105 허용)
        assert 95 <= avg <= 105


class TestCalculateWithHitCheck:
    """명중 체크 포함 데미지 계산 테스트"""

    def test_miss_returns_zero_damage(self):
        """빗나감 시 데미지 0"""
        # 매우 낮은 명중률
        result = DamageCalculator.calculate_damage_with_hit_check(
            attack=100,
            defense=0,
            accuracy=0,
            evasion=100,  # 거의 무조건 빗나감
        )

        # V2에서는 아무리 낮아도 75% 명중하므로 약 25%만 빗나간다.
        misses = 0
        for _ in range(100):
            r = DamageCalculator.calculate_damage_with_hit_check(
                attack=100,
                defense=0,
                accuracy=5,
                evasion=100,
            )
            if not r.is_hit:
                misses += 1
                assert r.damage == 0
                assert r.is_critical is False

        assert 10 <= misses <= 40

    def test_physical_vs_magical_toggle(self, monkeypatch):
        """물리/마법 데미지 전환"""
        monkeypatch.setattr("service.combat.damage_calculator.random.random", lambda: 0.0)
        physical = DamageCalculator.calculate_damage_with_hit_check(
            attack=100,
            defense=50,
            accuracy=100,
            evasion=0,
            is_physical=True,
            critical_rate=0,
        )

        magical = DamageCalculator.calculate_damage_with_hit_check(
            attack=100,
            defense=50,
            accuracy=100,
            evasion=0,
            is_physical=False,
            critical_rate=0,
        )

        # V2는 물리/마법 모두 동일한 방어 곡선을 사용한다.
        assert magical.defense_reduction == physical.defense_reduction


class TestDamageResult:
    """DamageResult 데이터 클래스 테스트"""

    def test_result_fields(self):
        """결과 필드 확인"""
        result = DamageCalculator.calculate_physical_damage(
            attack=100,
            defense=50,
            force_critical=True,
        )

        assert isinstance(result.damage, int)
        assert isinstance(result.is_critical, bool)
        assert isinstance(result.is_hit, bool)
        assert isinstance(result.raw_damage, int)
        assert isinstance(result.defense_reduction, int)
        assert result.is_critical is True
        assert result.is_hit is True
