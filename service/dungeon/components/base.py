"""
스킬 컴포넌트 기본 클래스 및 레지스트리

스킬의 다양한 효과를 컴포넌트 단위로 분리하여 조합합니다.
각 컴포넌트는 턴 기반 콜백을 구현합니다.

스탯 계수 시스템:
- ad_ratio: 물리 공격력(AD) 계수 (예: 1.4 = 140% AD)
- ap_ratio: 마법 공격력(AP) 계수 (예: 1.0 = 100% AP)
- 하이브리드 스킬은 두 계수 모두 사용 가능
"""
from models import UserStatEnum
from service.dungeon.turn_config import TurnConfig

skill_component_register = {}


def register_skill_with_tag(tag):
    def decorator(cls):
        skill_component_register[tag] = cls
        return cls
    return decorator


def get_component_by_tag(tag):
    return skill_component_register[tag]()


class SkillComponent(TurnConfig):
    def __init__(self):
        self.priority = 0
        self.skill_name = ""
        self.skill_attribute = "무속성"

    def apply_config(self, config, skill_name, priority=0):
        self.priority = priority
        self.skill_name = skill_name

    def _calculate_base_attack_power(self, attacker_stat) -> int:
        """스탯 계수를 적용한 기본 공격력 계산"""
        ad = attacker_stat.get(UserStatEnum.ATTACK, 0)
        ap = attacker_stat.get(UserStatEnum.AP_ATTACK, 0)
        total = int(ad * self.ad_ratio + ap * self.ap_ratio)
        return max(1, total)
