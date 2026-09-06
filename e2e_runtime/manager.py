from __future__ import annotations

import asyncio
import logging
import secrets
import uuid
from collections import OrderedDict
from collections.abc import Awaitable, Callable

from .models import CheckResult, TestRun, VisualResult, utc_now


logger = logging.getLogger(__name__)

SUITES = (
    "gateway", "commands", "components", "gameflow", "dungeon", "semantics",
    "roguelike", "rewards", "balance", "farming", "buildcraft", "economy", "visual", "all",
)
VISUAL_CASE_IDS = (
    "dungeon-select",
    "combat",
    "inventory",
    "skill-deck",
    "auction",
    "tower",
    "raid-lobby",
    "user-info",
)

Dispatch = Callable[[TestRun], Awaitable[None]]
Execute = Callable[[TestRun, object], Awaitable[None]]


class E2ERunManager:
    """FIFO coordinator for Discord-triggered E2E runs."""

    def __init__(
        self,
        dispatch: Dispatch,
        execute: Execute,
        *,
        queue_size: int = 10,
        timeout_seconds: float = 900,
        history_size: int = 100,
    ) -> None:
        self._dispatch = dispatch
        self._execute = execute
        self._queue: asyncio.Queue[str] = asyncio.Queue(maxsize=queue_size)
        self._runs: OrderedDict[str, TestRun] = OrderedDict()
        self._events: dict[str, asyncio.Event] = {}
        self._accepted: set[str] = set()
        self._worker: asyncio.Task | None = None
        self._timeout_seconds = timeout_seconds
        self._history_size = history_size

    def start(self) -> None:
        if not self._worker or self._worker.done():
            self._worker = asyncio.create_task(self._work(), name="discord-e2e-fifo")

    async def stop(self) -> None:
        if self._worker:
            self._worker.cancel()
            try:
                await self._worker
            except asyncio.CancelledError:
                pass
            self._worker = None

    def create_run(self, suite: str) -> TestRun:
        if suite not in SUITES:
            raise ValueError(f"unknown suite: {suite}")
        run_id = str(uuid.uuid4())
        run = TestRun(run_id=run_id, suite=suite, nonce=secrets.token_urlsafe(24))
        self._runs[run_id] = run
        self._events[run_id] = asyncio.Event()
        try:
            self._queue.put_nowait(run_id)
        except asyncio.QueueFull:
            self._runs.pop(run_id, None)
            self._events.pop(run_id, None)
            raise RuntimeError("E2E queue is full")
        self._trim_history()
        return run

    def get_run(self, run_id: str) -> TestRun | None:
        return self._runs.get(run_id)

    def list_runs(self) -> list[TestRun]:
        return list(reversed(self._runs.values()))

    async def accept_trigger(self, message: object, run_id: str, suite: str, nonce: str) -> bool:
        run = self._runs.get(run_id)
        if not run or run.suite != suite or not secrets.compare_digest(run.nonce, nonce):
            return False
        if run_id in self._accepted or run.status != "queued":
            return False
        self._accepted.add(run_id)
        run.status = "running"
        run.started_at = utc_now()
        try:
            await self._execute(run, message)
        except Exception as exc:
            logger.exception("Discord E2E run %s failed", run_id)
            self.fail(run, f"runner error: {type(exc).__name__}: {exc}")
        finally:
            self._events[run_id].set()
        return True

    def complete_functional(self, run: TestRun, checks: list[CheckResult]) -> None:
        run.checks.extend(checks)
        failed = any(check.status == "failed" for check in run.checks)
        # Browser/Golden checks are optional. The aggregate `all` suite is the
        # unattended functional gate and must finish without a Discord Web
        # login session.
        needs_visual = run.suite == "visual" and not failed
        if needs_visual:
            run.status = "awaiting_visual"
        else:
            run.status = "failed" if failed else "passed"
            run.finished_at = utc_now()

    def fail(self, run: TestRun, error: str) -> None:
        run.error = error
        run.status = "failed"
        run.finished_at = utc_now()

    def submit_visual_results(self, run: TestRun, payloads: list[dict]) -> TestRun:
        if run.status != "awaiting_visual":
            raise ValueError("run is not awaiting visual results")
        expected = {case["case_id"] for case in run.visual_cases}
        for payload in payloads:
            result = VisualResult.from_payload(payload)
            if result.case_id not in expected:
                raise ValueError(f"unexpected visual case: {result.case_id}")
            run.visual_results[result.case_id] = result

        if expected.issubset(run.visual_results):
            run.finished_at = utc_now()
            run.status = (
                "passed"
                if all(run.visual_results[case_id].status == "passed" for case_id in expected)
                else "failed"
            )
        return run

    async def _work(self) -> None:
        while True:
            run_id = await self._queue.get()
            run = self._runs[run_id]
            event = self._events[run_id]
            try:
                await self._dispatch(run)
                await asyncio.wait_for(event.wait(), timeout=self._timeout_seconds)
            except asyncio.TimeoutError:
                self.fail(run, "timed out waiting for the Discord Gateway trigger or runner")
            except Exception as exc:
                logger.exception("Could not dispatch E2E run %s", run_id)
                self.fail(run, f"dispatch error: {type(exc).__name__}: {exc}")
            finally:
                self._accepted.discard(run_id)
                self._queue.task_done()

    def _trim_history(self) -> None:
        while len(self._runs) > self._history_size:
            oldest_id, oldest = next(iter(self._runs.items()))
            if oldest.status in ("queued", "running", "awaiting_visual"):
                break
            self._runs.pop(oldest_id, None)
            self._events.pop(oldest_id, None)
