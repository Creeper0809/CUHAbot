"""
장비 통합 관리자 (Equipment Integration Manager)

장비 컴포넌트의 전투 훅(hook) 처리를 담당합니다.
"""
import logging
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from models import User
    from service.dungeon.combat_context import CombatContext

logger = logging.getLogger(__name__)


class EquipmentIntegrationManager:
    """장비 컴포넌트 훅 처리"""

    def __init__(self):
        """EquipmentIntegrationManager 초기화"""
        self._warned_users = set()  # 경고를 이미 출력한 유저 ID 저장

    def get_equipment_components(self, entity) -> list:
        """
        엔티티의 장비 컴포넌트 가져오기 (캐시 사용)

        Args:
            entity: User 또는 Monster

        Returns:
            컴포넌트 리스트
        """
        # 유저만 장비 착용
        from models.users import User as UserClass
        if not isinstance(entity, UserClass):
            return []

        # 캐시에서 가져오기
        if hasattr(entity, '_equipment_components_cache'):
            return entity._equipment_components_cache

        # 캐시가 없으면 경고 로그 출력 (한 번만)
        if entity.discord_id not in self._warned_users:
            logger.warning(
                f"Equipment components cache not found for user {entity.discord_id}. "
                f"Equipment effects will not be applied. "
                f"Call cache_equipment_components() at combat start."
            )
            self._warned_users.add(entity.discord_id)
        return []

    def apply_combat_start(
        self,
        user: "User",
        context: "CombatContext",
        session=None,
    ) -> list[str]:
        """
        전투 시작 시 장비 컴포넌트의 on_combat_start() 호출

        Args:
            user: 유저 엔티티
            context: 전투 컨텍스트

        Returns:
            로그 메시지 리스트
        """
        logs = []
        components = self.get_equipment_components(user)

        for comp in components:
            if hasattr(comp, 'on_combat_start'):
                # 대상은 첫 번째 몬스터 (없으면 None)
                target = context.get_primary_monster() if context.monsters else None
                log = comp.on_combat_start(user, target)
                if log and log.strip():
                    logs.append(log)

            if getattr(comp, '_tag', '') == 'dungeon_specific_buff':
                dungeon = getattr(session, 'dungeon', None)
                dungeon_id = getattr(dungeon, 'id', None)
                dungeon_type = str(
                    getattr(session, 'content_type', getattr(dungeon, 'type', '')) or ''
                ).lower()
                if '훈련' in str(getattr(dungeon, 'name', '')):
                    dungeon_type = 'training'
                if comp.is_active_in_dungeon(dungeon_id, dungeon_type):
                    applied = {}
                    for stat, value in comp.get_stat_bonuses().items():
                        attr = {'ad_defense': 'defense'}.get(stat, stat)
                        if not hasattr(user, attr):
                            continue
                        current = getattr(user, attr)
                        delta = int(value) if isinstance(current, int) and not isinstance(current, bool) else float(value)
                        setattr(user, attr, current + delta)
                        applied[attr] = applied.get(attr, 0.0) + delta
                    if applied:
                        user._equipment_temporary_stats = applied
                        logs.append("🏰 던전 전용 장비 효과가 활성화되었습니다.")

        return logs

    def apply_turn_start(
        self,
        entity,
        target=None
    ) -> list[str]:
        """
        턴 시작 시 장비 컴포넌트의 on_turn_start() 호출

        Args:
            entity: 행동하는 엔티티
            target: 대상 엔티티

        Returns:
            로그 메시지 리스트
        """
        logs = []
        components = self.get_equipment_components(entity)

        for comp in components:
            if hasattr(comp, 'on_turn_start'):
                log = comp.on_turn_start(entity, target)
                if log and log.strip():
                    logs.append(log)

            # These legacy effects expose on_turn even though their semantic
            # trigger is the beginning of an action.
            if getattr(comp, '_tag', '') == 'random_attribute' and hasattr(comp, 'on_turn'):
                log = comp.on_turn(entity, target)
                if log and log.strip():
                    logs.append(log)

        return logs

    def apply_on_attack(
        self,
        attacker,
        target,
        damage: int
    ) -> list[str]:
        """
        공격 후 장비 컴포넌트의 on_attack() 호출

        Args:
            attacker: 공격자
            target: 대상
            damage: 가한 피해량

        Returns:
            로그 메시지 리스트
        """
        logs = []
        components = self.get_equipment_components(attacker)

        for comp in components:
            if hasattr(comp, 'on_attack'):
                log = comp.on_attack(attacker, target, damage)
                if log and log.strip():
                    logs.append(log)
            if getattr(comp, '_tag', '') == 'on_attack_proc' and hasattr(comp, 'on_turn'):
                log = comp.on_turn(attacker, target)
                if log and log.strip():
                    logs.append(log)

        return logs

    def apply_on_damaged(
        self,
        defender,
        attacker,
        damage: int
    ) -> list[str]:
        """
        피격 시 장비 컴포넌트의 on_damaged() 호출

        Args:
            defender: 방어자
            attacker: 공격자
            damage: 받은 피해량

        Returns:
            로그 메시지 리스트
        """
        logs = []
        components = self.get_equipment_components(defender)

        for comp in components:
            if getattr(comp, '_tag', '') == 'damage_delay':
                # The pipeline already moved the delayed portion before HP was
                # changed; calling on_damaged again would schedule it twice.
                continue
            if hasattr(comp, 'on_damaged'):
                log = comp.on_damaged(defender, attacker, damage)
                if log and log.strip():
                    logs.append(log)

        return logs

    def apply_passives(self, actor) -> list[str]:
        """
        턴마다 장비 패시브 효과 처리 (재생, 성장 등)

        Args:
            actor: 행동하는 엔티티

        Returns:
            로그 메시지 리스트
        """
        logs = []
        components = self.get_equipment_components(actor)

        for comp in components:
            if getattr(comp, '_tag', '') == "combat_stat_growth" and hasattr(comp, 'on_turn'):
                log = comp.on_turn(actor, None)
                if log and log.strip():
                    logs.append(log)

        return logs

    def apply_skill_used(self, actor, skill) -> list[str]:
        """Track equipment combos and refresh effects after choosing a skill."""
        if skill is None:
            return []
        logs = []
        for comp in self.get_equipment_components(actor):
            if not hasattr(comp, 'on_skill_used'):
                continue
            argument = getattr(skill, 'id', 0) if getattr(comp, '_tag', '') == 'skill_refresh' else skill
            log = comp.on_skill_used(actor, argument)
            if log and str(log).strip():
                logs.append(str(log))
        return logs

    def apply_on_kill(self, killer, dying_entity) -> list[str]:
        """Run equipment kill triggers exactly once per defeated entity."""
        logs = []
        for comp in self.get_equipment_components(killer):
            if getattr(comp, '_tag', '') not in {'on_kill_heal', 'on_kill_stack'}:
                continue
            log = comp.on_death(dying_entity, killer)
            if log and str(log).strip():
                logs.append(str(log))
        return logs

    def apply_combat_end(self, user) -> list[str]:
        """Restore temporary equipment conversions before discarding state."""
        logs = []
        for comp in self.get_equipment_components(user):
            if hasattr(comp, 'on_combat_end'):
                log = comp.on_combat_end(user)
                if log and str(log).strip():
                    logs.append(str(log))
        for attr, delta in getattr(user, '_equipment_temporary_stats', {}).items():
            setattr(user, attr, getattr(user, attr) - delta)
        user._equipment_temporary_stats = {}
        return logs

    def has_first_strike(self, user) -> bool:
        return any(
            getattr(comp, '_tag', '') == 'first_strike'
            and getattr(comp, 'has_guaranteed_first_strike', lambda: False)()
            for comp in self.get_equipment_components(user)
        )

    def reset_component_caches(self, user: "User") -> None:
        """
        장비 컴포넌트 캐시 및 상태 리셋 (전투 종료 시)

        Args:
            user: 유저 엔티티
        """
        components = self.get_equipment_components(user)

        for comp in components:
            # 사용 횟수 리셋
            if hasattr(comp, 'used_count'):
                comp.used_count = 0

            # 적용 대상 리셋
            if hasattr(comp, '_applied_entities'):
                comp._applied_entities.clear()

            # 턴 카운트 리셋
            if hasattr(comp, '_turn_count'):
                comp._turn_count = 0
            if hasattr(comp, '_turn_counts'):
                comp._turn_counts.clear()

            # 이연 피해 리셋
            if hasattr(comp, '_delayed_damage'):
                comp._delayed_damage = 0

            # 무적 상태 리셋
            if hasattr(comp, '_invincible_remaining'):
                comp._invincible_remaining = 0

            # 부활 횟수 리셋
            if hasattr(comp, '_revives_used'):
                comp._revives_used = 0

            # 연쇄 공격 리셋
            if hasattr(comp, '_chain_count'):
                comp._chain_count = 0
            if hasattr(comp, '_current_stacks'):
                comp._current_stacks = 0
            if hasattr(comp, '_last_skill_id'):
                comp._last_skill_id = None
            if hasattr(comp, '_used_skills'):
                comp._used_skills.clear()
            if hasattr(comp, '_accumulated'):
                comp._accumulated = 0.0

            # 예측 상태 리셋
            if hasattr(comp, '_predicted_this_turn'):
                comp._predicted_this_turn = False

            # 보호 상태 리셋
            if hasattr(comp, '_is_protecting'):
                comp._is_protecting = False
            if hasattr(comp, '_taunt_remaining'):
                comp._taunt_remaining = 0

        # 캐시 자체도 제거
        if hasattr(user, '_equipment_components_cache'):
            delattr(user, '_equipment_components_cache')

        # 경고 기록 제거
        if user.discord_id in self._warned_users:
            self._warned_users.discard(user.discord_id)
