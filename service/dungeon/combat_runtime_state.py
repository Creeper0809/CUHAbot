"""Shared per-combat state for V3 skills and encounter decision machines."""
from __future__ import annotations

from dataclasses import dataclass, field
import random
from typing import Any


@dataclass
class EntityRuntimeState:
    resources: dict[str, int] = field(default_factory=dict)
    counters: dict[str, int] = field(default_factory=dict)
    marks: dict[str, dict[str, Any]] = field(default_factory=dict)
    delayed_effects: list[dict[str, Any]] = field(default_factory=list)
    skill_uses: dict[int, int] = field(default_factory=dict)
    ai: dict[str, Any] = field(default_factory=dict)

    def add_resource(self, name: str, amount: int, maximum: int | None = None) -> int:
        value = self.resources.get(name, 0) + int(amount)
        if maximum is not None:
            value = min(value, int(maximum))
        self.resources[name] = max(0, value)
        return self.resources[name]

    def spend_resource(self, name: str, amount: int) -> bool:
        amount = max(0, int(amount))
        current = self.resources.get(name, 0)
        if current < amount:
            return False
        self.resources[name] = current - amount
        return True


@dataclass
class CombatRuntimeState:
    seed: int = 0
    round_number: int = 1
    entities: dict[int, EntityRuntimeState] = field(default_factory=dict)
    event_log: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.rng = random.Random(self.seed)

    def for_entity(self, entity: Any) -> EntityRuntimeState:
        return self.entities.setdefault(id(entity), EntityRuntimeState())

    def bind(self, entity: Any) -> EntityRuntimeState:
        state = self.for_entity(entity)
        entity.combat_runtime_state = self
        return state

    def record(self, event_type: str, **payload: Any) -> None:
        self.event_log.append({"type": event_type, "round": self.round_number, **payload})

    def advance_round(self, round_number: int) -> None:
        self.round_number = int(round_number)
        for state in self.entities.values():
            for effect in state.delayed_effects:
                if effect.get("clock") == "owner_action":
                    continue
                effect["turns"] = max(0, int(effect.get("turns", 0)) - 1)
