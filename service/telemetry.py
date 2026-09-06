"""Best-effort append-only gameplay telemetry for Balance V2 tuning."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from models.game_system import GameTelemetryEvent

logger = logging.getLogger(__name__)


async def record_game_event(
    event_type: str,
    *,
    user=None,
    guild_id: int | None = None,
    content_type: str | None = None,
    run_nonce: str | None = None,
    level: int | None = None,
    metrics: dict[str, Any] | None = None,
) -> GameTelemetryEvent | None:
    """Persist telemetry without ever changing the gameplay result."""
    try:
        return await GameTelemetryEvent.create(
            event_type=event_type,
            user_id=getattr(user, "id", None),
            guild_id=guild_id,
            content_type=content_type,
            run_nonce=run_nonce,
            level=level if level is not None else getattr(user, "level", None),
            metrics=metrics or {},
        )
    except Exception:
        logger.exception("Could not persist game telemetry event %s", event_type)
        return None


async def balance_cohort_report(days: int = 7) -> dict[str, Any]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=max(1, days))
    rows = await GameTelemetryEvent.filter(created_at__gte=cutoff).values(
        "event_type", "level", "content_type", "metrics"
    )
    return summarize_balance_events(rows, days=max(1, days))


def summarize_balance_events(rows: list[dict[str, Any]], *, days: int) -> dict[str, Any]:
    """Pure aggregation used by commands, tests, and offline operations."""
    counts: dict[str, int] = {}
    clear_by_band: dict[str, dict[str, int]] = {}
    route_choices: dict[str, int] = {}
    death_rooms: dict[str, int] = {}
    augment_counts: dict[str, int] = {}
    box_grades: dict[str, int] = {}
    gold_earned = gold_spent = 0
    replacements = 0
    for row in rows:
        event_type = row["event_type"]
        counts[event_type] = counts.get(event_type, 0) + 1
        metrics = row.get("metrics") or {}
        level = int(row.get("level") or 1)
        band = f"{((level - 1) // 10) * 10 + 1}-{((level - 1) // 10 + 1) * 10}"
        if event_type == "dungeon_run_finished":
            bucket = clear_by_band.setdefault(band, {"runs": 0, "clears": 0})
            bucket["runs"] += 1
            bucket["clears"] += bool(metrics.get("cleared"))
            gold_earned += int(metrics.get("gold", 0))
            if metrics.get("result") == "death":
                room = str(int(metrics.get("room", 0) or 0))
                death_rooms[room] = death_rooms.get(room, 0) + 1
            augment_key = str(int(metrics.get("augments", 0) or 0))
            augment_counts[augment_key] = augment_counts.get(augment_key, 0) + 1
        elif event_type in {"enhancement", "shop_purchase"}:
            gold_spent += int(metrics.get("cost", 0))
        elif event_type == "equipment_replaced":
            replacements += 1
        elif event_type == "roguelike_route_selected":
            kind = str(metrics.get("kind") or "unknown")
            route_choices[kind] = route_choices.get(kind, 0) + 1
        elif event_type == "box_opened":
            for grade in metrics.get("grades", []):
                key = str(int(grade or 0))
                box_grades[key] = box_grades.get(key, 0) + 1
    return {
        "days": max(1, days),
        "events": len(rows),
        "counts": counts,
        "clear_by_level_band": {
            band: {**value, "clear_rate": value["clears"] / max(1, value["runs"])}
            for band, value in sorted(clear_by_band.items())
        },
        "gold_earned": gold_earned,
        "gold_spent": gold_spent,
        "gold_spend_ratio": gold_spent / max(1, gold_earned),
        "equipment_replacements": replacements,
        "route_choices": route_choices,
        "death_rooms": death_rooms,
        "augment_counts": augment_counts,
        "box_grades": box_grades,
    }


async def cleanup_game_events(days: int = 180) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(days=max(30, days))
    return await GameTelemetryEvent.filter(created_at__lt=cutoff).delete()
