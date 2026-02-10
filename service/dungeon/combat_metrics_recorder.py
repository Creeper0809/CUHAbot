"""
전투 지표 기록기 (Combat Metrics Recorder)

전투 중 데미지, 치유량 등의 지표를 추적하고 기여도를 기록합니다.
"""
import logging
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from models import User
    from service.session import DungeonSession

logger = logging.getLogger(__name__)


class CombatMetricsRecorder:
    """전투 지표 추적 및 기여도 기록"""

    def __init__(self):
        """CombatMetricsRecorder 초기화"""
        pass

    def parse_combat_metrics_from_logs(self, logs: list[str]) -> tuple[int, int]:
        """
        전투 로그에서 데미지와 치유량을 추출

        로그 패턴:
        - 공격: "⚔️ **공격자** 「스킬명」 → **대상** 150💥..."
        - 치유: "💚 **치유자** 「스킬명」 → **+100** HP"
        - 흡혈: "   💚 흡혈: +50 HP"

        Args:
            logs: 행동 로그 리스트

        Returns:
            (총 데미지, 총 치유량)
        """
        total_damage = 0
        total_healing = 0

        for log in logs:
            try:
                # 공격 데미지 파싱: "→ **대상** 150💥" 또는 "→ **대상** 150"
                # 패턴: "→ **대상** 숫자"에서 숫자 추출
                damage_match = re.search(r'→\s+\*\*[^*]+\*\*\s+(\d+)', log)
                if damage_match and '⚔️' in log:
                    damage = int(damage_match.group(1))
                    total_damage += damage
                    continue

                # 치유량 파싱: "→ **+100** HP" 또는 "흡혈: +50 HP"
                # 패턴: "+숫자 HP" 또는 "**+숫자** HP" (별표는 옵션)
                # 💚 이모지가 있어야 치유로 인정 (HP 키워드만으로는 너무 광범위)
                healing_match = re.search(r'\*?\*?\+(\d+)\*?\*?\s*HP', log)
                if healing_match and '💚' in log:
                    healing = int(healing_match.group(1))
                    total_healing += healing
                    continue

                # 반사 데미지는 제외 (🔄가 있으면 스킵)
                if '🔄' in log:
                    continue

            except (ValueError, IndexError, AttributeError) as e:
                logger.warning(f"Failed to parse combat metric from log: {log[:50]}... Error: {e}")
                continue

        return total_damage, total_healing

    def record_actor_contribution(
        self,
        session: "DungeonSession",
        actor: "User",
        action_logs: list[str]
    ) -> None:
        """
        액터의 기여도를 기록 (데미지/치유량 추출 후 기여도 추적)

        Args:
            session: 던전 세션
            actor: 행동한 액터
            action_logs: 행동 로그 리스트
        """
        from service.intervention.contribution_tracker import record_contribution

        # 로그에서 데미지/치유량 추출
        damage, healing = self.parse_combat_metrics_from_logs(action_logs)

        # 기여도 기록
        record_contribution(session, actor, damage=damage, healing=healing)
