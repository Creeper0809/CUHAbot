"""
장비 전용 패시브 컴포넌트

장비에만 사용되는 특수 패시브 효과들입니다.
"""
import random
from typing import Dict
from service.dungeon.components.base import SkillComponent, register_skill_with_tag


@register_skill_with_tag("on_attack_proc")
class OnAttackProcComponent(SkillComponent):
    """
    공격 시 확률 발동 컴포넌트 (장비 전용 패시브)

    플레이어가 공격 스킬을 사용할 때마다 일정 확률로
    상태이상이나 추가 효과를 발동합니다.

    Config options:
        proc_chance (float): 발동 확률 (0.0~1.0, 예: 0.1 = 10%)
        status_effect (str): 적용할 상태이상 (예: "burn", "slow", "freeze")
        status_duration (int): 상태이상 지속 턴 수
        status_stacks (int): 상태이상 스택 수 (기본 1)
        extra_damage_ratio (float): 추가 데미지 비율 (선택, 예: 0.2 = 20%)
    """

    def __init__(self):
        super().__init__()
        self.proc_chance = 0.0
        self.status_effect = None
        self.status_duration = 0
        self.status_stacks = 1
        self.extra_damage_ratio = 0.0

    def apply_config(self, config, skill_name, priority=0):
        super().apply_config(config, skill_name, priority)
        self.proc_chance = config.get("proc_chance", 0.0)
        self.status_effect = config.get("status_effect", None)
        self.status_duration = config.get("status_duration", 0)
        self.status_stacks = config.get("status_stacks", 1)
        self.extra_damage_ratio = config.get("extra_damage_ratio", 0.0)

    def on_turn(self, attacker, target):
        """
        공격 스킬 사용 시 확률적으로 효과 발동

        Note: 이 컴포넌트는 장비 패시브로 장착되어 있으면,
        플레이어가 사용하는 모든 스킬에 이 효과가 적용됩니다.
        """
        # 확률 체크
        if random.random() > self.proc_chance:
            return ""

        logs = []

        # 상태이상 적용
        if self.status_effect and self.status_duration > 0:
            from service.dungeon.status import apply_status_effect

            status_log = apply_status_effect(
                entity=target,
                effect_type=self.status_effect,
                duration=self.status_duration,
                stacks=self.status_stacks
            )

            if status_log:
                status_names = {
                    "burn": "화상",
                    "poison": "중독",
                    "slow": "둔화",
                    "freeze": "동결",
                    "stun": "기절",
                    "shock": "감전",
                    "curse": "저주",
                }
                status_name = status_names.get(self.status_effect, self.status_effect)
                logs.append(
                    f"⚡ **{attacker.get_name()}** 장비 효과 발동! "
                    f"→ **{target.get_name()}** {status_name} 부여!"
                )

        # 추가 데미지 (선택)
        if self.extra_damage_ratio > 0:
            from service.dungeon.damage_pipeline import process_incoming_damage
            from models import UserStatEnum

            attacker_stat = attacker.get_stat()
            ad = attacker_stat.get(UserStatEnum.ATTACK, 0)

            extra_damage = int(ad * self.extra_damage_ratio)
            if extra_damage > 0:
                event = process_incoming_damage(
                    target, extra_damage, attacker=attacker,
                    attribute=self.skill_attribute,
                )
                logs.append(
                    f"   💥 연쇄 피해 {event.actual_damage}"
                )

        return "\n".join(logs) if logs else ""


@register_skill_with_tag("race_bonus")
class RaceBonusComponent(SkillComponent):
    """
    종족 특효 컴포넌트 (장비 전용 패시브)

    특정 종족에 대해 추가 데미지를 줍니다.

    Config options:
        race (str): 대상 종족 (예: "dragon", "undead", "beast", etc.)
        damage_bonus (float): 데미지 보너스 비율 (예: 0.5 = 50% 추가)
    """

    def __init__(self):
        super().__init__()
        self.race = None
        self.damage_bonus = 0.0

    def apply_config(self, config, skill_name, priority=0):
        super().apply_config(config, skill_name, priority)
        self.race = config.get("race", None)
        self.damage_bonus = config.get("damage_bonus", 0.0)

    def on_turn(self, attacker, target):
        """
        대상의 종족을 확인하고 보너스 데미지 적용

        Note: 이 메서드는 실제로 데미지를 주지 않고,
        damage_calculator에서 참조할 수 있도록 정보만 제공합니다.
        실제 종족 보너스는 get_race_bonus_multiplier()를 통해 적용됩니다.
        """
        return ""

    def get_race_bonus_multiplier(self, target) -> float:
        """
        대상 종족에 대한 보너스 배율 반환

        Returns:
            1.0 + damage_bonus if race matches, else 1.0
        """
        if not self.race or self.damage_bonus == 0:
            return 1.0

        # 대상의 종족 확인
        target_race = getattr(target, 'race', None)
        if not target_race:
            return 1.0

        # 종족 매칭
        race_aliases = {
            "dragon": ["드래곤", "dragon", "용"],
            "undead": ["언데드", "undead", "해골", "skeleton"],
            "beast": ["짐승", "beast", "야수"],
            "demon": ["악마", "demon", "데몬", "마수"],  # 마수 추가 (Monster race system)
            "slime": ["슬라임", "slime"],
            "goblin": ["고블린", "goblin"],
            "elemental": ["정령", "elemental"],
            "golem": ["골렘", "golem", "기계"],
            "magic_user": ["마법사", "wizard", "mage", "인간형"],  # 인간형 추가 (humanoid race)
            "aquatic": ["수생", "aquatic"],  # 수생 종족 추가 (for future equipment)
        }

        for race_key, aliases in race_aliases.items():
            if self.race in aliases and target_race in aliases:
                return 1.0 + self.damage_bonus

        return 1.0


@register_skill_with_tag("on_kill_stack")
class OnKillStackComponent(SkillComponent):
    """
    처치 시 스택 컴포넌트 (장비 전용 패시브)

    적을 처치할 때마다 영구적으로 스탯이 증가합니다.

    Config options:
        stat (str): 증가할 스탯 (예: "attack", "ap_attack", "hp")
        amount_per_kill (float): 처치당 증가량 (비율, 예: 0.01 = 1%)
        max_stacks (int): 최대 스택 수 (기본 무제한 = 0)
    """

    def __init__(self):
        super().__init__()
        self.stat = "attack"
        self.amount_per_kill = 0.0
        self.max_stacks = 0
        self._current_stacks = 0

    def apply_config(self, config, skill_name, priority=0):
        super().apply_config(config, skill_name, priority)
        self.stat = config.get("stat", "attack")
        self.amount_per_kill = config.get("amount_per_kill", 0.0)
        self.max_stacks = config.get("max_stacks", 0)

    def on_death(self, dying_entity, killer):
        """
        적 처치 시 스택 증가

        Note: 이 훅은 전투 시스템에서 적이 죽을 때 호출됩니다.
        """
        if killer != dying_entity:  # 자살이 아닌 경우
            # 스택 제한 체크
            if self.max_stacks > 0 and self._current_stacks >= self.max_stacks:
                return ""

            self._current_stacks += 1

            return (
                f"⚔️ **{killer.get_name()}** 처치 스택 +1! "
                f"(총 {self._current_stacks}스택, {self.stat} +{self.amount_per_kill * 100 * self._current_stacks:.0f}%)"
            )

        return ""

    def get_stat_bonus(self) -> Dict[str, float]:
        """현재 스택에 따른 스탯 보너스 반환"""
        if self._current_stacks == 0:
            return {}

        return {
            self.stat: self.amount_per_kill * self._current_stacks
        }
