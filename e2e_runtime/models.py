from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal


RunStatus = Literal["queued", "running", "awaiting_visual", "passed", "failed"]
CheckStatus = Literal["passed", "failed", "skipped"]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


@dataclass(slots=True)
class CheckResult:
    name: str
    status: CheckStatus
    details: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class VisualResult:
    case_id: str
    status: CheckStatus
    dhash_distance: int | None = None
    changed_pixel_ratio: float | None = None
    screenshot_path: str | None = None
    golden_path: str | None = None
    diff_path: str | None = None
    notes: str = ""

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "VisualResult":
        status = payload.get("status")
        if status not in ("passed", "failed", "skipped"):
            raise ValueError("visual result status must be passed, failed, or skipped")
        return cls(
            case_id=str(payload["case_id"]),
            status=status,
            dhash_distance=payload.get("dhash_distance"),
            changed_pixel_ratio=payload.get("changed_pixel_ratio"),
            screenshot_path=payload.get("screenshot_path"),
            golden_path=payload.get("golden_path"),
            diff_path=payload.get("diff_path"),
            notes=str(payload.get("notes", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class TestRun:
    run_id: str
    suite: str
    nonce: str
    status: RunStatus = "queued"
    created_at: datetime = field(default_factory=utc_now)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    trigger_message_id: int | None = None
    thread_id: int | None = None
    thread_jump_url: str | None = None
    checks: list[CheckResult] = field(default_factory=list)
    visual_cases: list[dict[str, Any]] = field(default_factory=list)
    visual_results: dict[str, VisualResult] = field(default_factory=dict)
    error: str | None = None

    def to_dict(self, include_nonce: bool = False) -> dict[str, Any]:
        result = {
            "run_id": self.run_id,
            "suite": self.suite,
            "status": self.status,
            "created_at": iso(self.created_at),
            "started_at": iso(self.started_at),
            "finished_at": iso(self.finished_at),
            "trigger_message_id": str(self.trigger_message_id) if self.trigger_message_id else None,
            "thread_id": str(self.thread_id) if self.thread_id else None,
            "thread_jump_url": self.thread_jump_url,
            "checks": [check.to_dict() for check in self.checks],
            "visual_cases": self.visual_cases,
            "visual_results": [value.to_dict() for value in self.visual_results.values()],
            "error": self.error,
        }
        if include_nonce:
            result["nonce"] = self.nonce
        return result
