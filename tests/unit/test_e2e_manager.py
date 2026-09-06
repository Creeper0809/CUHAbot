import asyncio

from e2e_runtime.manager import E2ERunManager, SUITES, VISUAL_CASE_IDS
from e2e_runtime.models import CheckResult


def test_fifo_dispatch_waits_for_current_run_completion():
    async def scenario():
        dispatched = []
        manager = None

        async def dispatch(run):
            dispatched.append(run.run_id)

        async def execute(run, message):
            manager.complete_functional(run, [CheckResult("ok", "passed")])

        manager = E2ERunManager(dispatch, execute, timeout_seconds=1)
        manager.start()
        first = manager.create_run("gateway")
        second = manager.create_run("commands")
        await asyncio.sleep(0)

        assert dispatched == [first.run_id]
        assert await manager.accept_trigger(object(), first.run_id, first.suite, first.nonce)
        await asyncio.sleep(0.01)
        assert dispatched == [first.run_id, second.run_id]
        assert await manager.accept_trigger(object(), second.run_id, second.suite, second.nonce)
        await asyncio.sleep(0.01)
        assert first.status == "passed"
        assert second.status == "passed"
        await manager.stop()

    asyncio.run(scenario())


def test_trigger_requires_matching_suite_and_nonce():
    async def scenario():
        async def dispatch(run):
            return None

        async def execute(run, message):
            raise AssertionError("must not execute")

        manager = E2ERunManager(dispatch, execute)
        run = manager.create_run("gateway")
        assert not await manager.accept_trigger(object(), run.run_id, "commands", run.nonce)
        assert not await manager.accept_trigger(object(), run.run_id, run.suite, "wrong")

    asyncio.run(scenario())


def test_all_supported_suites_are_published():
    assert SUITES == (
        "gateway", "commands", "components", "gameflow", "dungeon", "semantics",
        "roguelike", "rewards", "balance", "farming", "buildcraft", "economy", "visual", "all",
    )
    assert len(VISUAL_CASE_IDS) == 8


def test_all_suite_completes_without_visual_results():
    async def noop(*args):
        return None

    manager = E2ERunManager(noop, noop)
    run = manager.create_run("all")

    manager.complete_functional(run, [CheckResult("functional", "passed")])

    assert run.status == "passed"
    assert run.finished_at is not None


def test_visual_run_completes_only_after_every_case():
    async def noop(*args):
        return None

    manager = E2ERunManager(noop, noop)
    run = manager.create_run("visual")
    run.visual_cases = [{"case_id": case_id} for case_id in VISUAL_CASE_IDS]
    manager.complete_functional(run, [CheckResult("publication", "passed")])
    assert run.status == "awaiting_visual"

    manager.submit_visual_results(run, [
        {"case_id": case_id, "status": "passed", "dhash_distance": 0, "changed_pixel_ratio": 0.0}
        for case_id in VISUAL_CASE_IDS
    ])
    assert run.status == "passed"


def test_visual_failure_fails_run():
    async def noop(*args):
        return None

    manager = E2ERunManager(noop, noop)
    run = manager.create_run("visual")
    run.visual_cases = [{"case_id": "combat"}]
    manager.complete_functional(run, [CheckResult("publication", "passed")])
    manager.submit_visual_results(run, [{"case_id": "combat", "status": "failed"}])
    assert run.status == "failed"
