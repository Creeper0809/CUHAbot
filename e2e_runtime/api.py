from __future__ import annotations

import hmac
from typing import Any

from aiohttp import web

from .manager import E2ERunManager, SUITES, VISUAL_CASE_IDS


def create_app(manager: E2ERunManager, api_token: str, health_provider) -> web.Application:
    if not api_token:
        raise RuntimeError("E2E_API_TOKEN is required")

    @web.middleware
    async def auth(request: web.Request, handler):
        if request.path == "/health":
            return await handler(request)
        authorization = request.headers.get("Authorization", "")
        expected = f"Bearer {api_token}"
        if not hmac.compare_digest(authorization, expected):
            raise web.HTTPUnauthorized(text="Bearer token required")
        return await handler(request)

    app = web.Application(middlewares=[auth], client_max_size=256 * 1024)

    async def health(_: web.Request) -> web.Response:
        value = health_provider()
        if hasattr(value, "__await__"):
            value = await value
        return web.json_response(value)

    async def suites(_: web.Request) -> web.Response:
        return web.json_response({
            "suites": list(SUITES),
            "visual_cases": list(VISUAL_CASE_IDS),
        })

    async def create_run(request: web.Request) -> web.Response:
        try:
            payload: dict[str, Any] = await request.json()
        except Exception as exc:
            raise web.HTTPBadRequest(text="invalid JSON") from exc
        try:
            run = manager.create_run(str(payload.get("suite", "all")))
        except ValueError as exc:
            raise web.HTTPBadRequest(text=str(exc)) from exc
        except RuntimeError as exc:
            raise web.HTTPServiceUnavailable(text=str(exc)) from exc
        return web.json_response(run.to_dict(), status=202)

    async def list_runs(_: web.Request) -> web.Response:
        return web.json_response({"runs": [run.to_dict() for run in manager.list_runs()]})

    async def get_run(request: web.Request) -> web.Response:
        run = manager.get_run(request.match_info["run_id"])
        if not run:
            raise web.HTTPNotFound(text="run not found")
        return web.json_response(run.to_dict())

    async def visual_results(request: web.Request) -> web.Response:
        run = manager.get_run(request.match_info["run_id"])
        if not run:
            raise web.HTTPNotFound(text="run not found")
        try:
            payload = await request.json()
            results = payload.get("results", [])
            if not isinstance(results, list) or not results:
                raise ValueError("results must be a non-empty list")
            manager.submit_visual_results(run, results)
        except (KeyError, TypeError, ValueError) as exc:
            raise web.HTTPBadRequest(text=str(exc)) from exc
        return web.json_response(run.to_dict())

    app.router.add_get("/health", health)
    app.router.add_get("/v1/test-suites", suites)
    app.router.add_get("/v1/test-runs", list_runs)
    app.router.add_post("/v1/test-runs", create_run)
    app.router.add_get("/v1/test-runs/{run_id}", get_run)
    app.router.add_post("/v1/test-runs/{run_id}/visual-results", visual_results)
    return app
