"""
스탯 컴포넌트: BuffComponent, DebuffComponent, PassiveBuffComponent
"""
from models import UserStatEnum
from service.dungeon.components.base import SkillComponent, register_skill_with_tag
from service.dungeon.status import (
    AttackBuff, DefenseBuff, SpeedBuff,
)


@register_skill_with_tag("buff")
class BuffComponent(SkillComponent):
    """
    버프 컴포넌트 - 실제 Buff 객체를 entity.status에 추가

    Config options:
        duration (int): 지속 턴 수 (기본 3)
        attack (float): 공격력 증가율 (예: 0.25 = +25%)
        defense (float): 방어력 증가율
        speed (float): 속도 증가율
        crit_rate (float): 치명타 확률 증가
    """

    def __init__(self):
        super().__init__()
        self.duration = 3
        self.attack_mod = 0
        self.defense_mod = 0
        self.speed_mod = 0
        self.crit_rate_mod = 0

    def apply_config(self, config, skill_name, priority=0):
        super().apply_config(config, skill_name, priority)
        self.duration = config.get("duration", 3)
        self.attack_mod = config.get("attack", 0)
        self.defense_mod = config.get("defense", 0)
        self.speed_mod = config.get("speed", 0)
        self.crit_rate_mod = config.get("crit_rate", 0)

    def on_turn_start(self, attacker, target):
        effects = []
        stat = attacker.get_stat()

        if self.attack_mod != 0:
            amount = int(stat[UserStatEnum.ATTACK] * self.attack_mod)
            buff = AttackBuff()
            buff.amount = amount
            buff.duration = self.duration
            attacker.status.append(buff)
            effects.append(f"공격력 +{amount}")

        if self.defense_mod != 0:
            amount = int(stat[UserStatEnum.DEFENSE] * self.defense_mod)
            buff = DefenseBuff()
            buff.amount = amount
            buff.duration = self.duration
            attacker.status.append(buff)
            effects.append(f"방어력 +{amount}")

        if self.speed_mod != 0:
            amount = int(stat[UserStatEnum.SPEED] * self.speed_mod)
            buff = SpeedBuff()
            buff.amount = amount
            buff.duration = self.duration
            attacker.status.append(buff)
            effects.append(f"속도 +{amount}")

        if not effects:
            return ""

        return f"✨ **{attacker.get_name()}** 「{self.skill_name}」 → {', '.join(effects)} ({self.duration}턴)"


@register_skill_with_tag("debuff")
class DebuffComponent(SkillComponent):
    """디버프 컴포넌트 - 실제 디버프 Buff를 target.status에 추가"""

    def __init__(self):
        super().__init__()
        self.duration = 3
        self.attack_mod = 0
        self.defense_mod = 0
        self.speed_mod = 0

    def apply_config(self, config, skill_name, priority=0):
        super().apply_config(config, skill_name, priority)
        self.duration = config.get("duration", 3)
        self.attack_mod = config.get("attack", 0)
        self.defense_mod = config.get("defense", 0)
        self.speed_mod = config.get("speed", 0)

    def on_turn(self, attacker, target):
        effects = []
        target_stat = target.get_stat()

        if self.attack_mod != 0:
            amount = int(target_stat[UserStatEnum.ATTACK] * self.attack_mod)
            buff = AttackBuff()
            buff.amount = amount  # 음수값
            buff.duration = self.duration
            buff.is_debuff = True
            target.status.append(buff)
            effects.append(f"공격력 {amount}")

        if self.defense_mod != 0:
            amount = int(target_stat[UserStatEnum.DEFENSE] * self.defense_mod)
            buff = DefenseBuff()
            buff.amount = amount
            buff.duration = self.duration
            buff.is_debuff = True
            target.status.append(buff)
            effects.append(f"방어력 {amount}")

        if self.speed_mod != 0:
            amount = int(target_stat[UserStatEnum.SPEED] * self.speed_mod)
            buff = SpeedBuff()
            buff.amount = amount
            buff.duration = self.duration
            buff.is_debuff = True
            target.status.append(buff)
            effects.append(f"속도 {amount}")

        if not effects:
            return ""

        return f"🔮 **{attacker.get_name()}** 「{self.skill_name}」 → **{target.get_name()}** {', '.join(effects)} ({self.duration}턴)"


@register_skill_with_tag("passive_buff")
class PassiveBuffComponent(SkillComponent):
    """
    패시브 버프 컴포넌트 - 전투 시작 시 1회 영구 버프

    Config options:
        attack_percent (float): 공격력 증가 비율
        hp_percent (float): HP 증가 비율
        defense_percent (float): 방어력 증가 비율
        crit_rate (float): 치명타 확률 증가
        condition (str): 발동 조건 (vs_boss, always 등)
    """

    def __init__(self):
        super().__init__()
        self.attack_percent = 0.0
        self.hp_percent = 0.0
        self.defense_percent = 0.0
        self.crit_rate = 0.0
        self.condition = "always"
        self._applied = False

    def apply_config(self, config, skill_name, priority=0):
        super().apply_config(config, skill_name, priority)
        self.attack_percent = config.get("attack_percent", 0.0)
        self.hp_percent = config.get("hp_percent", 0.0)
        self.defense_percent = config.get("defense_percent", 0.0)
        self.crit_rate = config.get("crit_rate", 0.0)
        self.condition = config.get("condition", "always")

    def on_turn_start(self, attacker, target):
        if self._applied:
            return ""
        self._applied = True

        stat = attacker.get_stat()
        effects = []
        duration = 999  # 영구

        if self.attack_percent != 0:
            amount = int(stat[UserStatEnum.ATTACK] * self.attack_percent)
            buff = AttackBuff()
            buff.amount = amount
            buff.duration = duration
            attacker.status.append(buff)
            effects.append(f"공격력 +{amount}")

        if self.defense_percent != 0:
            amount = int(stat[UserStatEnum.DEFENSE] * self.defense_percent)
            buff = DefenseBuff()
            buff.amount = amount
            buff.duration = duration
            attacker.status.append(buff)
            effects.append(f"방어력 +{amount}")

        if not effects:
            return ""

        return f"🌟 **{attacker.get_name()}** 패시브 「{self.skill_name}」 → {', '.join(effects)}"
