"""
특수 컴포넌트: StatusComponent, ComboComponent, SummonComponent
"""
import random

from config import DAMAGE
from models import UserStatEnum
from service.dungeon.components.base import SkillComponent, register_skill_with_tag
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
        if random.random() >= self.chance:
            return ""
        return apply_status_effect(target, self.status_type, self.stacks, self.status_duration)


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

        if bonus_damage > 0:
            target.take_damage(bonus_damage)

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
            main_log = f"{combo_name} **{attacker.get_name()}** 「{self.skill_name}」 → **+{bonus_damage}**{crit_mark}"
            logs.insert(0, main_log)
        else:
            logs.insert(0, f"{combo_name} **{attacker.get_name()}** 「{self.skill_name}」 발동!")

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
