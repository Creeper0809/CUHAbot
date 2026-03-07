"""
Skill component targeting helpers.

This module resolves target scopes such as:
- self / ally / all_allies
- enemy / all_enemies / all
"""
from __future__ import annotations

from typing import Iterable


def find_combat_session(attacker, target=None):
    """Find the combat session containing attacker/target."""
    from service.session import get_session, get_all_sessions

    attacker_discord_id = getattr(attacker, "discord_id", None)
    target_discord_id = getattr(target, "discord_id", None)

    for discord_id in (attacker_discord_id, target_discord_id):
        if discord_id is None:
            continue
        session = get_session(discord_id)
        if session is not None:
            return session

    for session in get_all_sessions().values():
        leader = getattr(session, "user", None)
        if attacker_discord_id and getattr(leader, "discord_id", None) == attacker_discord_id:
            return session
        if target_discord_id and getattr(leader, "discord_id", None) == target_discord_id:
            return session

        participants = getattr(session, "participants", {}) or {}
        for participant in participants.values():
            participant_id = getattr(participant, "discord_id", None)
            if attacker_discord_id and participant_id == attacker_discord_id:
                return session
            if target_discord_id and participant_id == target_discord_id:
                return session

        context = getattr(session, "combat_context", None)
        monsters = getattr(context, "monsters", []) if context else []
        if attacker in monsters or (target is not None and target in monsters):
            return session

    return None


def _unique_alive(entities: Iterable) -> list:
    deduped = []
    seen = set()

    for entity in entities:
        if entity is None:
            continue
        key = getattr(entity, "discord_id", None) or id(entity)
        if key in seen:
            continue
        seen.add(key)

        if hasattr(entity, "now_hp") and entity.now_hp <= 0:
            continue
        deduped.append(entity)

    return deduped


def _get_alive_parties(session, attacker) -> tuple[list, list]:
    """Return (allies, enemies) for attacker in a session."""
    context = getattr(session, "combat_context", None)
    monsters = context.get_all_alive_monsters() if context else []

    players = []
    leader = getattr(session, "user", None)
    if leader is not None:
        players.append(leader)
    participants = getattr(session, "participants", {}) or {}
    players.extend(participants.values())

    players = _unique_alive(players)
    monsters = _unique_alive(monsters)

    if getattr(attacker, "discord_id", None) is not None:
        return players, monsters
    return monsters, players


def _pick_single_ally(allies: list, attacker):
    """Pick one ally, preferring non-self and lowest HP ratio."""
    from models import UserStatEnum

    candidates = [ally for ally in allies if id(ally) != id(attacker)]
    if not candidates:
        return attacker

    def hp_ratio(entity):
        max_hp = entity.get_stat().get(UserStatEnum.HP, getattr(entity, "hp", 1))
        if max_hp <= 0:
            return 1.0
        return entity.now_hp / max_hp

    return min(candidates, key=hp_ratio)


def resolve_targets(attacker, target, target_type: str | None) -> list:
    """
    Resolve target scope for a skill component.

    Supported values:
    - self
    - ally
    - all_allies / all_ally / allies
    - enemy / single
    - all_enemies / all_enemy / enemies / all
    """
    normalized = (target_type or "self").strip().lower()
    session = find_combat_session(attacker, target)

    if session:
        allies, enemies = _get_alive_parties(session, attacker)
    else:
        allies = _unique_alive([attacker])
        enemies = _unique_alive([target]) if target is not None else []

    if normalized in {"self"}:
        return _unique_alive([attacker])

    if normalized in {"ally"}:
        return _unique_alive([_pick_single_ally(allies, attacker)])

    if normalized in {"all_allies", "all_ally", "allies"}:
        return allies

    if normalized in {"enemy", "single"}:
        if target is not None and (not hasattr(target, "now_hp") or target.now_hp > 0):
            return [target]
        return enemies[:1]

    if normalized in {"all_enemies", "all_enemy", "enemies", "all"}:
        return enemies

    return _unique_alive([attacker])
