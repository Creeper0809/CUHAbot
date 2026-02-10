"""
패시브 효과 프로세서 (Passive Effect Processor)

패시브 스킬 효과 발동 및 관리를 담당합니다.
"""
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from models import User
    from service.dungeon.combat_context import CombatContext

logger = logging.getLogger(__name__)


class PassiveEffectProcessor:
    """패시브 스킬 효과 처리"""

    def __init__(self):
        """PassiveEffectProcessor 초기화"""
        pass

    def apply_combat_start_passives(
        self,
        user: "User",
        context: "CombatContext"
    ) -> list[str]:
        """
        전투 시작 시 모든 엔티티의 패시브 발동 로그 출력

        Args:
            user: 리더 유저
            context: 전투 컨텍스트

        Returns:
            패시브 발동 로그 리스트
        """
        from models.repos.skill_repo import get_skill_by_id

        logs = []
        entities = [user] + list(context.monsters)

        # NOTE: _applied_entities는 전투 종료 시 reset_all_skill_usage_counts()에서 일괄 초기화됨
        # 동시 전투 시 싱글톤 컴포넌트 공유 문제를 방지하기 위해,
        # 각 컴포넌트는 id(entity)로 엔티티를 구분하여 중복 적용을 방지함

        for entity in entities:
            skill_ids = getattr(entity, 'equipped_skill', None) or getattr(entity, 'use_skill', [])
            for sid in skill_ids:
                if sid == 0:
                    continue
                skill = get_skill_by_id(sid)
                if not skill or not skill.is_passive:
                    continue
                log = skill.on_turn_start(entity, context)
                if log and log.strip():
                    logs.append(log)

        return logs

    def process_passive_effects(self, actor) -> list[str]:
        """
        매 턴 재생/조건부/턴성장 패시브 처리

        Args:
            actor: 행동하는 엔티티

        Returns:
            패시브 효과 로그 리스트
        """
        from models.repos.skill_repo import get_skill_by_id

        logs = []
        skill_ids = getattr(actor, 'equipped_skill', None) or getattr(actor, 'use_skill', [])

        for sid in skill_ids:
            if sid == 0:
                continue
            skill = get_skill_by_id(sid)
            if not skill or not skill.is_passive:
                continue

            for comp in skill.components:
                tag = getattr(comp, '_tag', '')
                log = ""
                if tag == "passive_regen":
                    log = comp.process_regen(actor)
                elif tag == "conditional_passive":
                    log = comp.process_conditional(actor)
                elif tag == "passive_turn_scaling":
                    log = comp.process_turn_scaling(actor)
                if log and log.strip():
                    logs.append(log)

        return logs

    def reset_all_skill_usage_counts(self) -> None:
        """모든 스킬의 사용 횟수 카운터 및 패시브 적용 상태 리셋 (전투 종료 시)"""
        from models.repos.static_cache import skill_cache_by_id

        for skill in skill_cache_by_id.values():
            for component in skill.components:
                if hasattr(component, 'used_count'):
                    component.used_count = 0
                if hasattr(component, '_applied_entities'):
                    component._applied_entities.clear()
                if hasattr(component, '_turn_counts'):
                    component._turn_counts.clear()
                if hasattr(component, '_base_stats'):
                    component._base_stats.clear()
