"""
인카운터 서비스

던전 인카운터 생성 및 관리를 담당합니다.
"""
import random
from typing import TYPE_CHECKING

from service.dungeon.encounter_types import (
    Encounter,
    EncounterType,
    TreasureEncounter,
    TrapEncounter,
    RandomEventEncounter,
    NPCEncounter,
    HiddenRoomEncounter,
)

if TYPE_CHECKING:
    from models import Monster


from config import ENCOUNTER


def _get_default_encounter_weights() -> dict:
    """config에서 기본 인카운터 가중치 생성"""
    return {
        EncounterType.MONSTER: ENCOUNTER.MONSTER_WEIGHT,
        EncounterType.TREASURE: ENCOUNTER.TREASURE_WEIGHT,
        EncounterType.TRAP: ENCOUNTER.TRAP_WEIGHT,
        EncounterType.EVENT: ENCOUNTER.EVENT_WEIGHT,
        EncounterType.NPC: ENCOUNTER.NPC_WEIGHT,
        EncounterType.HIDDEN_ROOM: ENCOUNTER.HIDDEN_ROOM_WEIGHT,
    }


# =============================================================================
# 인카운터 팩토리
# =============================================================================


class EncounterFactory:
    """
    인카운터 생성 팩토리

    던전 설정에 따라 적절한 인카운터를 생성합니다.
    """

    @staticmethod
    def roll_encounter_type(
        weights: dict = None,
        exclude_monster: bool = False
    ) -> EncounterType:
        """
        인카운터 타입 결정

        Args:
            weights: 인카운터 확률 가중치 (기본값 사용 시 None)
            exclude_monster: True면 몬스터 인카운터 제외

        Returns:
            결정된 인카운터 타입
        """
        if weights is None:
            weights = _get_default_encounter_weights().copy()

        if exclude_monster:
            weights = {k: v for k, v in weights.items() if k != EncounterType.MONSTER}

        encounter_types = list(weights.keys())
        encounter_weights = list(weights.values())

        return random.choices(encounter_types, weights=encounter_weights, k=1)[0]

    @staticmethod
    def create_encounter(encounter_type: EncounterType) -> Encounter:
        """
        인카운터 객체 생성

        Args:
            encounter_type: 인카운터 타입

        Returns:
            생성된 인카운터 객체

        Raises:
            ValueError: 알 수 없는 인카운터 타입
        """
        if encounter_type == EncounterType.TREASURE:
            # 보물상자 등급 랜덤
            grade = random.choices(
                ["normal", "silver", "gold"],
                weights=[
                    ENCOUNTER.CHEST_NORMAL_WEIGHT,
                    ENCOUNTER.CHEST_SILVER_WEIGHT,
                    ENCOUNTER.CHEST_GOLD_WEIGHT,
                ],
                k=1
            )[0]
            return TreasureEncounter(chest_grade=grade)

        elif encounter_type == EncounterType.TRAP:
            # 함정 피해 랜덤
            damage_percent = random.uniform(
                ENCOUNTER.TRAP_DAMAGE_MIN, ENCOUNTER.TRAP_DAMAGE_MAX
            )
            return TrapEncounter(damage_percent=damage_percent)

        elif encounter_type == EncounterType.EVENT:
            return RandomEventEncounter()

        elif encounter_type == EncounterType.NPC:
            return NPCEncounter()

        elif encounter_type == EncounterType.HIDDEN_ROOM:
            return HiddenRoomEncounter()

        elif encounter_type == EncounterType.MONSTER:
            # 몬스터 인카운터는 별도 처리 필요
            raise ValueError(
                "Monster encounters should be created via _spawn_random_monster"
            )

        else:
            raise ValueError(f"Unknown encounter type: {encounter_type}")

    @staticmethod
    def get_dungeon_encounter_weights(dungeon_id: int) -> dict:
        """
        던전별 인카운터 확률 가져오기

        Args:
            dungeon_id: 던전 ID

        Returns:
            인카운터 확률 가중치

        TODO: 던전별 커스텀 확률 지원
        """
        # 현재는 모든 던전에 기본 확률 사용
        # 나중에 던전 테이블에 encounter_weights 필드 추가 가능
        return _get_default_encounter_weights().copy()
