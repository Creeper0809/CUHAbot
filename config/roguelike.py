"""Balance and rollout configuration for the Discord roguelike dungeon."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class RouteKind(str, Enum):
    COMBAT = "combat"
    ELITE = "elite"
    TREASURE = "treasure"
    EVENT = "event"
    HAZARD = "hazard"
    REST = "rest"
    SECRET = "secret"
    NPC = "npc"


@dataclass(frozen=True)
class RoguelikeConfig:
    ROUTE_ROOMS: int = 8
    BOSS_STAGE: int = 9
    CHOICE_TIMEOUT_SECONDS: int = 60
    PAUSE_GRACE_SECONDS: int = 300
    FAILURE_REWARD_RATE: float = 0.70
    CLEAR_BONUS_RATE: float = 0.20

    EARLY_WEIGHTS: tuple[tuple[RouteKind, int], ...] = (
        (RouteKind.COMBAT, 40), (RouteKind.ELITE, 8),
        (RouteKind.TREASURE, 14), (RouteKind.EVENT, 14),
        (RouteKind.HAZARD, 8), (RouteKind.REST, 10),
        (RouteKind.SECRET, 4), (RouteKind.NPC, 2),
    )
    MID_WEIGHTS: tuple[tuple[RouteKind, int], ...] = (
        (RouteKind.COMBAT, 34), (RouteKind.ELITE, 16),
        (RouteKind.TREASURE, 13), (RouteKind.EVENT, 14),
        (RouteKind.HAZARD, 10), (RouteKind.REST, 8),
        (RouteKind.SECRET, 3), (RouteKind.NPC, 2),
    )
    LATE_WEIGHTS: tuple[tuple[RouteKind, int], ...] = (
        (RouteKind.COMBAT, 28), (RouteKind.ELITE, 27),
        (RouteKind.TREASURE, 12), (RouteKind.EVENT, 12),
        (RouteKind.HAZARD, 11), (RouteKind.REST, 5),
        (RouteKind.SECRET, 3), (RouteKind.NPC, 2),
    )

    ROOM_STAT_SCALES: tuple[float, ...] = (0.9, 0.9, 1.0, 1.0, 1.1, 1.1, 1.2, 1.2)
    AUGMENT_ROOMS: tuple[int, ...] = (2, 4, 6)
    HAZARD_TRIGGER_CHANCE: float = 0.35
    HAZARD_DAMAGE_MIN: float = 0.08
    HAZARD_DAMAGE_MAX: float = 0.15
    HAZARD_REWARD_MULTIPLIER: float = 1.25
    REST_HEAL_RATE: float = 0.20
    REST_SHIELD_RATE: float = 0.10


ROGUELIKE = RoguelikeConfig()


@dataclass(frozen=True)
class PityRule:
    key: str
    box_ids: tuple[int, ...]
    target_grade: int
    soft_start: int
    hard_pity: int


BOX_PITY_RULES: tuple[PityRule, ...] = (
    PityRule("low", (5940,), 4, 9, 15),
    PityRule("mid", (5941,), 5, 12, 20),
    PityRule("high", (5942, 5945), 6, 15, 25),
    PityRule("best", (5943, 5946), 7, 21, 35),
)

BOX_PITY_BY_ID = {
    box_id: rule
    for rule in BOX_PITY_RULES
    for box_id in rule.box_ids
}

FIXED_GRADE_BOX_IDS = frozenset({5920, 5921, 5922, 5923, 5924, 5930, 5931, 5932, 5933, 5934, 5947})
SOFT_PITY_INCREMENT = 0.03
SOFT_PITY_CAP = 0.50
