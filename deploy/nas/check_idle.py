"""Fail-closed check of a SIGSTOP-frozen legacy Bot's complete session log.

The old Bot has no maintenance API. Run only after freezing admissions, with its
complete container log. Reject truncated history, outstanding sessions, or a
session ending in the last 60 seconds (its final save may still be in flight).
"""
import datetime as dt
import json
import re
import sys
from zoneinfo import ZoneInfo


def check(lines, now=None):
    active = set()
    ready = False
    latest = None
    for line in lines:
        if "Logged in as " in line:
            ready = True
        match = re.search(r"(Creating new|Ending) session for user (\d+)", line)
        if not match:
            continue
        if not ready:
            raise RuntimeError("Log history starts after Bot startup; idle state cannot be proven")
        stamp = re.search(r"\d{4}-\d\d-\d\d \d\d:\d\d:\d\d", line)
        if not stamp:
            raise RuntimeError("Missing session timestamp")
        latest = dt.datetime.fromisoformat(stamp[0]).replace(tzinfo=ZoneInfo("Asia/Seoul"))
        if match[1] == "Creating new":
            active.add(match[2])
        else:
            active.discard(match[2])
    if not ready or active:
        raise RuntimeError(f"Bot is not provably idle; pending sessions={len(active)}")
    now = now or dt.datetime.now(dt.timezone.utc)
    if latest and (now - latest).total_seconds() < 60:
        raise RuntimeError("Wait for the final session save to settle")
    return {"idle": True, "pending_sessions": 0, "last_session_event": latest.isoformat() if latest else None}


if __name__ == "__main__":
    print(json.dumps(check(sys.stdin)))
