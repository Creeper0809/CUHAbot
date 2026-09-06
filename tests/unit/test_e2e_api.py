import pytest
from aiohttp.test_utils import TestClient, TestServer

from e2e_runtime.api import create_app
from e2e_runtime.manager import E2ERunManager


async def noop(*args):
    return None


@pytest.mark.asyncio
async def test_health_is_local_probe_without_authentication():
    manager = E2ERunManager(noop, noop)
    app = create_app(manager, "test-token", lambda: {"status": "ok"})
    async with TestClient(TestServer(app)) as client:
        response = await client.get("/health")
        assert response.status == 200
        assert await response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_run_endpoints_require_bearer_and_hide_nonce():
    manager = E2ERunManager(noop, noop)
    app = create_app(manager, "test-token", lambda: {"status": "ok"})
    headers = {"Authorization": "Bearer test-token"}
    async with TestClient(TestServer(app)) as client:
        unauthorized = await client.get("/v1/test-suites")
        assert unauthorized.status == 401

        created = await client.post("/v1/test-runs", json={"suite": "gateway"}, headers=headers)
        assert created.status == 202
        body = await created.json()
        assert body["status"] == "queued"
        assert "nonce" not in body

        fetched = await client.get(f"/v1/test-runs/{body['run_id']}", headers=headers)
        assert fetched.status == 200
        assert (await fetched.json())["run_id"] == body["run_id"]


@pytest.mark.asyncio
async def test_unknown_suite_is_rejected():
    manager = E2ERunManager(noop, noop)
    app = create_app(manager, "test-token", lambda: {"status": "ok"})
    headers = {"Authorization": "Bearer test-token"}
    async with TestClient(TestServer(app)) as client:
        response = await client.post("/v1/test-runs", json={"suite": "nope"}, headers=headers)
        assert response.status == 400
