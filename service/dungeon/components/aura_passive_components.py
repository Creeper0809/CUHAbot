"""
오라 패시브 컴포넌트: AuraBuffComponent, AuraDebuffComponent

전투 시작 시 아군/적에게 영구 버프/디버프를 적용합니다.
on_turn_start(attacker, context)에서 context를 통해 대상을 결정합니다.
"""
from models import UserStatEnum
from service.dungeon.components.base import SkillComponent, register_skill_with_tag
from service.dungeon.status import AttackBuff, DefenseBuff, SpeedBuff
from config import COMBAT


@register_skill_with_tag("passive_aura_debuff")
class AuraDebuffComponent(SkillComponent):
    """
    오라 디버프 패시브 - 전투 시작 시 적에게 영구 디버프

    Config options:
        target (str): "enemies" (적에게 적용) 또는 "allies" (아군에게 적용)
        attack_percent (float): 공격력 변화율 (음수 = 감소, 예: -0.1 = -10%)
        defense_percent (float): 방어력 변화율
        speed_percent (float): 속도 변화율
    """

    def __init__(self):
        super().__init__()
        self.target_type: str = "enemies"
        self.attack_percent: float = 0.0
        self.defense_percent: float = 0.0
        self.speed_percent: float = 0.0
        self._applied_entities: set[int] = set()

    def apply_config(self, config, skill_name, priority=0):
        super().apply_config(config, skill_name, priority)
        self.target_type = config.get("target", "enemies")
        self.attack_percent = config.get("attack_percent", 0.0)
        self.defense_percent = config.get("defense_percent", 0.0)
        self.speed_percent = config.get("speed_percent", 0.0)

    def on_turn_start(self, attacker, context):
        entity_id = id(attacker)
        if entity_id in self._applied_entities:
            return ""
        self._applied_entities.add(entity_id)

        targets = self._resolve_targets(attacker, context)
        if not targets:
            return self._get_log_message(attacker)

        for target in targets:
            self._apply_aura_to(target)

        return self._get_log_message(attacker)

    def _resolve_targets(self, attacker, context):
        """오라 대상 결정"""
        if context is None:
            return []

        # context가 CombatContext인 경우
        if self.target_type == "enemies":
            # 몬스터 → 유저: context에서 user 찾기
            if hasattr(context, 'user'):
                return [context.user]
            return []

        # allies: 같은 편 몬스터 (자신 제외)
        if hasattr(context, 'get_all_alive_monsters'):
            return [m for m in context.get_all_alive_monsters() if id(m) != id(attacker)]
        return []

    def _apply_aura_to(self, target):
        """대상에게 영구 디버프 적용"""
        stat = target.get_stat()
        duration = COMBAT.PERMANENT_BUFF_DURATION

        if self.attack_percent != 0:
            amount = int(stat[UserStatEnum.ATTACK] * self.attack_percent)
            buff = AttackBuff()
            buff.amount = amount
            buff.duration = duration
            buff.is_debuff = True
            target.status.append(buff)

        if self.defense_percent != 0:
            amount = int(stat[UserStatEnum.DEFENSE] * self.defense_percent)
            buff = DefenseBuff()
            buff.amount = amount
            buff.duration = duration
            buff.is_debuff = True
            target.status.append(buff)

        if self.speed_percent != 0:
            amount = int(stat[UserStatEnum.SPEED] * self.speed_percent)
            buff = SpeedBuff()
            buff.amount = amount
            buff.duration = duration
            buff.is_debuff = True
            target.status.append(buff)

    def _get_log_message(self, attacker) -> str:
        effects = []
        if self.attack_percent != 0:
            effects.append(f"공격력 {int(self.attack_percent * 100)}%")
        if self.defense_percent != 0:
            effects.append(f"방어력 {int(self.defense_percent * 100)}%")
        if self.speed_percent != 0:
            effects.append(f"속도 {int(self.speed_percent * 100)}%")

        if not effects:
            return ""

        target_text = "적" if self.target_type == "enemies" else "아군"
        return (
            f"🌟 **{attacker.get_name()}** 패시브 「{self.skill_name}」 → "
            f"{target_text} {', '.join(effects)}"
        )


@register_skill_with_tag("passive_aura_buff")
class AuraBuffComponent(SkillComponent):
    """
    오라 버프 패시브 - 전투 시작 시 아군에게 영구 버프

    Config options:
        target (str): "allies" (아군) 또는 "enemies" (적)
        attack_percent (float): 공격력 증가율 (예: 0.1 = +10%)
        defense_percent (float): 방어력 증가율
        speed_percent (float): 속도 증가율
    """

    def __init__(self):
        super().__init__()
        self.target_type: str = "allies"
        self.attack_percent: float = 0.0
        self.defense_percent: float = 0.0
        self.speed_percent: float = 0.0
        self._applied_entities: set[int] = set()

    def apply_config(self, config, skill_name, priority=0):
        super().apply_config(config, skill_name, priority)
        self.target_type = config.get("target", "allies")
        self.attack_percent = config.get("attack_percent", 0.0)
        self.defense_percent = config.get("defense_percent", 0.0)
        self.speed_percent = config.get("speed_percent", 0.0)

    def on_turn_start(self, attacker, context):
        entity_id = id(attacker)
        if entity_id in self._applied_entities:
            return ""
        self._applied_entities.add(entity_id)

        targets = self._resolve_targets(attacker, context)
        if not targets:
            return self._get_log_message(attacker)

        for target in targets:
            self._apply_aura_to(target)

        return self._get_log_message(attacker)

    def _resolve_targets(self, attacker, context):
        if context is None:
            return []

        if self.target_type == "allies":
            if hasattr(context, 'get_all_alive_monsters'):
                return [m for m in context.get_all_alive_monsters() if id(m) != id(attacker)]
            return []

        # enemies: 유저에게 적용
        if hasattr(context, 'user'):
            return [context.user]
        return []

    def _apply_aura_to(self, target):
        stat = target.get_stat()
        duration = COMBAT.PERMANENT_BUFF_DURATION

        if self.attack_percent != 0:
            amount = int(stat[UserStatEnum.ATTACK] * self.attack_percent)
            buff = AttackBuff()
            buff.amount = amount
            buff.duration = duration
            target.status.append(buff)

        if self.defense_percent != 0:
            amount = int(stat[UserStatEnum.DEFENSE] * self.defense_percent)
            buff = DefenseBuff()
            buff.amount = amount
            buff.duration = duration
            target.status.append(buff)

        if self.speed_percent != 0:
            amount = int(stat[UserStatEnum.SPEED] * self.speed_percent)
            buff = SpeedBuff()
            buff.amount = amount
            buff.duration = duration
            target.status.append(buff)

    def _get_log_message(self, attacker) -> str:
        effects = []
        if self.attack_percent != 0:
            effects.append(f"공격력 +{int(self.attack_percent * 100)}%")
        if self.defense_percent != 0:
            effects.append(f"방어력 +{int(self.defense_percent * 100)}%")
        if self.speed_percent != 0:
            effects.append(f"속도 +{int(self.speed_percent * 100)}%")

        if not effects:
            return ""

        target_text = "아군" if self.target_type == "allies" else "적"
        return (
            f"🌟 **{attacker.get_name()}** 패시브 「{self.skill_name}」 → "
            f"{target_text} {', '.join(effects)}"
        )
