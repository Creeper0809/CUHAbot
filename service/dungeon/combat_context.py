"""
전투 컨텍스트 모듈

1:1과 1:N 전투를 통합 처리하는 CombatContext 클래스를 제공합니다.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Dict, Optional, Union
import random

if TYPE_CHECKING:
    from models.monster import Monster
    from models.users import User


class TargetingMode(Enum):
    """타겟팅 모드"""
    LOWEST_HP = "lowest_hp"      # 가장 HP가 낮은 몬스터
    HIGHEST_HP = "highest_hp"    # 가장 HP가 높은 몬스터
    RANDOM = "random"            # 랜덤
    FIRST = "first"              # 첫 번째


@dataclass
class CombatContext:
    """
    전투 컨텍스트 - 1:1과 1:N 전투 통합

    단일 몬스터 또는 몬스터 그룹을 통합 처리하는 래퍼 클래스입니다.
    기존 1:1 전투 코드와의 호환성을 유지하면서 다중 몬스터 전투를 지원합니다.

    행동 게이지 시스템:
    - 각 전투원의 속도에 비례해 게이지 충전
    - 게이지 100 도달 시 행동 가능
    - 행동 후 게이지 소모
    """

    monsters: list["Monster"]
    """전투 중인 몬스터 리스트 (1~3마리)"""

    targeting_mode: TargetingMode = TargetingMode.LOWEST_HP
    """단일 타겟 스킬의 타겟 선택 방식"""

    action_gauges: Dict[int, int] = field(default_factory=dict)
    """각 전투원의 행동 게이지 (entity_id: gauge_value)"""

    action_count: int = 0
    """총 행동 횟수 (무한루프 방지용)"""

    round_number: int = 1
    """현재 라운드 번호"""

    round_marker_gauge: int = 0
    """라운드 마커 게이지 (속도 20 기준 더미)"""

    def get_primary_monster(self) -> "Monster":
        """
        단일 타겟 스킬용 주 타겟 반환

        Returns:
            타겟팅 모드에 따라 선택된 몬스터
        """
        alive = self.get_all_alive_monsters()
        if not alive:
            # 모두 사망했으면 첫 번째 몬스터 반환 (전투 종료 직전)
            return self.monsters[0]

        if self.targeting_mode == TargetingMode.LOWEST_HP:
            return min(alive, key=lambda m: m.now_hp)
        elif self.targeting_mode == TargetingMode.HIGHEST_HP:
            return max(alive, key=lambda m: m.now_hp)
        elif self.targeting_mode == TargetingMode.RANDOM:
            return random.choice(alive)
        else:  # FIRST
            return alive[0]

    def get_all_alive_monsters(self) -> list["Monster"]:
        """
        살아있는 몬스터 리스트 반환

        Returns:
            now_hp > 0인 몬스터들의 리스트
        """
        return [m for m in self.monsters if m.now_hp > 0]

    def is_all_dead(self) -> bool:
        """
        모든 몬스터 사망 여부 확인

        Returns:
            모든 몬스터가 사망했으면 True
        """
        return all(m.now_hp <= 0 for m in self.monsters)

    def get_total_hp(self) -> int:
        """
        전체 몬스터 HP 합계

        Returns:
            현재 살아있는 몬스터들의 HP 합
        """
        return sum(m.now_hp for m in self.get_all_alive_monsters())

    @classmethod
    def from_single(cls, monster: "Monster") -> "CombatContext":
        """
        1:1 전투용 컨텍스트 생성 (기존 코드 호환)

        Args:
            monster: 단일 몬스터

        Returns:
            단일 몬스터를 포함하는 컨텍스트
        """
        return cls(monsters=[monster])

    @classmethod
    def from_group(cls, monsters: list["Monster"]) -> "CombatContext":
        """
        1:N 전투용 컨텍스트 생성

        Args:
            monsters: 몬스터 리스트 (1~3마리)

        Returns:
            몬스터 그룹을 포함하는 컨텍스트
        """
        return cls(monsters=monsters)

    # =========================================================================
    # 행동 게이지 시스템
    # =========================================================================

    def initialize_gauges(self, user: "User") -> None:
        """
        모든 전투원의 행동 게이지 초기화

        Args:
            user: 유저 엔티티
        """
        # 유저 게이지 초기화
        self.action_gauges[id(user)] = 0

        # 몬스터들 게이지 초기화
        for monster in self.monsters:
            self.action_gauges[id(monster)] = 0

    def fill_gauges(self, user: "User") -> None:
        """
        모든 전투원의 행동 게이지 충전

        각 전투원의 속도에 비례해서 게이지가 충전됩니다.
        충전량 = 속도 × SPEED_MULTIPLIER

        Args:
            user: 유저 엔티티
        """
        from config import COMBAT

        # 유저 게이지 충전
        user_speed = self._get_entity_speed(user)
        self.action_gauges[id(user)] += int(user_speed * COMBAT.ACTION_GAUGE_SPEED_MULTIPLIER)

        # 몬스터들 게이지 충전
        for monster in self.get_all_alive_monsters():
            monster_speed = self._get_entity_speed(monster)
            self.action_gauges[id(monster)] += int(monster_speed * COMBAT.ACTION_GAUGE_SPEED_MULTIPLIER)

        # 라운드 마커 충전 (속도 20 고정)
        self.round_marker_gauge += int(20 * COMBAT.ACTION_GAUGE_SPEED_MULTIPLIER)

    def check_and_advance_round(self) -> bool:
        """
        라운드 마커 체크 및 라운드 진행

        라운드 마커 게이지가 100 이상이면 라운드 증가

        Returns:
            라운드가 증가했으면 True
        """
        from config import COMBAT

        if self.round_marker_gauge >= COMBAT.ACTION_GAUGE_MAX:
            self.round_number += 1
            self.round_marker_gauge -= COMBAT.ACTION_GAUGE_COST
            self.round_marker_gauge = max(0, self.round_marker_gauge)
            return True
        return False

    def get_next_actor(self, user: "User") -> Optional[Union["User", "Monster"]]:
        """
        다음 행동할 전투원 반환 (게이지 100 이상)

        게이지가 100 이상인 전투원 중 가장 높은 게이지를 가진 엔티티를 반환합니다.
        동점일 경우 랜덤으로 선택합니다.

        Args:
            user: 유저 엔티티

        Returns:
            다음 행동할 엔티티 (없으면 None)
        """
        from config import COMBAT

        # 행동 가능한 전투원 수집 (게이지 >= 100, 살아있음, 행동 가능)
        ready_entities = []

        # 유저 체크
        user_gauge = self.action_gauges.get(id(user), 0)
        if user_gauge >= COMBAT.ACTION_GAUGE_MAX and user.now_hp > 0:
            ready_entities.append((user, user_gauge))

        # 몬스터들 체크
        for monster in self.get_all_alive_monsters():
            monster_gauge = self.action_gauges.get(id(monster), 0)
            if monster_gauge >= COMBAT.ACTION_GAUGE_MAX:
                ready_entities.append((monster, monster_gauge))

        if not ready_entities:
            return None

        # 가장 높은 게이지를 가진 엔티티 찾기
        max_gauge = max(gauge for _, gauge in ready_entities)
        max_gauge_entities = [entity for entity, gauge in ready_entities if gauge == max_gauge]

        # 동점이면 랜덤 선택
        return random.choice(max_gauge_entities)

    def consume_gauge(self, entity: Union["User", "Monster"]) -> None:
        """
        행동 후 게이지 소모

        Args:
            entity: 행동한 엔티티
        """
        from config import COMBAT

        entity_id = id(entity)
        if entity_id in self.action_gauges:
            self.action_gauges[entity_id] -= COMBAT.ACTION_GAUGE_COST
            # 게이지가 음수가 되지 않도록 보정
            self.action_gauges[entity_id] = max(0, self.action_gauges[entity_id])

    def _get_entity_speed(self, entity: Union["User", "Monster"]) -> int:
        """
        엔티티의 속도 스탯 반환

        Args:
            entity: 유저 또는 몬스터

        Returns:
            속도 값
        """
        from models.users import User

        if isinstance(entity, User):
            from models.user_stats import UserStatEnum
            return entity.get_stat()[UserStatEnum.SPEED]
        else:
            return entity.speed
