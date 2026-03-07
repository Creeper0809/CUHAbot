"""
스탯 컴포넌트: BuffComponent, DebuffComponent, PassiveBuffComponent,
              TurnScalingComponent, DebuffReductionComponent
"""
import random

from models import UserStatEnum
from service.dungeon.components.base import SkillComponent, register_skill_with_tag
from service.dungeon.components.targeting_utils import resolve_targets
from service.dungeon.status import (
    AttackBuff, DefenseBuff, SpeedBuff, AccuracyBuff, EvasionBuff,
    HealReceivedBuff, InvulnerabilityBuff,
)
from service.player.stat_synergy_combat import get_buff_duration_bonus
from config import COMBAT


def _normalize_ratio(value: float | int | None, default: float = 0.0) -> float:
    if value is None:
        return default
    ratio = float(value)
    if abs(ratio) > 1:
        ratio /= 100.0
    return ratio


def _scaled_delta(base_value: int, modifier: float) -> int:
    # Ratio-style modifiers (-1.0 ~ 1.0) scale with stat, otherwise treated as absolute.
    if abs(modifier) <= 1:
        return int(base_value * modifier)
    return int(modifier)


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
        self.target_type = "self"
        self.stat_key = ""
        self.stat_value = 0.0

    def apply_config(self, config, skill_name, priority=0):
        super().apply_config(config, skill_name, priority)
        self.duration = config.get("duration", 3)
        self.attack_mod = _normalize_ratio(config.get("attack", 0))
        self.defense_mod = _normalize_ratio(config.get("defense", 0))
        self.speed_mod = _normalize_ratio(config.get("speed", 0))
        self.crit_rate_mod = _normalize_ratio(config.get("crit_rate", 0))
        self.target_type = config.get("target", "self")
        self.stat_key = str(config.get("stat", "")).lower().strip()
        self.stat_value = _normalize_ratio(config.get("value", 0.0))

        # New-format mapping: {"stat":"defense","value":0.15}
        if self.stat_key in {"attack", "defense", "speed"} and self.stat_value != 0:
            if self.stat_key == "attack":
                self.attack_mod = self.stat_value
            elif self.stat_key == "defense":
                self.defense_mod = self.stat_value
            elif self.stat_key == "speed":
                self.speed_mod = self.stat_value
        elif self.stat_key == "all":
            self.attack_mod = self.stat_value
            self.defense_mod = self.stat_value
            self.speed_mod = self.stat_value
        elif self.stat_key == "random_all":
            # Random +/- for each stat, used by some boss gimmicks.
            amt = abs(self.stat_value)
            self.attack_mod = random.uniform(-amt, amt)
            self.defense_mod = random.uniform(-amt, amt)
            self.speed_mod = random.uniform(-amt, amt)
        elif self.stat_key == "random":
            amt = self.stat_value
            chosen = random.choice(["attack", "defense", "speed"])
            if chosen == "attack":
                self.attack_mod = amt
            elif chosen == "defense":
                self.defense_mod = amt
            else:
                self.speed_mod = amt

    def on_turn(self, attacker, target):
        targets = resolve_targets(attacker, target, self.target_type)
        if not targets:
            return ""

        duration = self.duration + get_buff_duration_bonus(attacker)
        per_target_logs = []

        for each in targets:
            each_stat = each.get_stat()
            effects = []

            if self.attack_mod != 0:
                amount = _scaled_delta(each_stat[UserStatEnum.ATTACK], self.attack_mod)
                buff = AttackBuff()
                buff.amount = amount
                buff.duration = duration
                each.status.append(buff)
                effects.append(f"공격력 {amount:+}")

            if self.defense_mod != 0:
                amount = _scaled_delta(each_stat[UserStatEnum.DEFENSE], self.defense_mod)
                buff = DefenseBuff()
                buff.amount = amount
                buff.duration = duration
                each.status.append(buff)
                effects.append(f"방어력 {amount:+}")

            if self.speed_mod != 0:
                amount = _scaled_delta(each_stat[UserStatEnum.SPEED], self.speed_mod)
                buff = SpeedBuff()
                buff.amount = amount
                buff.duration = duration
                each.status.append(buff)
                effects.append(f"속도 {amount:+}")

            if self.stat_key in {"invincible", "invulnerability"}:
                invul = InvulnerabilityBuff()
                invul.duration = duration
                each.status.append(invul)
                effects.append("무적")

            if effects:
                per_target_logs.append(f"**{each.get_name()}**: {', '.join(effects)}")

        if not per_target_logs:
            return ""

        return (
            f"✨ **{attacker.get_name()}** 「{self.skill_name}」 ({duration}턴)\n"
            + "\n".join(per_target_logs)
        )


@register_skill_with_tag("debuff")
class DebuffComponent(SkillComponent):
    """디버프 컴포넌트 - 실제 디버프 Buff를 target.status에 추가"""

    def __init__(self):
        super().__init__()
        self.duration = 3
        self.attack_mod = 0
        self.defense_mod = 0
        self.speed_mod = 0
        self.target_type = "single"
        self.stat_key = ""
        self.stat_value = 0.0

    def apply_config(self, config, skill_name, priority=0):
        super().apply_config(config, skill_name, priority)
        self.duration = config.get("duration", 3)
        self.attack_mod = _normalize_ratio(config.get("attack", 0))
        self.defense_mod = _normalize_ratio(config.get("defense", 0))
        self.speed_mod = _normalize_ratio(config.get("speed", 0))
        self.target_type = config.get("target", "single")
        self.stat_key = str(config.get("stat", "")).lower().strip()
        self.stat_value = _normalize_ratio(config.get("value", 0.0))

        if self.stat_key in {"attack", "defense", "speed"} and self.stat_value != 0:
            if self.stat_key == "attack":
                self.attack_mod = self.stat_value
            elif self.stat_key == "defense":
                self.defense_mod = self.stat_value
            else:
                self.speed_mod = self.stat_value
        elif self.stat_key in {"all", "all_debuffs"}:
            value = self.stat_value if self.stat_value != 0 else -0.15
            self.attack_mod = value
            self.defense_mod = value
            self.speed_mod = value
        elif self.stat_key == "random":
            value = self.stat_value if self.stat_value != 0 else -0.15
            chosen = random.choice(["attack", "defense", "speed"])
            if chosen == "attack":
                self.attack_mod = value
            elif chosen == "defense":
                self.defense_mod = value
            else:
                self.speed_mod = value
        elif self.stat_key == "random_all":
            value = abs(self.stat_value if self.stat_value != 0 else 0.15)
            self.attack_mod = random.uniform(-value, value)
            self.defense_mod = random.uniform(-value, value)
            self.speed_mod = random.uniform(-value, value)

    def on_turn(self, attacker, target):
        targets = resolve_targets(attacker, target, self.target_type)
        if not targets:
            return ""

        per_target_logs = []
        for each in targets:
            each_stat = each.get_stat()
            effects = []

            if self.attack_mod != 0:
                amount = _scaled_delta(each_stat[UserStatEnum.ATTACK], self.attack_mod)
                buff = AttackBuff()
                buff.amount = amount
                buff.duration = self.duration
                buff.is_debuff = True
                each.status.append(buff)
                effects.append(f"공격력 {amount:+}")

            if self.defense_mod != 0:
                amount = _scaled_delta(each_stat[UserStatEnum.DEFENSE], self.defense_mod)
                buff = DefenseBuff()
                buff.amount = amount
                buff.duration = self.duration
                buff.is_debuff = True
                each.status.append(buff)
                effects.append(f"방어력 {amount:+}")

            if self.speed_mod != 0:
                amount = _scaled_delta(each_stat[UserStatEnum.SPEED], self.speed_mod)
                buff = SpeedBuff()
                buff.amount = amount
                buff.duration = self.duration
                buff.is_debuff = True
                each.status.append(buff)
                effects.append(f"속도 {amount:+}")

            if self.stat_key in {"accuracy", "evasion"}:
                points = int(self.stat_value * 100) if abs(self.stat_value) <= 1 else int(self.stat_value)
                if self.stat_key == "accuracy":
                    buff = AccuracyBuff()
                    buff.amount = points
                    buff.duration = self.duration
                    buff.is_debuff = True
                    each.status.append(buff)
                    effects.append(f"명중률 {points:+}%")
                else:
                    buff = EvasionBuff()
                    buff.amount = points
                    buff.duration = self.duration
                    buff.is_debuff = True
                    each.status.append(buff)
                    effects.append(f"회피율 {points:+}%")

            if self.stat_key in {"heal_received", "heal_block"}:
                heal_mod = self.stat_value
                if self.stat_key == "heal_block":
                    heal_mod = -1.0 if heal_mod == 0 else heal_mod
                hb = HealReceivedBuff()
                hb.amount = heal_mod
                hb.duration = self.duration
                hb.is_debuff = True
                each.status.append(hb)
                effects.append(f"회복량 {int(heal_mod * 100):+}%")

            if effects:
                per_target_logs.append(f"**{each.get_name()}**: {', '.join(effects)}")

        if not per_target_logs:
            return ""

        return (
            f"🔮 **{attacker.get_name()}** 「{self.skill_name}」 ({self.duration}턴)\n"
            + "\n".join(per_target_logs)
        )


@register_skill_with_tag("passive_buff")
class PassiveBuffComponent(SkillComponent):
    """
    패시브 버프 컴포넌트 - 장착 시 영구 스탯 보너스

    스탯 보너스는 get_stat()에서 get_passive_stat_bonuses()를 통해 적용됩니다.
    on_turn_start()는 전투 시작 시 로그 출력용으로만 사용됩니다.

    Config options:
        attack_percent (float): 공격력 증가 비율 (예: 0.2 = +20%)
        defense_percent (float): 방어력 증가 비율
        speed_percent (float): 속도 증가 비율
        hp_percent (float): HP 증가 비율
        evasion_percent (float): 회피율 증가 (예: 0.15 = +15%)
        ap_attack_percent (float): 마법 공격력 증가 비율
        crit_rate (float): 치명타 확률 증가
    """

    # 스탯 메타데이터 (컴포넌트가 자기 스탯 정보를 제공)
    STAT_METADATA = {
        "accuracy": {"label": "명중률", "suffix": "%", "prefix": "", "is_ratio": False},
        "evasion": {"label": "회피율", "suffix": "%", "prefix": "", "is_ratio": False},
        "crit_rate": {"label": "치명타율", "suffix": "%", "prefix": "", "is_ratio": False},
        "crit_damage": {"label": "치명타배율", "suffix": "%", "prefix": "", "is_ratio": False},
        "drop_rate": {"label": "드롭률", "suffix": "%", "prefix": "+", "is_ratio": True},
        "lifesteal": {"label": "흡혈", "suffix": "%", "prefix": "", "is_ratio": True},
        "armor_pen": {"label": "방어 관통", "suffix": "%", "prefix": "", "is_ratio": False},
        "magic_pen": {"label": "마법 관통", "suffix": "%", "prefix": "", "is_ratio": False},
        "fire_resist": {"label": "화염 저항", "suffix": "%", "prefix": "", "is_ratio": False},
        "ice_resist": {"label": "냉기 저항", "suffix": "%", "prefix": "", "is_ratio": False},
        "lightning_resist": {"label": "번개 저항", "suffix": "%", "prefix": "", "is_ratio": False},
        "water_resist": {"label": "수속성 저항", "suffix": "%", "prefix": "", "is_ratio": False},
        "holy_resist": {"label": "신성 저항", "suffix": "%", "prefix": "", "is_ratio": False},
        "dark_resist": {"label": "암흑 저항", "suffix": "%", "prefix": "", "is_ratio": False},
        "block_rate": {"label": "블록률", "suffix": "%", "prefix": "", "is_ratio": False},
        "exp_bonus": {"label": "경험치 보너스", "suffix": "%", "prefix": "+", "is_ratio": False},
        "fire_damage": {"label": "화염 공격력", "suffix": "%", "prefix": "+", "is_ratio": False},
        "ice_damage": {"label": "냉기 공격력", "suffix": "%", "prefix": "+", "is_ratio": False},
        "lightning_damage": {"label": "번개 공격력", "suffix": "%", "prefix": "+", "is_ratio": False},
        "water_damage": {"label": "수속성 공격력", "suffix": "%", "prefix": "+", "is_ratio": False},
        "holy_damage": {"label": "신성 공격력", "suffix": "%", "prefix": "+", "is_ratio": False},
        "dark_damage": {"label": "암흑 공격력", "suffix": "%", "prefix": "+", "is_ratio": False},
    }

    def __init__(self):
        super().__init__()
        self.attack_percent = 0.0
        self.hp_percent = 0.0
        self.defense_percent = 0.0
        self.speed_percent = 0.0
        self.evasion_percent = 0.0
        self.ap_attack_percent = 0.0
        self.crit_rate = 0.0
        self.crit_damage = 0.0
        self.lifesteal = 0.0
        self.drop_rate = 0.0
        self._applied_entities: set[int] = set()
        self._raw_config: dict = {}

    def apply_config(self, config, skill_name, priority=0):
        super().apply_config(config, skill_name, priority)
        self._raw_config = {k: v for k, v in config.items() if k != "tag"}
        self.attack_percent = config.get("attack_percent", 0.0)
        self.hp_percent = config.get("hp_percent", 0.0)
        self.defense_percent = config.get("defense_percent", 0.0)
        self.speed_percent = config.get("speed_percent", 0.0)
        self.evasion_percent = config.get("evasion_percent", 0.0) or config.get("evasion", 0.0)
        self.ap_attack_percent = config.get("ap_attack_percent", 0.0)
        self.crit_rate = config.get("crit_rate", 0.0)
        self.crit_damage = config.get("crit_damage", 0.0)
        self.lifesteal = config.get("lifesteal", 0.0)
        self.drop_rate = config.get("drop_rate", 0.0)

    def get_displayable_stats(self) -> dict:
        """
        UI에 표시할 수 있는 스탯 반환 (비지터 패턴)

        컴포넌트가 자기 자신의 스탯 정보(값 + 메타데이터)를 제공합니다.
        새로운 스탯 추가 시 STAT_METADATA에만 추가하면 UI에 자동 반영됩니다.

        Returns:
            {
                "stat_key": {
                    "value": float,
                    "metadata": {"label": str, "suffix": str, ...}
                }
            }
        """
        result = {}
        for stat_key, value in self._raw_config.items():
            if stat_key in self.STAT_METADATA and value > 0:
                result[stat_key] = {
                    "value": value,
                    "metadata": self.STAT_METADATA[stat_key]
                }
        return result

    def on_turn_start(self, attacker, target):
        """전투 시작 시 패시브 발동 로그 출력 (스탯은 get_stat()에서 이미 적용)"""
        entity_id = id(attacker)
        if entity_id in self._applied_entities:
            return ""
        self._applied_entities.add(entity_id)

        def _format_percent(value: float) -> int:
            """퍼센트 표기용 값 정규화 (0~1 범위는 비율, 1 초과는 이미 퍼센트)"""
            return int(value * 100) if abs(value) <= 1 else int(value)

        effects = []
        if self.attack_percent != 0:
            effects.append(f"공격력 +{int(self.attack_percent * 100)}%")
        if self.defense_percent != 0:
            effects.append(f"방어력 +{int(self.defense_percent * 100)}%")
        if self.speed_percent != 0:
            effects.append(f"속도 +{int(self.speed_percent * 100)}%")
        if self.hp_percent != 0:
            effects.append(f"HP +{int(self.hp_percent * 100)}%")
        if self.evasion_percent != 0:
            effects.append(f"회피 +{int(self.evasion_percent * 100)}%")
        if self.ap_attack_percent != 0:
            effects.append(f"마공 +{int(self.ap_attack_percent * 100)}%")
        if self.crit_rate != 0:
            effects.append(f"치명타 +{int(self.crit_rate * 100)}%")
        if self.crit_damage != 0:
            effects.append(f"치명타배율 +{int(self.crit_damage * 100)}%")
        if self.lifesteal != 0:
            effects.append(f"흡혈 +{_format_percent(self.lifesteal)}%")
        if self.drop_rate != 0:
            effects.append(f"드롭률 +{int(self.drop_rate * 100)}%")

        if not effects:
            return ""

        return f"🌟 **{attacker.get_name()}** 패시브 「{self.skill_name}」 → {', '.join(effects)}"


@register_skill_with_tag("passive_regen")
class PassiveRegenComponent(SkillComponent):
    """
    패시브 재생 컴포넌트 - 매 턴 HP% 회복

    전투 루프에서 매 턴 process_passive_effects()를 통해 호출됩니다.

    Config options:
        percent (float): 최대 HP 대비 회복 비율 (예: 0.02 = 2%)
    """

    def __init__(self):
        super().__init__()
        self.percent = 0.0

    def apply_config(self, config, skill_name, priority=0):
        super().apply_config(config, skill_name, priority)
        self.percent = config.get("percent", 0.0)

    def process_regen(self, entity) -> str:
        """매 턴 HP 재생 처리"""
        if self.percent <= 0:
            return ""

        max_hp = entity.get_stat().get(UserStatEnum.HP, getattr(entity, 'hp', 0))
        heal = int(max_hp * self.percent)
        if heal <= 0:
            return ""

        old_hp = entity.now_hp
        entity.now_hp = min(entity.now_hp + heal, max_hp)
        actual = entity.now_hp - old_hp
        if actual <= 0:
            return ""

        return f"💚 **{entity.get_name()}** 「{self.skill_name}」 HP +{actual} 회복"

    def on_turn_start(self, attacker, target):
        """전투 시작 시 로그 출력"""
        if self.percent <= 0:
            return ""
        return f"🌟 **{attacker.get_name()}** 패시브 「{self.skill_name}」 → 매 턴 HP {int(self.percent * 100)}% 회복"


@register_skill_with_tag("conditional_passive")
class ConditionalPassiveComponent(SkillComponent):
    """
    조건부 패시브 컴포넌트 - HP 조건 충족 시 1회 영구 버프

    전투 루프에서 매 턴 process_conditional()를 통해 호출됩니다.

    Config options:
        hp_threshold (float): HP 임계값 (예: 0.3 = 30% 이하일 때 발동)
        attack_percent (float): 공격력 증가 비율
        defense_percent (float): 방어력 증가 비율
        speed_percent (float): 속도 증가 비율
    """

    def __init__(self):
        super().__init__()
        self.hp_threshold = 0.5
        self.attack_percent = 0.0
        self.defense_percent = 0.0
        self.speed_percent = 0.0
        self._applied_entities: set[int] = set()

    def apply_config(self, config, skill_name, priority=0):
        super().apply_config(config, skill_name, priority)
        self.hp_threshold = config.get("hp_threshold", 0.5)
        self.attack_percent = config.get("attack_percent", 0.0)
        self.defense_percent = config.get("defense_percent", 0.0)
        self.speed_percent = config.get("speed_percent", 0.0)

    def process_conditional(self, entity) -> str:
        """매 턴 HP 조건 체크, 충족 시 1회 영구 버프 적용"""
        entity_id = id(entity)
        if entity_id in self._applied_entities:
            return ""

        max_hp = entity.get_stat().get(UserStatEnum.HP, getattr(entity, 'hp', 0))
        if max_hp <= 0:
            return ""

        hp_ratio = entity.now_hp / max_hp
        if hp_ratio > self.hp_threshold:
            return ""

        # 조건 충족 → 영구 버프 적용
        self._applied_entities.add(entity_id)
        stat = entity.get_stat()
        effects = []
        duration = COMBAT.PERMANENT_BUFF_DURATION

        if self.attack_percent != 0:
            amount = int(stat[UserStatEnum.ATTACK] * self.attack_percent)
            buff = AttackBuff()
            buff.amount = amount
            buff.duration = duration
            entity.status.append(buff)
            effects.append(f"공격력 +{amount}")

        if self.defense_percent != 0:
            amount = int(stat[UserStatEnum.DEFENSE] * self.defense_percent)
            buff = DefenseBuff()
            buff.amount = amount
            buff.duration = duration
            entity.status.append(buff)
            effects.append(f"방어력 +{amount}")

        if self.speed_percent != 0:
            amount = int(stat[UserStatEnum.SPEED] * self.speed_percent)
            buff = SpeedBuff()
            buff.amount = amount
            buff.duration = duration
            entity.status.append(buff)
            effects.append(f"속도 +{amount}")

        if not effects:
            return ""

        threshold_pct = int(self.hp_threshold * 100)
        return f"⚡ **{entity.get_name()}** 「{self.skill_name}」 발동! (HP {threshold_pct}% 이하) → {', '.join(effects)}"

    def on_turn_start(self, attacker, target):
        """전투 시작 시 로그 출력"""
        threshold_pct = int(self.hp_threshold * 100)
        effects = []
        if self.attack_percent != 0:
            effects.append(f"공격력 +{int(self.attack_percent * 100)}%")
        if self.defense_percent != 0:
            effects.append(f"방어력 +{int(self.defense_percent * 100)}%")
        if self.speed_percent != 0:
            effects.append(f"속도 +{int(self.speed_percent * 100)}%")
        if not effects:
            return ""
        return f"🌟 **{attacker.get_name()}** 패시브 「{self.skill_name}」 → HP {threshold_pct}% 이하 시 {', '.join(effects)}"


# 스탯 Enum → Buff 클래스 매핑
_STAT_BUFF_MAP = {
    "attack": (UserStatEnum.ATTACK, AttackBuff),
    "defense": (UserStatEnum.DEFENSE, DefenseBuff),
    "speed": (UserStatEnum.SPEED, SpeedBuff),
}


@register_skill_with_tag("passive_turn_scaling")
class TurnScalingComponent(SkillComponent):
    """
    턴 성장 패시브 - 매 턴 스탯이 증가

    Config options:
        stat (str): 증가할 스탯 ("attack", "defense", "speed")
        percent_per_turn (float): 턴당 증가율 (예: 0.05 = 기본 스탯의 5%)
    """

    def __init__(self):
        super().__init__()
        self.stat: str = "attack"
        self.percent_per_turn: float = 0.05
        self._base_stats: dict[int, int] = {}
        self._turn_counts: dict[int, int] = {}
        self._applied_entities: set[int] = set()

    def apply_config(self, config, skill_name, priority=0):
        super().apply_config(config, skill_name, priority)
        self.stat = config.get("stat", "attack")
        self.percent_per_turn = config.get("percent_per_turn", 0.05)

    def process_turn_scaling(self, entity) -> str:
        """매 턴 스탯 증가 버프 추가"""
        entity_id = id(entity)

        stat_info = _STAT_BUFF_MAP.get(self.stat)
        if not stat_info:
            return ""

        stat_enum, buff_class = stat_info

        # 첫 호출 시 기본 스탯 저장 (복리 방지)
        if entity_id not in self._base_stats:
            self._base_stats[entity_id] = entity.get_stat().get(stat_enum, 0)

        self._turn_counts[entity_id] = self._turn_counts.get(entity_id, 0) + 1

        base = self._base_stats[entity_id]
        increment = max(1, int(base * self.percent_per_turn))

        buff = buff_class()
        buff.amount = increment
        buff.duration = COMBAT.PERMANENT_BUFF_DURATION
        entity.status.append(buff)

        turn = self._turn_counts[entity_id]
        total = increment * turn
        return f"📈 **{entity.get_name()}** 「{self.skill_name}」 {self.stat} +{increment} (누적 +{total})"

    def on_turn_start(self, attacker, target):
        entity_id = id(attacker)
        if entity_id in self._applied_entities:
            return ""
        self._applied_entities.add(entity_id)
        return (
            f"🌟 **{attacker.get_name()}** 패시브 「{self.skill_name}」 → "
            f"매 턴 {self.stat} +{int(self.percent_per_turn * 100)}%"
        )


@register_skill_with_tag("passive_debuff_reduction")
class DebuffReductionComponent(SkillComponent):
    """
    디버프 감소 패시브 - 받는 디버프 지속시간 감소

    damage_pipeline.py의 get_debuff_reduction()에서 스캔됩니다.
    helpers.py의 apply_status_effect()에서 duration 감소 적용.

    Config options:
        reduction_percent (float): 지속시간 감소율 (예: 0.5 = 50%)
    """

    def __init__(self):
        super().__init__()
        self.reduction_percent: float = 0.0
        self._applied_entities: set[int] = set()

    def apply_config(self, config, skill_name, priority=0):
        super().apply_config(config, skill_name, priority)
        self.reduction_percent = config.get("reduction_percent", 0.0)

    def on_turn_start(self, attacker, target):
        entity_id = id(attacker)
        if entity_id in self._applied_entities:
            return ""
        self._applied_entities.add(entity_id)

        if self.reduction_percent <= 0:
            return ""
        return (
            f"🌟 **{attacker.get_name()}** 패시브 「{self.skill_name}」 → "
            f"디버프 지속시간 -{int(self.reduction_percent * 100)}%"
        )
