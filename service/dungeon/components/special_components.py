"""
특수 컴포넌트: StatusComponent, ComboComponent, SummonComponent
"""
import random

from config import DAMAGE
from models import UserStatEnum
from service.dungeon.components.base import SkillComponent, register_skill_with_tag
from service.dungeon.damage_pipeline import process_incoming_damage
from service.dungeon.status import (
    apply_status_effect, remove_status_effects,
    get_status_stacks, has_status_effect,
)


@register_skill_with_tag("status")
class StatusComponent(SkillComponent):
    """
    상태이상 적용 컴포넌트

    Config options:
        type (str): 상태이상 타입 (burn, poison, bleed, slow, freeze, stun 등)
        chance (float): 적용 확률 (0.0~1.0)
        duration (int): 지속 턴 수
        stacks (int): 적용 스택 수
    """

    def __init__(self):
        super().__init__()
        self.status_type = ""
        self.chance = 1.0
        self.status_duration = 0
        self.stacks = 1

    def apply_config(self, config, skill_name, priority=0):
        super().apply_config(config, skill_name, priority)
        self.status_type = config.get("type", "")
        self.chance = config.get("chance", 1.0)
        self.status_duration = config.get("duration", 0)
        self.stacks = config.get("stacks", 1)

    def on_turn(self, attacker, target):
        if not self.status_type:
            return ""
        chance = self.chance
        duration = self.status_duration

        if hasattr(attacker, "equipped_skill"):
            from service.skill.synergy_service import SynergyService
            chance += SynergyService.calculate_status_chance_bonus(
                attacker.equipped_skill, self.status_type, current_skill=self.skill
            )
            duration += SynergyService.calculate_status_duration_bonus(
                attacker.equipped_skill, self.status_type, current_skill=self.skill
            )

        chance = max(0.0, min(1.0, chance))
        duration = max(0, int(duration))

        if random.random() >= chance:
            return ""
        return apply_status_effect(target, self.status_type, self.stacks, duration)


@register_skill_with_tag("combo")
class ComboComponent(SkillComponent):
    """
    콤보 체인 컴포넌트

    대상의 상태이상을 체크하여 추가 데미지/효과 적용
    DamageComponent와 함께 사용하여 콤보 효과 구현

    Config options:
        combo_type (str): 콤보 타입 (ignite, shatter, overload 등) - 메시지용
        prerequisite (str): 선행 조건 상태이상 (burn, freeze, paralyze 등)
        min_stacks (int): 최소 스택 수 (기본 1)
        damage_multiplier (float): 추가 데미지 배율 (기본 1.0)
        consume_stacks (bool): 스택 소모 여부 (기본 False)
        force_critical (bool): 강제 치명타 여부 (기본 False)
        ad_ratio (float): 물리 공격력 계수
        ap_ratio (float): 마법 공격력 계수
        apply_status (str): 추가 적용할 상태이상 (선택)
        apply_duration (int): 추가 상태이상 지속 시간
    """

    def __init__(self):
        super().__init__()
        self.combo_type = ""
        self.prerequisite = ""
        self.min_stacks = 1
        self.damage_multiplier = 1.0
        self.consume_stacks = False
        self.force_critical = False
        self.ad_ratio = 0.0
        self.ap_ratio = 0.0
        self.apply_status = ""
        self.apply_duration = 0

    def apply_config(self, config, skill_name, priority=0):
        super().apply_config(config, skill_name, priority)
        self.combo_type = config.get("combo_type", "")
        self.prerequisite = config.get("prerequisite", "")
        self.min_stacks = config.get("min_stacks", 1)
        self.damage_multiplier = config.get("damage_multiplier", 1.0)
        self.consume_stacks = config.get("consume_stacks", False)
        self.force_critical = config.get("force_critical", False)
        self.ad_ratio = config.get("ad_ratio", 0.0)
        self.ap_ratio = config.get("ap_ratio", 0.0)
        self.apply_status = config.get("apply_status", "")
        self.apply_duration = config.get("apply_duration", 0)

    def on_turn(self, attacker, target):
        if not self.prerequisite:
            return ""
        if not has_status_effect(target, self.prerequisite):
            return ""

        stacks = get_status_stacks(target, self.prerequisite)
        if stacks < self.min_stacks:
            return ""

        # 콤보 발동!
        logs = []
        bonus_damage = self._calculate_combo_damage(attacker)

        actual_damage = 0
        if bonus_damage > 0:
            event = process_incoming_damage(
                target, bonus_damage, attacker=attacker,
                attribute=self.skill_attribute,
            )
            actual_damage = event.actual_damage
            logs.extend(event.extra_logs)

        # 스택 소모
        if self.consume_stacks:
            remove_status_effects(target, count=99, filter_type=self.prerequisite)

        # 추가 상태이상 적용
        if self.apply_status:
            status_log = apply_status_effect(target, self.apply_status, stacks=1, duration=self.apply_duration)
            if status_log:
                logs.append(status_log)

        # 콤보 메시지
        combo_name = self._get_combo_name()
        crit_mark = " 💥" if self.force_critical else ""

        if bonus_damage > 0:
            main_log = f"{combo_name} **{attacker.get_name()}** 「{self.skill_name}」 → **{target.get_name()}** +{actual_damage}{crit_mark}"
            logs.insert(0, main_log)
        else:
            logs.insert(0, f"{combo_name} **{attacker.get_name()}** 「{self.skill_name}」 → **{target.get_name()}** 발동!")

        return "\n".join(logs)

    def _calculate_combo_damage(self, attacker) -> int:
        attacker_stat = attacker.get_stat()
        ad = attacker_stat.get(UserStatEnum.ATTACK, 0)
        ap = attacker_stat.get(UserStatEnum.AP_ATTACK, 0)

        base_damage = int(ad * self.ad_ratio + ap * self.ap_ratio)
        bonus_damage = int(base_damage * self.damage_multiplier)

        if bonus_damage > 0 and self.force_critical:
            bonus_damage = int(bonus_damage * DAMAGE.CRITICAL_MULTIPLIER)

        return bonus_damage

    def _get_combo_name(self) -> str:
        """콤보 타입별 이름/이모지 반환"""
        combo_names = {
            "ignite": "🔥소각",
            "incinerate": "💥연소",
            "shatter": "❄️💥파쇄",
            "paralyze_combo": "⚡마비",
            "overload": "⚡💥과부하",
            "curse_combo": "👿저주",
            "vampiric": "🩸흡혈",
            "infect": "🦠감염",
            "submerge": "🌊침수",
            "stun_combo": "💫기절",
            "bleed_combo": "🩸출혈",
        }
        return combo_names.get(self.combo_type, "💥콤보")


@register_skill_with_tag("summon")
class SummonComponent(SkillComponent):
    """
    몬스터 소환 컴포넌트

    전투 중 추가 몬스터를 소환합니다.
    CombatContext의 monsters 리스트에 추가됩니다.

    Config options:
        monster_ids (list[int]): 소환 가능한 몬스터 ID 리스트
        count (int): 소환할 개수 (기본 1)
        use_limit (int): 전투당 사용 제한 (기본 None=무제한)
    """

    def __init__(self):
        super().__init__()
        self.monster_ids = []
        self.count = 1
        self.use_limit = None
        self.used_count = 0

    def apply_config(self, config, skill_name, priority=0):
        super().apply_config(config, skill_name, priority)
        self.monster_ids = config.get("monster_ids", [])
        self.count = config.get("count", 1)
        self.use_limit = config.get("use_limit", None)

    def on_turn(self, attacker, defender) -> str:
        from models.repos.static_cache import monster_cache_by_id
        from service.session import get_session, get_all_sessions

        # 사용 제한 체크
        if self.use_limit is not None and self.used_count >= self.use_limit:
            return f"💫 **{attacker.get_name()}** {self.skill_name} 사용 불가 (제한 초과)"

        if not self.monster_ids:
            return f"⚠️ **{attacker.get_name()}** {self.skill_name} 소환 실패 (설정 오류)"

        session = self._find_session(attacker, defender)
        if not session or not session.combat_context:
            return f"⚠️ **{attacker.get_name()}** {self.skill_name} 소환 실패 (전투 컨텍스트 없음)"

        summoned_names = []
        for _ in range(self.count):
            selected_id = random.choice(self.monster_ids)
            if selected_id in monster_cache_by_id:
                summoned = monster_cache_by_id[selected_id].copy()
                session.combat_context.monsters.append(summoned)
                summoned_names.append(summoned.get_name())

        self.used_count += 1

        if not summoned_names:
            return f"⚠️ **{attacker.get_name()}** {self.skill_name} 소환 실패"

        names_str = ", ".join(summoned_names)
        return f"✨ **{attacker.get_name()}** {self.skill_name}! → {names_str} 소환!"

    def _find_session(self, attacker, defender):
        from service.session import get_session, get_all_sessions

        # defender가 User 객체인 경우
        if hasattr(defender, 'discord_id'):
            session = get_session(defender.discord_id)
            if session:
                return session

        # 그 외의 경우 모든 세션 검색 (안전장치)
        all_sessions = get_all_sessions()
        for s in all_sessions.values():
            if s.combat_context and attacker in s.combat_context.monsters:
                return s
        return None


@register_skill_with_tag("passive_revive")
class OnDeathReviveComponent(SkillComponent):
    """
    사망 시 부활 패시브 - 사망 시 HP를 회복하여 부활

    _check_death_triggers()에서 on_death 호출 시 발동합니다.
    _applied_entities로 전투당 1회 제한.

    Config options:
        hp_percent (float): 부활 시 최대 HP 대비 회복 비율 (예: 0.5 = 50%)
        max_uses (int): 전투당 최대 부활 횟수 (기본 1)
    """

    def __init__(self):
        super().__init__()
        self.hp_percent: float = 0.3
        self.max_uses: int = 1
        self._applied_entities: set[int] = set()

    def apply_config(self, config, skill_name, priority=0):
        super().apply_config(config, skill_name, priority)
        self.hp_percent = config.get("hp_percent", 0.3)
        self.max_uses = config.get("max_uses", 1)

    def on_death(self, dying_entity, killer, context):
        entity_id = id(dying_entity)
        if entity_id in self._applied_entities:
            return ""

        self._applied_entities.add(entity_id)

        from models import UserStatEnum
        max_hp = dying_entity.get_stat().get(UserStatEnum.HP, getattr(dying_entity, 'hp', 0))
        revive_hp = max(1, int(max_hp * self.hp_percent))
        dying_entity.now_hp = revive_hp

        return (
            f"💀✨ **{dying_entity.get_name()}** 「{self.skill_name}」 발동! "
            f"HP {revive_hp}({int(self.hp_percent * 100)}%)로 부활!"
        )

    def on_turn_start(self, attacker, target):
        entity_id = id(attacker)
        if entity_id in self._applied_entities:
            return ""
        return (
            f"🌟 **{attacker.get_name()}** 패시브 「{self.skill_name}」 → "
            f"사망 시 HP {int(self.hp_percent * 100)}%로 부활"
        )


@register_skill_with_tag("on_death_summon")
class OnDeathSummonComponent(SkillComponent):
    """
    사망 시 소환 컴포넌트

    보유 몬스터가 사망할 때 다른 몬스터를 소환합니다.
    on_turn에서는 아무것도 하지 않으며, on_death에서만 동작합니다.

    Config options:
        monster_ids (list[int]): 소환할 몬스터 ID 리스트
        count (int): 소환할 개수 (기본 1)
        chance (float): 발동 확률 (0.0~1.0, 기본 1.0=확정)
    """

    def __init__(self):
        super().__init__()
        self.monster_ids = []
        self.count = 1
        self.chance = 1.0

    def apply_config(self, config, skill_name, priority=0):
        super().apply_config(config, skill_name, priority)
        self.monster_ids = config.get("monster_ids", [])
        self.count = config.get("count", 1)
        self.chance = config.get("chance", 1.0)

    def on_death(self, dying_entity, killer, context):
        from models.repos.static_cache import monster_cache_by_id

        if not self.monster_ids:
            return ""

        if random.random() >= self.chance:
            return ""

        summoned_names = []
        for _ in range(self.count):
            selected_id = random.choice(self.monster_ids)
            cached = monster_cache_by_id.get(selected_id)
            if not cached:
                continue
            summoned = cached.copy()
            context.monsters.append(summoned)
            context.action_gauges[id(summoned)] = 0
            summoned_names.append(summoned.get_name())

        if not summoned_names:
            return ""

        names_str = ", ".join(summoned_names)
        return f"💀 **{dying_entity.get_name()}** 분열! → {names_str} 출현!"


@register_skill_with_tag("dot")
class DotComponent(SkillComponent):
    """
    지속 피해 컴포넌트 (Damage over Time)

    매 턴마다 대상에게 지속 데미지를 입힙니다.
    burn/poison과 달리 순수하게 데미지만 주는 효과입니다.

    Config options:
        ad_ratio (float): 물리 공격력 계수
        ap_ratio (float): 마법 공격력 계수
        duration (int): 지속 턴 수
        target (str): 대상 ("single" 또는 "all")
        is_physical (bool): 물리/마법 데미지 여부 (기본 False=마법)
        hp_threshold (float): HP 조건 (선택, 예: 0.2 = HP 20% 이하일 때만 발동)
    """

    def __init__(self):
        super().__init__()
        self.ad_ratio = 0.0
        self.ap_ratio = 0.0
        self.duration = 0
        self.target = "single"
        self.is_physical = False
        self.hp_threshold = None
        self._dot_active = False

    def apply_config(self, config, skill_name, priority=0):
        super().apply_config(config, skill_name, priority)
        self.ad_ratio = config.get("ad_ratio", 0.0)
        self.ap_ratio = config.get("ap_ratio", 0.0)
        self.duration = config.get("duration", 0)
        self.target = config.get("target", "single")
        self.is_physical = config.get("is_physical", False)
        self.hp_threshold = config.get("hp_threshold", None)

    def on_turn(self, attacker, target):
        """초기 발동 - DOT 효과 시작"""
        if self._dot_active:
            return ""

        # HP 조건 체크
        if self.hp_threshold is not None:
            max_hp = attacker.get_stat().get("HP", attacker.hp)
            if attacker.now_hp / max_hp > self.hp_threshold:
                return ""

        self._dot_active = True
        return (
            f"🔥 **{attacker.get_name()}** 「{self.skill_name}」 발동! "
            f"{self.duration}턴간 지속 데미지!"
        )

    def on_turn_start(self, attacker, target):
        """매 턴 시작 시 DOT 데미지 적용"""
        if not self._dot_active:
            return ""

        from service.session import get_session, get_all_sessions
        from models import UserStatEnum

        session = self._find_session(attacker, target)
        if not session or not session.combat_context:
            return ""

        attacker_stat = attacker.get_stat()
        ad = attacker_stat.get(UserStatEnum.ATTACK, 0)
        ap = attacker_stat.get(UserStatEnum.AP_ATTACK, 0)

        base_damage = int(ad * self.ad_ratio + ap * self.ap_ratio)
        if base_damage == 0:
            return ""

        logs = []
        if self.target == "all":
            # 전체 공격
            targets = [session.combat_context.user] if hasattr(session.combat_context, 'user') else []
            for monster in session.combat_context.monsters:
                if monster != attacker and monster.now_hp > 0:
                    targets.append(monster)

            for t in targets:
                event = process_incoming_damage(
                    t, base_damage, attacker=attacker,
                    attribute=self.skill_attribute,
                )
                logs.append(
                    f"   🔥 **{t.get_name()}** {event.actual_damage} 지속 피해"
                )
        else:
            # 단일 대상
            event = process_incoming_damage(
                target, base_damage, attacker=attacker,
                attribute=self.skill_attribute,
            )
            logs.append(
                f"🔥 **{attacker.get_name()}** 「{self.skill_name}」 → "
                f"**{target.get_name()}** {event.actual_damage} 지속 피해"
            )

        return "\n".join(logs)

    def _find_session(self, attacker, target):
        from service.session import get_session, get_all_sessions

        if hasattr(target, 'discord_id'):
            return get_session(target.discord_id)

        all_sessions = get_all_sessions()
        for s in all_sessions.values():
            if s.combat_context and attacker in s.combat_context.monsters:
                return s
        return None


@register_skill_with_tag("revive")
class ReviveComponent(SkillComponent):
    """
    부활 컴포넌트

    죽은 아군을 부활시킵니다. 몬스터 전용입니다.

    Config options:
        target (str): 대상 ("ally" = 1체, "all_ally" = 전체)
        count (int): 부활 대상 수 (target="ally"일 때, 기본 1)
        hp_percent (float): 부활 시 HP 비율 (예: 0.5 = 50%)
    """

    def __init__(self):
        super().__init__()
        self.target_type = "ally"
        self.count = 1
        self.hp_percent = 0.5

    def apply_config(self, config, skill_name, priority=0):
        super().apply_config(config, skill_name, priority)
        self.target_type = config.get("target", "ally")
        self.count = config.get("count", 1)
        self.hp_percent = config.get("hp_percent", 0.5)

    def on_turn(self, attacker, target):
        """부활 스킬 발동"""
        from service.session import get_session, get_all_sessions
        from models import UserStatEnum

        session = self._find_session(attacker, target)
        if not session or not session.combat_context:
            return "⚠️ 부활 실패 (전투 컨텍스트 없음)"

        # 죽은 아군 찾기 (같은 팀의 죽은 몬스터)
        dead_allies = [
            m for m in session.combat_context.monsters
            if m.now_hp <= 0 and m != attacker
        ]

        if not dead_allies:
            return f"✨ **{attacker.get_name()}** 「{self.skill_name}」 → 부활 대상 없음"

        revived_names = []
        if self.target_type == "all_ally":
            # 전체 부활
            targets = dead_allies
        else:
            # 1~count개 부활
            targets = dead_allies[:self.count]

        for ally in targets:
            max_hp = ally.get_stat().get(UserStatEnum.HP, ally.hp)
            revive_hp = max(1, int(max_hp * self.hp_percent))
            ally.now_hp = revive_hp
            revived_names.append(f"{ally.get_name()}(HP {int(self.hp_percent * 100)}%)")

        if not revived_names:
            return f"✨ **{attacker.get_name()}** 「{self.skill_name}」 → 부활 실패"

        names_str = ", ".join(revived_names)
        return f"✨💫 **{attacker.get_name()}** 「{self.skill_name}」 → {names_str} 부활!"

    def _find_session(self, attacker, target):
        from service.session import get_session, get_all_sessions

        if hasattr(target, 'discord_id'):
            return get_session(target.discord_id)

        all_sessions = get_all_sessions()
        for s in all_sessions.values():
            if s.combat_context and attacker in s.combat_context.monsters:
                return s
        return None


@register_skill_with_tag("self_destruct")
class SelfDestructComponent(SkillComponent):
    """
    자폭 컴포넌트

    일정 턴 충전 후 자폭하여 전체에게 큰 피해를 입힙니다.
    충전 중 기절 등으로 중단될 수 있습니다.

    Config options:
        charge_turns (int): 충전 턴 수 (예: 3 = 3턴 후 자폭)
        ap_ratio (float): 마법 공격력 계수
        ad_ratio (float): 물리 공격력 계수
        target (str): 대상 (기본 "all")
        interruptible (bool): 중단 가능 여부 (기본 True)
    """

    def __init__(self):
        super().__init__()
        self.charge_turns = 3
        self.ap_ratio = 0.0
        self.ad_ratio = 0.0
        self.target = "all"
        self.interruptible = True
        self._charge_count = 0
        self._is_charging = False

    def apply_config(self, config, skill_name, priority=0):
        super().apply_config(config, skill_name, priority)
        self.charge_turns = config.get("charge_turns", 3)
        self.ap_ratio = config.get("ap_ratio", 0.0)
        self.ad_ratio = config.get("ad_ratio", 0.0)
        self.target = config.get("target", "all")
        self.interruptible = config.get("interruptible", True)

    def on_turn(self, attacker, target):
        """초기 발동 - 충전 시작"""
        if not self._is_charging:
            self._is_charging = True
            self._charge_count = 0
            return f"⚠️ **{attacker.get_name()}** 「{self.skill_name}」 충전 시작! ({self.charge_turns}턴 후 자폭)"

        return ""

    def on_turn_start(self, attacker, target):
        """매 턴 충전 진행 및 자폭 체크"""
        if not self._is_charging:
            return ""

        from service.session import get_session, get_all_sessions
        from models import UserStatEnum

        # 중단 체크 (기절, 동결 등)
        if self.interruptible:
            from service.dungeon.status import has_status_effect
            if has_status_effect(attacker, "stun") or has_status_effect(attacker, "freeze"):
                self._is_charging = False
                self._charge_count = 0
                return f"⚡ **{attacker.get_name()}** 「{self.skill_name}」 충전 중단!"

        self._charge_count += 1

        # 충전 중
        if self._charge_count < self.charge_turns:
            return f"⚠️ **{attacker.get_name()}** 「{self.skill_name}」 충전 중... ({self._charge_count}/{self.charge_turns})"

        # 자폭!
        self._is_charging = False
        self._charge_count = 0

        session = self._find_session(attacker, target)
        if not session or not session.combat_context:
            return "💥 자폭 실패 (전투 컨텍스트 없음)"

        attacker_stat = attacker.get_stat()
        ad = attacker_stat.get(UserStatEnum.ATTACK, 0)
        ap = attacker_stat.get(UserStatEnum.AP_ATTACK, 0)

        base_damage = int(ad * self.ad_ratio + ap * self.ap_ratio)
        if base_damage == 0:
            return "💥 자폭 실패 (데미지 없음)"

        logs = [f"💥💥💥 **{attacker.get_name()}** 「{self.skill_name}」 자폭!"]

        # 전체 공격
        targets = []
        if hasattr(session.combat_context, 'user') and session.combat_context.user:
            targets.append(session.combat_context.user)
        for monster in session.combat_context.monsters:
            if monster != attacker and monster.now_hp > 0:
                targets.append(monster)

        for t in targets:
            event = process_incoming_damage(
                t, base_damage, attacker=attacker,
                attribute=self.skill_attribute,
            )
            logs.append(f"   💥 **{t.get_name()}** {event.actual_damage}")

        # 자폭한 몬스터는 사망
        attacker.now_hp = 0
        logs.append(f"   💀 **{attacker.get_name()}** 사망!")

        return "\n".join(logs)

    def _find_session(self, attacker, target):
        from service.session import get_session, get_all_sessions

        if hasattr(target, 'discord_id'):
            return get_session(target.discord_id)

        all_sessions = get_all_sessions()
        for s in all_sessions.values():
            if s.combat_context and attacker in s.combat_context.monsters:
                return s
        return None
