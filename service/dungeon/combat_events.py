"""
전투 이벤트 시스템

스킬 컴포넌트가 데미지 계산, 피해 적용 등의 시점에 개입할 수 있도록
이벤트 객체를 제공합니다.
"""
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from service.dungeon.entity import Entity


@dataclass
class DamageCalculationEvent:
    """
    데미지 계산 이벤트 (데미지 확정 전)

    컴포넌트가 이 이벤트를 받아서:
    - 치명타 판정 및 배율 적용
    - 방어구 관통 추가
    - 데미지 배율 조정
    """
    attacker: "Entity"
    defender: "Entity"
    base_damage: int
    skill_name: str = ""
    skill_attribute: str = "무속성"
    multipliers: List[float] = field(default_factory=lambda: [1.0])
    defense_ignore: float = 0.0
    is_critical: bool = False
    logs: List[str] = field(default_factory=list)

    def apply_multiplier(self, mult: float, log_message: str = ""):
        """
        데미지 배율 적용

        Args:
            mult: 배율 (예: 1.5 = 150%)
            log_message: 로그 메시지 (선택)
        """
        self.multipliers.append(mult)
        if mult > 1.0:
            self.is_critical = True
        if log_message:
            self.logs.append(log_message)

    def ignore_defense(self, ratio: float):
        """
        방어력 무시 비율 추가 (최대 70%까지)

        Args:
            ratio: 무시 비율 (0.0 ~ 1.0)
        """
        self.defense_ignore = min(self.defense_ignore + ratio, 0.7)

    def add_log(self, message: str):
        """전투 로그 추가"""
        self.logs.append(message)

    def get_final_damage(self) -> int:
        """최종 데미지 계산 (모든 배율 적용)"""
        result = self.base_damage
        for mult in self.multipliers:
            result = int(result * mult)
        return max(1, result)


@dataclass
class DamageDealtEvent:
    """
    데미지 적용 후 이벤트

    컴포넌트가 이 이벤트를 받아서:
    - 흡혈 (데미지의 일부만큼 회복)
    - 추가 효과 발동 (화상 부여 등)
    """
    attacker: "Entity"
    defender: "Entity"
    damage: int
    damage_attribute: str
    skill_name: str = ""
    logs: List[str] = field(default_factory=list)

    def add_log(self, message: str):
        """전투 로그 추가"""
        self.logs.append(message)


@dataclass
class TakeDamageEvent:
    """
    피해 받을 때 이벤트 (데미지 적용 전)

    컴포넌트가 이 이벤트를 받아서:
    - 속성 저항으로 데미지 경감
    - 보호막으로 데미지 흡수
    - 데미지 반사
    """
    attacker: "Entity"
    defender: "Entity"
    damage: int
    damage_attribute: str
    skill_name: str = ""
    reductions: List[int] = field(default_factory=list)
    logs: List[str] = field(default_factory=list)

    def reduce_damage(self, amount: int, log_message: str = ""):
        """
        데미지 감소

        Args:
            amount: 감소량
            log_message: 로그 메시지 (선택)
        """
        self.reductions.append(amount)
        if log_message:
            self.logs.append(log_message)

    def get_final_damage(self) -> int:
        """최종 피해량 (모든 경감 적용, 최소 1)"""
        return max(1, self.damage - sum(self.reductions))

    def add_log(self, message: str):
        """전투 로그 추가"""
        self.logs.append(message)


@dataclass
class HitCalculationEvent:
    """
    명중 판정 이벤트

    컴포넌트가 이 이벤트를 받아서:
    - 명중률/회피율 조정
    - 필중 효과 부여
    """
    attacker: "Entity"
    defender: "Entity"
    base_accuracy: float = 100.0
    base_evasion: float = 0.0
    accuracy_modifiers: List[float] = field(default_factory=list)
    evasion_modifiers: List[float] = field(default_factory=list)
    force_hit: bool = False
    logs: List[str] = field(default_factory=list)

    def add_accuracy(self, amount: float):
        """명중률 추가"""
        self.accuracy_modifiers.append(amount)

    def add_evasion(self, amount: float):
        """회피율 추가"""
        self.evasion_modifiers.append(amount)

    def set_force_hit(self):
        """필중 효과"""
        self.force_hit = True

    def get_final_accuracy(self) -> float:
        """최종 명중률"""
        return self.base_accuracy + sum(self.accuracy_modifiers)

    def get_final_evasion(self) -> float:
        """최종 회피율"""
        return self.base_evasion + sum(self.evasion_modifiers)

    def add_log(self, message: str):
        """전투 로그 추가"""
        self.logs.append(message)
