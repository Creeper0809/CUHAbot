"""
특수 장비 효과 컴포넌트

랜덤 효과, HP 회복, 전투 성장 등 특수한 장비 효과들입니다.
"""
import random
from typing import Optional
from service.dungeon.components.base import SkillComponent, register_skill_with_tag


@register_skill_with_tag("random_attribute")
class RandomAttributeComponent(SkillComponent):
    """
    랜덤 속성 부여 컴포넌트 (장비 전용 패시브)

    매 전투 또는 매 공격마다 랜덤 속성을 부여하거나
    랜덤 속성 데미지를 증가시킵니다.

    Config options:
        mode (str): "per_combat" (전투마다) 또는 "per_attack" (공격마다)
        damage_bonus (float): 랜덤 속성 데미지 보너스 (예: 0.3 = 30%)
        attributes (list): 랜덤 선택할 속성 리스트 (기본: 전체 속성)
    """

    def __init__(self):
        super().__init__()
        self.mode = "per_combat"
        self.damage_bonus = 0.0
        self.attributes = ["화염", "냉기", "번개", "수속성", "신성", "암흑"]
        self._current_attribute = None

    def apply_config(self, config, skill_name, priority=0):
        super().apply_config(config, skill_name, priority)
        self.mode = config.get("mode", "per_combat")
        self.damage_bonus = config.get("damage_bonus", 0.0)
        self.attributes = config.get("attributes", self.attributes)

    def on_combat_start(self, attacker, target):
        """전투 시작 시 랜덤 속성 선택 (per_combat 모드)"""
        if self.mode == "per_combat" and self._current_attribute is None:
            self._current_attribute = random.choice(self.attributes)
            return f"🎲 **{attacker.get_name()}** 랜덤 속성: {self._current_attribute} (+{int(self.damage_bonus * 100)}%)"
        return ""

    def on_turn(self, attacker, target):
        """공격마다 랜덤 속성 선택 (per_attack 모드)"""
        if self.mode == "per_attack":
            self._current_attribute = random.choice(self.attributes)
            return f"🎲 랜덤 속성: {self._current_attribute}"
        return ""

    def get_current_attribute(self) -> Optional[str]:
        """현재 활성화된 랜덤 속성 반환"""
        return self._current_attribute

    def get_attribute_damage_multiplier(self, skill_attribute: str) -> float:
        """
        속성 매칭 시 데미지 배율 반환

        Args:
            skill_attribute: 스킬의 속성

        Returns:
            1.0 + damage_bonus if attributes match, else 1.0
        """
        if self._current_attribute and skill_attribute == self._current_attribute:
            return 1.0 + self.damage_bonus
        return 1.0


@register_skill_with_tag("random_damage_variance")
class RandomDamageVarianceComponent(SkillComponent):
    """
    랜덤 데미지 변동 컴포넌트 (장비 전용 패시브)

    데미지 변동폭을 크게 증가시켜 도박 효과를 만듭니다.

    Config options:
        min_multiplier (float): 최소 데미지 배율 (예: 0.5 = 50%)
        max_multiplier (float): 최대 데미지 배율 (예: 2.0 = 200%)
    """

    def __init__(self):
        super().__init__()
        self.min_multiplier = 0.7
        self.max_multiplier = 1.3

    def apply_config(self, config, skill_name, priority=0):
        super().apply_config(config, skill_name, priority)
        self.min_multiplier = config.get("min_multiplier", 0.7)
        self.max_multiplier = config.get("max_multiplier", 1.3)

    def on_turn(self, attacker, target):
        """패시브이므로 직접 호출되지 않음"""
        return ""

    def get_damage_variance_multiplier(self) -> float:
        """
        랜덤 데미지 배율 반환

        Returns:
            min_multiplier ~ max_multiplier 사이의 랜덤 값
        """
        return random.uniform(self.min_multiplier, self.max_multiplier)


@register_skill_with_tag("on_kill_heal")
class OnKillHealComponent(SkillComponent):
    """
    처치 시 HP 회복 컴포넌트 (장비 전용 패시브)

    적을 처치할 때마다 HP를 회복합니다.

    Config options:
        heal_percent (float): 회복량 (최대 HP 대비 비율, 예: 0.2 = 20%)
        heal_flat (int): 고정 회복량 (선택)
    """

    def __init__(self):
        super().__init__()
        self.heal_percent = 0.0
        self.heal_flat = 0

    def apply_config(self, config, skill_name, priority=0):
        super().apply_config(config, skill_name, priority)
        self.heal_percent = config.get("heal_percent", 0.0)
        self.heal_flat = config.get("heal_flat", 0)

    def on_turn(self, attacker, target):
        """패시브이므로 직접 호출되지 않음"""
        return ""

    def on_death(self, dying_entity, killer):
        """
        적 처치 시 HP 회복

        Note: 이 훅은 전투 시스템에서 적이 죽을 때 호출됩니다.
        """
        if killer == dying_entity:
            return ""

        from models import UserStatEnum

        max_hp = killer.get_stat().get(UserStatEnum.HP, killer.hp)
        heal_amount = int(max_hp * self.heal_percent) + self.heal_flat

        if heal_amount <= 0:
            return ""

        old_hp = killer.now_hp
        killer.now_hp = min(killer.now_hp + heal_amount, max_hp)
        actual_heal = killer.now_hp - old_hp

        if actual_heal > 0:
            return f"💚 **{killer.get_name()}** 처치 시 HP 회복: +{actual_heal}"

        return ""


@register_skill_with_tag("combat_stat_growth")
class CombatStatGrowthComponent(SkillComponent):
    """
    전투 중 스탯 성장 컴포넌트 (장비 전용 패시브)

    전투 중 매 턴마다 또는 특정 조건 시 스탯이 영구 증가합니다.

    Config options:
        stat (str): 증가할 스탯 (예: "attack", "defense", "speed")
        growth_per_turn (float): 턴당 증가량 (비율, 예: 0.05 = 5%)
        max_stacks (int): 최대 스택 수 (0 = 무제한)
        trigger (str): 발동 조건 ("per_turn", "on_hit", "on_damaged")
    """

    def __init__(self):
        super().__init__()
        self.stat = "attack"
        self.growth_per_turn = 0.0
        self.max_stacks = 0
        self.trigger = "per_turn"
        self._current_stacks = 0

    def apply_config(self, config, skill_name, priority=0):
        super().apply_config(config, skill_name, priority)
        self.stat = config.get("stat", "attack")
        self.growth_per_turn = config.get("growth_per_turn", 0.0)
        self.max_stacks = config.get("max_stacks", 0)
        self.trigger = config.get("trigger", "per_turn")

    def on_turn(self, attacker, target):
        """매 턴 스탯 증가 (trigger="per_turn")"""
        if self.trigger == "per_turn":
            return self._add_stack(attacker)
        return ""

    def _add_stack(self, entity) -> str:
        """스택 추가"""
        if self.max_stacks > 0 and self._current_stacks >= self.max_stacks:
            return ""

        self._current_stacks += 1
        bonus_pct = self.growth_per_turn * self._current_stacks * 100

        return (
            f"⚔️ **{entity.get_name()}** 전투 성장! "
            f"{self.stat} +{bonus_pct:.0f}% (스택: {self._current_stacks})"
        )

    def get_stat_bonus(self) -> dict:
        """현재 스택에 따른 스탯 보너스 반환"""
        if self._current_stacks == 0:
            return {}

        return {
            self.stat: self.growth_per_turn * self._current_stacks
        }


@register_skill_with_tag("conditional_stat_bonus")
class ConditionalStatBonusComponent(SkillComponent):
    """
    조건부 스탯 보너스 컴포넌트 (장비 전용 패시브)

    특정 조건을 만족할 때 스탯 보너스를 얻습니다.

    Config options:
        condition (str): 조건 타입
            - "high_hp": HP가 높을수록 보너스 (예: HP 80% 이상)
            - "low_hp": HP가 낮을수록 보너스 (예: HP 30% 이하)
            - "balanced_hp": HP가 50%에 가까울수록 보너스
        stat (str): 보너스를 받을 스탯
        bonus_amount (float): 보너스 양 (비율)
        threshold_high (float): 상한 임계값 (high_hp용)
        threshold_low (float): 하한 임계값 (low_hp용)
    """

    def __init__(self):
        super().__init__()
        self.condition = "high_hp"
        self.stat = "attack"
        self.bonus_amount = 0.0
        self.threshold_high = 0.8
        self.threshold_low = 0.3

    def apply_config(self, config, skill_name, priority=0):
        super().apply_config(config, skill_name, priority)
        self.condition = config.get("condition", "high_hp")
        self.stat = config.get("stat", "attack")
        self.bonus_amount = config.get("bonus_amount", 0.0)
        self.threshold_high = config.get("threshold_high", 0.8)
        self.threshold_low = config.get("threshold_low", 0.3)

    def on_turn(self, attacker, target):
        """패시브이므로 직접 호출되지 않음"""
        return ""

    def get_conditional_stat_multiplier(self, entity) -> float:
        """
        조건에 따른 스탯 배율 반환

        Args:
            entity: 대상 엔티티

        Returns:
            1.0 + bonus if condition met, else 1.0
        """
        from models import UserStatEnum

        max_hp = entity.get_stat().get(UserStatEnum.HP, entity.hp)
        now_hp = entity.now_hp
        hp_ratio = now_hp / max_hp if max_hp > 0 else 1.0

        if self.condition == "high_hp":
            # HP가 높을수록 보너스 (임계값 이상일 때만)
            if hp_ratio >= self.threshold_high:
                return 1.0 + self.bonus_amount

        elif self.condition == "low_hp":
            # HP가 낮을수록 보너스 (임계값 이하일 때만)
            if hp_ratio <= self.threshold_low:
                # HP가 더 낮을수록 보너스 증가
                intensity = (self.threshold_low - hp_ratio) / self.threshold_low
                return 1.0 + (self.bonus_amount * (1 + intensity))

        elif self.condition == "balanced_hp":
            # HP 50%에 가까울수록 보너스
            distance_from_half = abs(hp_ratio - 0.5)
            if distance_from_half <= 0.1:  # 40%~60% 범위
                # 50%에 가까울수록 보너스 증가
                proximity = 1.0 - (distance_from_half / 0.1)
                return 1.0 + (self.bonus_amount * proximity)

        return 1.0


@register_skill_with_tag("sacrifice_effect")
class SacrificeEffectComponent(SkillComponent):
    """
    희생 효과 컴포넌트 (장비 전용 패시브)

    HP를 소모하여 강력한 효과를 얻습니다.

    Config options:
        hp_cost_percent (float): HP 소모량 (최대 HP 대비, 예: 0.1 = 10%)
        buff_duration (int): 버프 지속 시간 (턴)
        stat_bonus (dict): 버프로 얻을 스탯 보너스
    """

    def __init__(self):
        super().__init__()
        self.hp_cost_percent = 0.0
        self.buff_duration = 0
        self.stat_bonus = {}

    def apply_config(self, config, skill_name, priority=0):
        super().apply_config(config, skill_name, priority)
        self.hp_cost_percent = config.get("hp_cost_percent", 0.0)
        self.buff_duration = config.get("buff_duration", 0)
        self.stat_bonus = config.get("stat_bonus", {})

    def on_combat_start(self, attacker, target):
        """
        전투 시작 시 HP 소모 및 버프 적용

        The cost and buffs are applied exactly once at combat start.
        """
        if self.hp_cost_percent <= 0:
            return ""

        from models import UserStatEnum

        max_hp = attacker.get_stat().get(UserStatEnum.HP, attacker.hp)
        hp_cost = int(max_hp * self.hp_cost_percent)

        if attacker.now_hp <= hp_cost:
            return ""

        attacker.now_hp -= hp_cost

        from service.dungeon.status import AttackBuff, DefenseBuff
        for stat, value in self.stat_bonus.items():
            if stat == "attack":
                buff = AttackBuff()
            elif stat in {"defense", "ad_defense"}:
                buff = DefenseBuff()
            else:
                continue
            buff.amount = int(value)
            buff.duration = max(1, self.buff_duration)
            attacker.status.append(buff)

        bonus_desc = ", ".join([f"{k} +{v}%" for k, v in self.stat_bonus.items()])

        return (
            f"🩸 **{attacker.get_name()}** HP {hp_cost} 희생! "
            f"→ {self.buff_duration}턴간 {bonus_desc}"
        )

    def on_turn(self, attacker, target):
        """패시브이므로 직접 호출되지 않음"""
        return ""


@register_skill_with_tag("first_strike")
class FirstStrikeComponent(SkillComponent):
    """
    선공권 컴포넌트 (장비 전용 패시브)

    전투 시작 시 먼저 공격하거나 속도 보너스를 얻습니다.

    Config options:
        speed_bonus (float): 속도 보너스 비율 (예: 0.3 = 30%)
        guaranteed (bool): 확정 선공 여부 (True면 항상 먼저 공격)
        first_turn_bonus (int): 첫 N턴 동안 선공 보장 (0 = 전투 내내)
    """

    def __init__(self):
        super().__init__()
        self.speed_bonus = 0.0
        self.guaranteed = False
        self.first_turn_bonus = 0
        self._current_turn = 0

    def apply_config(self, config, skill_name, priority=0):
        super().apply_config(config, skill_name, priority)
        self.speed_bonus = config.get("speed_bonus", 0.0)
        self.guaranteed = config.get("guaranteed", False)
        self.first_turn_bonus = config.get("first_turn_bonus", 0)

    def on_combat_start(self, attacker, target):
        """전투 시작 시 선공권 적용"""
        self._current_turn = 0
        if self.guaranteed:
            return f"⚡ **{attacker.get_name()}** 선공 확정!"
        elif self.speed_bonus > 0:
            return f"⚡ **{attacker.get_name()}** 속도 +{int(self.speed_bonus * 100)}%"
        return ""

    def on_turn_start(self, attacker, target):
        """턴 시작 시 턴 카운트"""
        self._current_turn += 1
        return ""

    def get_speed_multiplier(self) -> float:
        """
        속도 배율 반환

        Returns:
            1.0 + speed_bonus
        """
        if self.first_turn_bonus > 0 and self._current_turn > self.first_turn_bonus:
            return 1.0
        return 1.0 + self.speed_bonus

    def has_guaranteed_first_strike(self) -> bool:
        """확정 선공 여부 반환"""
        if self.first_turn_bonus > 0:
            return self.guaranteed and self._current_turn <= self.first_turn_bonus
        return self.guaranteed


@register_skill_with_tag("counter_attack")
class CounterAttackComponent(SkillComponent):
    """
    반격 컴포넌트 (장비 전용 패시브)

    피격 시 일정 확률로 자동 반격합니다.

    Config options:
        counter_chance (float): 반격 확률 (예: 0.15 = 15%)
        counter_damage_multiplier (float): 반격 데미지 배율 (예: 0.5 = 50%)
        condition (str): 발동 조건 ("always", "on_melee", "on_defend")
    """

    def __init__(self):
        super().__init__()
        self.counter_chance = 0.0
        self.counter_damage_multiplier = 0.5
        self.condition = "always"

    def apply_config(self, config, skill_name, priority=0):
        super().apply_config(config, skill_name, priority)
        self.counter_chance = config.get("counter_chance", 0.0)
        self.counter_damage_multiplier = config.get("counter_damage_multiplier", 0.5)
        self.condition = config.get("condition", "always")

    def on_damaged(self, defender, attacker, damage: int) -> str:
        """
        피격 시 반격 발동

        Note: 이 훅은 전투 시스템에서 피격 시 호출됩니다.
        """
        if random.random() > self.counter_chance:
            return ""

        # 조건 체크
        if self.condition == "on_defend":
            # 방어 태세 체크 (추후 구현)
            pass

        # 반격 데미지 계산
        from models import UserStatEnum
        attacker_attack = defender.get_stat().get(UserStatEnum.ATTACK, 0)
        counter_damage = int(attacker_attack * self.counter_damage_multiplier)

        if counter_damage <= 0:
            return ""

        # 반격 실행
        actual_damage = attacker.take_damage(counter_damage)

        return (
            f"⚔️ **{defender.get_name()}** 반격! "
            f"**{attacker.get_name()}**에게 {actual_damage} 데미지"
        )


@register_skill_with_tag("extra_attack")
class ExtraAttackComponent(SkillComponent):
    """
    추가 공격 컴포넌트 (장비 전용 패시브)

    공격 후 일정 확률로 즉시 재공격합니다.

    Config options:
        extra_attack_chance (float): 추가 공격 확률 (예: 0.3 = 30%)
        max_chains (int): 최대 연쇄 횟수 (예: 3 = 최대 3회 연쇄)
        damage_multiplier (float): 추가 공격 데미지 배율 (예: 0.7 = 70%)
    """

    def __init__(self):
        super().__init__()
        self.extra_attack_chance = 0.0
        self.max_chains = 1
        self.damage_multiplier = 1.0
        self._chain_count = 0

    def apply_config(self, config, skill_name, priority=0):
        super().apply_config(config, skill_name, priority)
        self.extra_attack_chance = config.get("extra_attack_chance", 0.0)
        self.max_chains = config.get("max_chains", 1)
        self.damage_multiplier = config.get("damage_multiplier", 1.0)

    def on_attack(self, attacker, target, damage: int) -> str:
        """
        공격 후 추가 공격 발동

        Note: 이 훅은 전투 시스템에서 공격 후 호출됩니다.
        """
        # 최대 연쇄 제한
        if self._chain_count >= self.max_chains:
            self._chain_count = 0
            return ""

        # 확률 체크
        if random.random() > self.extra_attack_chance:
            self._chain_count = 0
            return ""

        self._chain_count += 1

        # 추가 공격 데미지 계산
        extra_damage = int(damage * self.damage_multiplier)
        if extra_damage <= 0:
            return ""

        # 추가 공격 실행
        actual_damage = target.take_damage(extra_damage)

        return (
            f"⚡ **{attacker.get_name()}** 연쇄 공격! ({self._chain_count}회) "
            f"**{target.get_name()}**에게 {actual_damage} 추가 데미지"
        )

    def get_chain_count(self) -> int:
        """현재 연쇄 횟수 반환"""
        return self._chain_count


@register_skill_with_tag("regeneration")
class RegenerationComponent(SkillComponent):
    """
    재생 컴포넌트 (장비 전용 패시브)

    매 턴 또는 일정 시간마다 HP를 회복합니다.

    Config options:
        regen_per_turn (float): 턴당 회복량 (최대 HP 대비, 예: 0.05 = 5%)
        regen_flat (int): 고정 회복량 (턴당)
        regen_per_minute (int): 분당 회복량 (전투 외)
        combat_only (bool): 전투 중에만 작동 (기본: True)
    """

    def __init__(self):
        super().__init__()
        self.regen_per_turn = 0.0
        self.regen_flat = 0
        self.regen_per_minute = 0
        self.combat_only = True

    def apply_config(self, config, skill_name, priority=0):
        super().apply_config(config, skill_name, priority)
        self.regen_per_turn = config.get("regen_per_turn", 0.0)
        self.regen_flat = config.get("regen_flat", 0)
        self.regen_per_minute = config.get("regen_per_minute", 0)
        self.combat_only = config.get("combat_only", True)

    def on_turn_start(self, attacker, target):
        """
        턴 시작 시 HP 회복

        Note: 전투 시스템에서 매 턴마다 호출됩니다.
        """
        if self.regen_per_turn <= 0 and self.regen_flat <= 0:
            return ""

        from models import UserStatEnum

        max_hp = attacker.get_stat().get(UserStatEnum.HP, attacker.hp)
        regen_amount = int(max_hp * self.regen_per_turn) + self.regen_flat

        if regen_amount <= 0:
            return ""

        old_hp = attacker.now_hp
        attacker.now_hp = min(attacker.now_hp + regen_amount, max_hp)
        actual_regen = attacker.now_hp - old_hp

        if actual_regen > 0:
            return f"💚 **{attacker.get_name()}** HP 재생: +{actual_regen}"

        return ""

    def get_out_of_combat_regen(self) -> int:
        """전투 외 분당 회복량 반환"""
        if self.combat_only:
            return 0
        return self.regen_per_minute


@register_skill_with_tag("revive")
class ReviveComponent(SkillComponent):
    """
    부활 컴포넌트 (장비 전용 패시브)

    사망 시 자동으로 부활합니다.

    Config options:
        revive_hp_percent (float): 부활 시 HP 비율 (예: 0.5 = 50%, 1.0 = 100%)
        revive_count (int): 부활 가능 횟수 (예: 1 = 1회, 0 = 무제한)
        invincible_turns (int): 부활 후 무적 턴 수 (기본: 0)
    """

    def __init__(self):
        super().__init__()
        self.revive_hp_percent = 0.5
        self.revive_count = 1
        self.invincible_turns = 0
        self._revives_used = 0
        self._invincible_remaining = 0

    def apply_config(self, config, skill_name, priority=0):
        super().apply_config(config, skill_name, priority)
        self.revive_hp_percent = config.get("revive_hp_percent", 0.5)
        self.revive_count = config.get("revive_count", 1)
        self.invincible_turns = config.get("invincible_turns", 0)

    def on_combat_start(self, attacker, target):
        """전투 시작 시 부활 카운트 초기화"""
        self._revives_used = 0
        self._invincible_remaining = 0
        return ""

    def on_death(self, dying_entity, killer):
        """
        사망 시 부활 발동

        Note: 이 훅은 전투 시스템에서 HP가 0이 될 때 호출됩니다.
        """
        # 부활 횟수 체크
        if self.revive_count > 0 and self._revives_used >= self.revive_count:
            return ""

        from models import UserStatEnum

        # 부활
        max_hp = dying_entity.get_stat().get(UserStatEnum.HP, dying_entity.hp)
        revive_hp = int(max_hp * self.revive_hp_percent)
        dying_entity.now_hp = revive_hp

        self._revives_used += 1
        self._invincible_remaining = self.invincible_turns

        remaining_msg = ""
        if self.revive_count > 0:
            remaining = self.revive_count - self._revives_used
            remaining_msg = f" (남은 부활: {remaining}회)"

        invincible_msg = ""
        if self.invincible_turns > 0:
            invincible_msg = f", {self.invincible_turns}턴간 무적"

        return (
            f"✨ **{dying_entity.get_name()}** 부활! "
            f"HP {revive_hp} 회복{invincible_msg}{remaining_msg}"
        )

    def on_turn_start(self, attacker, target):
        """무적 턴 감소"""
        if self._invincible_remaining > 0:
            self._invincible_remaining -= 1
            if self._invincible_remaining == 0:
                return f"🛡️ **{attacker.get_name()}** 무적 종료"
        return ""

    def is_invincible(self) -> bool:
        """현재 무적 상태 여부 반환"""
        return self._invincible_remaining > 0

    def get_remaining_revives(self) -> int:
        """남은 부활 횟수 반환"""
        if self.revive_count == 0:
            return 999  # 무제한
        return max(0, self.revive_count - self._revives_used)


@register_skill_with_tag("thorns_damage")
class ThornsDamageComponent(SkillComponent):
    """
    가시 피해 컴포넌트 (장비 전용 패시브)

    피격 시 고정 데미지를 반사합니다.

    Config options:
        thorns_damage (int): 고정 반사 데미지
        thorns_percent (float): 받은 데미지의 비율로 반사 (예: 0.1 = 10%)
    """

    def __init__(self):
        super().__init__()
        self.thorns_damage = 0
        self.thorns_percent = 0.0

    def apply_config(self, config, skill_name, priority=0):
        super().apply_config(config, skill_name, priority)
        self.thorns_damage = config.get("thorns_damage", 0)
        self.thorns_percent = config.get("thorns_percent", 0.0)

    def on_damaged(self, defender, attacker, damage: int) -> str:
        """
        피격 시 가시 피해 발동

        Note: 이 훅은 전투 시스템에서 피격 시 호출됩니다.
        """
        total_thorns = self.thorns_damage + int(damage * self.thorns_percent)

        if total_thorns <= 0:
            return ""

        # 가시 피해 실행
        actual_damage = attacker.take_damage(total_thorns)

        return (
            f"🌵 **{defender.get_name()}** 가시 피해! "
            f"**{attacker.get_name()}**에게 {actual_damage} 반사 데미지"
        )


@register_skill_with_tag("exploration_speed")
class ExplorationSpeedComponent(SkillComponent):
    """
    탐험 속도 컴포넌트 (장비 전용 패시브)

    던전 탐색 속도 및 채집 속도를 증가시킵니다.

    Config options:
        exploration_speed (float): 탐색 속도 증가율 (예: 0.2 = 20%)
        gathering_speed (float): 채집 속도 증가율 (예: 0.3 = 30%)
        encounter_rate (float): 전투 조우율 변화 (예: -0.1 = -10%, 0.1 = +10%)
    """

    def __init__(self):
        super().__init__()
        self.exploration_speed = 0.0
        self.gathering_speed = 0.0
        self.encounter_rate = 0.0

    def apply_config(self, config, skill_name, priority=0):
        super().apply_config(config, skill_name, priority)
        self.exploration_speed = config.get("exploration_speed", 0.0)
        self.gathering_speed = config.get("gathering_speed", 0.0)
        self.encounter_rate = config.get("encounter_rate", 0.0)

    def get_exploration_speed_multiplier(self) -> float:
        """탐색 속도 배율 반환"""
        return 1.0 + self.exploration_speed

    def get_gathering_speed_multiplier(self) -> float:
        """채집 속도 배율 반환"""
        return 1.0 + self.gathering_speed

    def get_encounter_rate_modifier(self) -> float:
        """전투 조우율 변화량 반환"""
        return self.encounter_rate


@register_skill_with_tag("trap_detection")
class TrapDetectionComponent(SkillComponent):
    """
    함정 감지 컴포넌트 (장비 전용 패시브)

    함정을 감지하거나 피해를 감소시킵니다.

    Config options:
        detection_chance (float): 함정 감지 확률 (예: 0.8 = 80%)
        trap_damage_reduction (float): 함정 피해 감소율 (예: 0.5 = 50%)
        auto_disarm (bool): 감지 시 자동 해제 여부
    """

    def __init__(self):
        super().__init__()
        self.detection_chance = 0.0
        self.trap_damage_reduction = 0.0
        self.auto_disarm = False

    def apply_config(self, config, skill_name, priority=0):
        super().apply_config(config, skill_name, priority)
        self.detection_chance = config.get("detection_chance", 0.0)
        self.trap_damage_reduction = config.get("trap_damage_reduction", 0.0)
        self.auto_disarm = config.get("auto_disarm", False)

    def can_detect_trap(self) -> bool:
        """함정 감지 여부 체크"""
        return random.random() < self.detection_chance

    def get_trap_damage_multiplier(self) -> float:
        """함정 피해 배율 반환"""
        return 1.0 - self.trap_damage_reduction


@register_skill_with_tag("enhancement_bonus")
class EnhancementBonusComponent(SkillComponent):
    """
    강화 보너스 컴포넌트 (장비 전용 패시브)

    강화 성공률 및 기본 강화 수치를 제공합니다.

    Config options:
        enhancement_success_rate (float): 강화 성공률 보너스 (예: 0.05 = +5%)
        base_enhancement (int): 기본 강화 수치 (예: 1 = +1 강화)
        max_enhancement_bonus (int): 최대 강화 한계 증가 (예: 1 = +1 한계)
    """

    def __init__(self):
        super().__init__()
        self.enhancement_success_rate = 0.0
        self.base_enhancement = 0
        self.max_enhancement_bonus = 0

    def apply_config(self, config, skill_name, priority=0):
        super().apply_config(config, skill_name, priority)
        self.enhancement_success_rate = config.get("enhancement_success_rate", 0.0)
        self.base_enhancement = config.get("base_enhancement", 0)
        self.max_enhancement_bonus = config.get("max_enhancement_bonus", 0)

    def get_enhancement_success_bonus(self) -> float:
        """강화 성공률 보너스 반환"""
        return self.enhancement_success_rate

    def get_base_enhancement(self) -> int:
        """기본 강화 수치 반환"""
        return self.base_enhancement


@register_skill_with_tag("durability_bonus")
class DurabilityBonusComponent(SkillComponent):
    """
    내구도 보너스 컴포넌트 (장비 전용 패시브)

    내구도 및 수리 비용을 조절합니다.

    Config options:
        durability_multiplier (float): 내구도 배율 (예: 2.0 = 2배, 3.0 = 3배)
        repair_cost_reduction (float): 수리 비용 감소율 (예: 0.5 = -50%)
        unlimited_repairs (bool): 수리 횟수 무제한 여부
    """

    def __init__(self):
        super().__init__()
        self.durability_multiplier = 1.0
        self.repair_cost_reduction = 0.0
        self.unlimited_repairs = False

    def apply_config(self, config, skill_name, priority=0):
        super().apply_config(config, skill_name, priority)
        self.durability_multiplier = config.get("durability_multiplier", 1.0)
        self.repair_cost_reduction = config.get("repair_cost_reduction", 0.0)
        self.unlimited_repairs = config.get("unlimited_repairs", False)

    def get_durability_multiplier(self) -> float:
        """내구도 배율 반환"""
        return self.durability_multiplier

    def get_repair_cost_multiplier(self) -> float:
        """수리 비용 배율 반환"""
        return 1.0 - self.repair_cost_reduction


@register_skill_with_tag("special_drop_bonus")
class SpecialDropBonusComponent(SkillComponent):
    """
    특수 드롭 보너스 컴포넌트 (장비 전용 패시브)

    특정 아이템 종류의 드롭률을 증가시킵니다.

    Config options:
        item_type (str): 대상 아이템 타입 ("ore", "leather", "herb", "material" 등)
        drop_bonus (float): 드롭률 증가 (예: 0.3 = +30%)
        quality_bonus (float): 드롭 품질 증가 확률 (예: 0.1 = 10%)
    """

    def __init__(self):
        super().__init__()
        self.item_type = ""
        self.drop_bonus = 0.0
        self.quality_bonus = 0.0

    def apply_config(self, config, skill_name, priority=0):
        super().apply_config(config, skill_name, priority)
        self.item_type = config.get("item_type", "")
        self.drop_bonus = config.get("drop_bonus", 0.0)
        self.quality_bonus = config.get("quality_bonus", 0.0)

    def get_drop_rate_multiplier(self, item_type: str) -> float:
        """
        특정 아이템 타입의 드롭률 배율 반환

        Args:
            item_type: 체크할 아이템 타입

        Returns:
            1.0 + drop_bonus if type matches, else 1.0
        """
        if self.item_type and item_type == self.item_type:
            return 1.0 + self.drop_bonus
        return 1.0


@register_skill_with_tag("dungeon_specific_buff")
class DungeonSpecificBuffComponent(SkillComponent):
    """
    던전 특화 버프 컴포넌트 (장비 전용 패시브)

    특정 던전에서만 추가 효과를 받습니다.

    Config options:
        dungeon_ids (list): 대상 던전 ID 리스트 (예: [1, 2, 3])
        dungeon_types (list): 대상 던전 타입 리스트 (예: ["training", "fire"])
        stat_bonuses (dict): 스탯 보너스 (예: {"attack": 20, "defense": 10})
    """

    def __init__(self):
        super().__init__()
        self.dungeon_ids = []
        self.dungeon_types = []
        self.stat_bonuses = {}

    def apply_config(self, config, skill_name, priority=0):
        super().apply_config(config, skill_name, priority)
        self.dungeon_ids = config.get("dungeon_ids", [])
        self.dungeon_types = config.get("dungeon_types", [])
        self.stat_bonuses = config.get("stat_bonuses", {})

    def is_active_in_dungeon(self, dungeon_id: int, dungeon_type: str = "") -> bool:
        """
        특정 던전에서 활성화 여부 확인

        Args:
            dungeon_id: 던전 ID
            dungeon_type: 던전 타입

        Returns:
            해당 던전에서 활성화되면 True
        """
        if self.dungeon_ids and dungeon_id in self.dungeon_ids:
            return True
        if self.dungeon_types and dungeon_type in self.dungeon_types:
            return True
        return False

    def get_stat_bonuses(self) -> dict:
        """스탯 보너스 반환"""
        return self.stat_bonuses


@register_skill_with_tag("heal_blocking")
class HealBlockingComponent(SkillComponent):
    """
    회복 봉인 컴포넌트 (장비 전용)

    대상의 회복을 일정 비율 또는 완전히 봉인합니다.

    Config options:
        block_percent (float): 회복 봉인 비율 (예: 1.0 = 100% 봉인, 0.5 = 50% 감소)
        duration (int): 회복 봉인 지속 턴 수 (0 = 영구)
        on_hit_chance (float): 공격 시 회복 봉인 부여 확률 (예: 0.3 = 30%)
    """

    def __init__(self):
        super().__init__()
        self.block_percent = 1.0
        self.duration = 3
        self.on_hit_chance = 1.0

    def apply_config(self, config, skill_name, priority=0):
        super().apply_config(config, skill_name, priority)
        self.block_percent = config.get("block_percent", 1.0)
        self.duration = config.get("duration", 3)
        self.on_hit_chance = config.get("on_hit_chance", 1.0)

    def on_attack(self, attacker, target, damage: int) -> str:
        """
        공격 시 회복 봉인 디버프 부여

        Note: 이 훅은 전투 시스템에서 공격 후 호출됩니다.
        """
        if random.random() > self.on_hit_chance:
            return ""

        # HealReceivedBuff is consumed directly by HealComponent.  The former
        # code called a non-existent helper and therefore never applied it.
        from service.dungeon.status import HealReceivedBuff

        block_level = int(self.block_percent * 100)
        effect_name = f"회복 봉인 {block_level}%"
        effect = HealReceivedBuff()
        effect.amount = -min(1.0, max(0.0, self.block_percent))
        effect.duration = max(1, self.duration)
        target.status.append(effect)
        return f"🚫 **{target.get_name()}** {effect_name} ({effect.duration}턴)"

    def get_heal_block_multiplier(self) -> float:
        """
        회복 봉인 배율 반환

        Returns:
            0.0 (완전 봉인) ~ 1.0 (봉인 없음)
        """
        return 1.0 - self.block_percent


@register_skill_with_tag("action_prediction")
class ActionPredictionComponent(SkillComponent):
    """
    행동 예측 컴포넌트 (장비 전용)

    적의 다음 행동을 예측하여 정보를 제공합니다.

    Config options:
        prediction_chance (float): 예측 확률 (예: 0.3 = 30%)
        evasion_bonus (float): 예측 성공 시 회피율 보너스 (예: 0.2 = 20%)
        damage_reduction (float): 예측 성공 시 받는 피해 감소 (예: 0.3 = 30%)
    """

    def __init__(self):
        super().__init__()
        self.prediction_chance = 0.3
        self.evasion_bonus = 0.2
        self.damage_reduction = 0.3
        self._predicted_this_turn = False

    def apply_config(self, config, skill_name, priority=0):
        super().apply_config(config, skill_name, priority)
        self.prediction_chance = config.get("prediction_chance", 0.3)
        self.evasion_bonus = config.get("evasion_bonus", 0.2)
        self.damage_reduction = config.get("damage_reduction", 0.3)

    def on_turn_start(self, attacker, target):
        """
        턴 시작 시 적 행동 예측

        Note: 이 훅은 전투 시스템에서 매 턴마다 호출됩니다.
        """
        self._predicted_this_turn = False

        if random.random() > self.prediction_chance:
            return ""

        self._predicted_this_turn = True

        # 적의 다음 스킬 정보 가져오기 (가능하면)
        prediction_msg = f"🔮 **{attacker.get_name()}** {target.get_name()}의 다음 행동 예측!"

        # 예측 성공 시 보너스
        if self.evasion_bonus > 0:
            prediction_msg += f" (회피 +{int(self.evasion_bonus * 100)}%, 피해 -{int(self.damage_reduction * 100)}%)"

        return prediction_msg

    def on_damaged(self, defender, attacker, damage: int) -> str:
        """
        예측 성공 시 피해 감소

        Note: 이 훅은 전투 시스템에서 피격 시 호출됩니다.
        """
        if not self._predicted_this_turn:
            return ""

        reduced_damage = int(damage * self.damage_reduction)
        if reduced_damage > 0:
            return f"🔮 예측 성공! 피해 -{reduced_damage}"

        return ""

    def get_evasion_bonus(self) -> float:
        """예측 성공 시 회피 보너스 반환"""
        if self._predicted_this_turn:
            return self.evasion_bonus
        return 0.0


@register_skill_with_tag("damage_delay")
class DamageDelayComponent(SkillComponent):
    """
    피해 이연 컴포넌트 (장비 전용)

    받은 피해의 일부를 다음 턴으로 이연합니다.

    Config options:
        delay_percent (float): 이연 비율 (예: 0.3 = 30%)
        max_delayed_damage (int): 최대 이연 가능 피해량 (0 = 무제한)
        attribute_resistance (list): 추가 속성 저항 (예: ["시간"])
    """

    def __init__(self):
        super().__init__()
        self.delay_percent = 0.3
        self.max_delayed_damage = 0
        self.attribute_resistance = []
        self._delayed_damage = 0

    def apply_config(self, config, skill_name, priority=0):
        super().apply_config(config, skill_name, priority)
        self.delay_percent = config.get("delay_percent", 0.3)
        self.max_delayed_damage = config.get("max_delayed_damage", 0)
        self.attribute_resistance = config.get("attribute_resistance", [])

    def on_combat_start(self, attacker, target):
        """전투 시작 시 이연 피해 초기화"""
        self._delayed_damage = 0
        return ""

    def on_damaged(self, defender, attacker, actual_damage: int) -> str:
        """
        피격 시 피해 이연

        Note: 이 훅은 전투 시스템에서 피격 시 호출됩니다.
        반환값은 메시지이며, 실제 피해 감소는 get_damage_reduction_multiplier()로 처리
        """
        if actual_damage <= 0:
            return ""

        # 이연할 피해량 계산
        delayed = int(actual_damage * self.delay_percent)

        # 최대 이연량 제한
        if self.max_delayed_damage > 0:
            delayed = min(delayed, self.max_delayed_damage - self._delayed_damage)

        if delayed <= 0:
            return ""

        self._delayed_damage += delayed

        return f"⏳ 피해 {delayed} 이연! (다음 턴에 받음)"

    def on_turn_start(self, attacker, target):
        """
        턴 시작 시 이연된 피해 적용

        Note: 이 훅은 전투 시스템에서 매 턴마다 호출됩니다.
        """
        if self._delayed_damage <= 0:
            return ""

        # 이연 피해 적용
        actual_damage = attacker.take_damage(self._delayed_damage)
        delayed_msg = f"⏰ 이연 피해 {actual_damage} 적용!"

        self._delayed_damage = 0

        return delayed_msg

    def get_damage_reduction_amount(self, damage: int) -> int:
        """
        피해 감소량 반환

        Args:
            damage: 원본 피해량

        Returns:
            감소할 피해량
        """
        delayed = int(damage * self.delay_percent)

        # 최대 이연량 제한
        if self.max_delayed_damage > 0:
            delayed = min(delayed, self.max_delayed_damage - self._delayed_damage)

        return max(0, delayed)


@register_skill_with_tag("periodic_invincibility")
class PeriodicInvincibilityComponent(SkillComponent):
    """
    주기적 무적 컴포넌트 (장비 전용)

    N턴마다 1턴간 무적 상태가 됩니다.

    Config options:
        interval (int): 무적 발동 주기 (턴 수)
        duration (int): 무적 지속 턴 수 (기본: 1)
        damage_reduction (float): 무적 대신 피해 감소 사용 시 (예: 1.0 = 100% 면역)
    """

    def __init__(self):
        super().__init__()
        self.interval = 5
        self.duration = 1
        self.damage_reduction = 1.0
        self._turn_count = 0
        self._invincible_remaining = 0

    def apply_config(self, config, skill_name, priority=0):
        super().apply_config(config, skill_name, priority)
        self.interval = config.get("interval", 5)
        self.duration = config.get("duration", 1)
        self.damage_reduction = config.get("damage_reduction", 1.0)

    def on_combat_start(self, attacker, target):
        """전투 시작 시 턴 카운트 초기화"""
        self._turn_count = 0
        self._invincible_remaining = 0
        return ""

    def on_turn_start(self, attacker, target):
        """
        턴 시작 시 무적 체크

        Note: 이 훅은 전투 시스템에서 매 턴마다 호출됩니다.
        """
        self._turn_count += 1

        # 무적 지속 감소
        if self._invincible_remaining > 0:
            self._invincible_remaining -= 1
            if self._invincible_remaining == 0:
                return f"🛡️ **{attacker.get_name()}** 무적 종료"
            return ""

        # 주기 체크
        if self._turn_count % self.interval == 0:
            self._invincible_remaining = self.duration
            return f"✨ **{attacker.get_name()}** 무적 발동! ({self.duration}턴)"

        # 다음 무적까지 남은 턴
        remaining = self.interval - (self._turn_count % self.interval)
        if remaining <= 2:
            return f"⏳ 다음 무적까지 {remaining}턴"

        return ""

    def is_invincible(self) -> bool:
        """현재 무적 상태 여부 반환"""
        return self._invincible_remaining > 0

    def get_damage_reduction_multiplier(self) -> float:
        """
        피해 감소 배율 반환

        Returns:
            0.0 (완전 면역) ~ 1.0 (감소 없음)
        """
        if self._invincible_remaining > 0:
            return 1.0 - self.damage_reduction
        return 1.0


@register_skill_with_tag("ally_protection")
class AllyProtectionComponent(SkillComponent):
    """
    아군 보호 컴포넌트 (장비 전용)

    아군을 보호할 때 피해 감소 및 도발 효과를 받습니다.
    현재는 1:1 전투만 지원하므로 제한적으로 동작합니다.

    Config options:
        damage_reduction (float): 보호 시 피해 감소 (예: 0.2 = 20%)
        taunt_chance (float): 도발 확률 (예: 0.5 = 50%)
        taunt_duration (int): 도발 지속 턴 수 (기본: 2)
    """

    def __init__(self):
        super().__init__()
        self.damage_reduction = 0.2
        self.taunt_chance = 0.5
        self.taunt_duration = 2
        self._is_protecting = False
        self._taunt_remaining = 0

    def apply_config(self, config, skill_name, priority=0):
        super().apply_config(config, skill_name, priority)
        self.damage_reduction = config.get("damage_reduction", 0.2)
        self.taunt_chance = config.get("taunt_chance", 0.5)
        self.taunt_duration = config.get("taunt_duration", 2)

    def on_combat_start(self, attacker, target):
        """전투 시작 시 초기화"""
        self._is_protecting = False
        self._taunt_remaining = 0

        # 1:1 전투에서는 항상 보호 중으로 간주 (HP가 낮은 상대를 보호한다고 가정)
        if hasattr(target, 'now_hp') and hasattr(target, 'hp'):
            if target.now_hp < target.hp * 0.5:
                self._is_protecting = True
                return f"🛡️ **{attacker.get_name()}** 보호 태세!"

        return ""

    def on_turn_start(self, attacker, target):
        """
        턴 시작 시 도발 체크

        Note: 이 훅은 전투 시스템에서 매 턴마다 호출됩니다.
        """
        if self._taunt_remaining > 0:
            self._taunt_remaining -= 1
            if self._taunt_remaining == 0:
                return f"💢 **{attacker.get_name()}** 도발 종료"
            return ""

        # 보호 중이고 도발 확률 체크
        if self._is_protecting and random.random() < self.taunt_chance:
            self._taunt_remaining = self.taunt_duration
            return f"💢 **{attacker.get_name()}** 도발 발동! ({self.taunt_duration}턴)"

        return ""

    def get_damage_reduction_multiplier(self) -> float:
        """
        보호 중일 때 피해 감소 배율 반환

        Returns:
            1.0 - damage_reduction (보호 중) or 1.0 (일반)
        """
        if self._is_protecting:
            return 1.0 - self.damage_reduction
        return 1.0

    def is_taunting(self) -> bool:
        """현재 도발 상태 여부 반환"""
        return self._taunt_remaining > 0
