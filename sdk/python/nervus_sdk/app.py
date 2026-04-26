from __future__ import annotations

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Callable, Awaitable

import httpx
from fastapi import FastAPI, HTTPException, Request
import uvicorn

from .models import AppConfig, AppManifest, Event, EventHandler
from .bus import connect as bus_connect, disconnect as bus_disconnect, subscribe, emit as _emit, make_filter
from .context import connect as ctx_connect, disconnect as ctx_disconnect, Context
from .memory import connect as mem_connect, disconnect as mem_disconnect, MemoryGraph
from .llm import LLMClient

logger = logging.getLogger("nervus.app")

_MANIFEST_SEARCH = [
    os.getenv("NERVUS_MANIFEST_PATH", ""),
    "/app/manifest.json",
    str(Path(__file__).parent.parent.parent / "manifest.json"),
    "manifest.json",
]


def _load_manifest_file() -> dict[str, Any] | None:
    for path in _MANIFEST_SEARCH:
        if path and Path(path).is_file():
            try:
                return json.loads(Path(path).read_text())
            except Exception:
                pass
    return None


class NervusApp:
    def __init__(self, app_id: str, manifest: AppManifest | None = None):
        self.app_id = app_id
        self.config = AppConfig.from_env(app_id)

        self.llm = LLMClient(self.config.llama_url)
        self.memory = MemoryGraph
        self.ctx = Context

        self._handlers: list[tuple[str, dict, EventHandler]] = []
        self._actions: dict[str, Callable] = {}
        self._state_fn: Callable | None = None
        self._manifest: AppManifest | None = manifest

        if self._manifest is None:
            raw = _load_manifest_file()
            if raw:
                try:
                    self._manifest = AppManifest.model_validate(raw)
                except Exception:
                    pass

        self._api = FastAPI(title=f"Nervus App: {app_id}", version="1.0.0")
        self._setup_routes()

        logging.basicConfig(
            level=logging.INFO,
            format=f"%(asctime)s [{app_id}] %(levelname)s %(message)s",
        )

    # ── decorators ───────────────────────────────────────────────────────────

    def on(self, subject: str, filter: dict | None = None):
        def decorator(fn: EventHandler):
            self._handlers.append((subject, filter or {}, fn))
            return fn
        return decorator

    def action(self, name: str):
        def decorator(fn: Callable):
            self._actions[name] = fn
            return fn
        return decorator

    def state(self, fn: Callable):
        self._state_fn = fn
        return fn

    # ── manual API ───────────────────────────────────────────────────────────

    async def emit(self, subject: str, payload: dict, correlation_id: str | None = None) -> None:
        await _emit(subject, payload, correlation_id)

    def mount(self, path: str, router):
        self._api.include_router(router, prefix=path)

    # ── standard NSI routes ──────────────────────────────────────────────────

    def _setup_routes(self):
        api = self._api

        @api.get("/manifest")
        async def get_manifest():
            if self._manifest:
                return self._manifest.model_dump()
            return {"id": self.app_id, "schema_version": "0.1"}

        @api.get("/health")
        async def health():
            return {"status": "ok", "app_id": self.app_id}

        @api.get("/state")
        async def get_state():
            if self._state_fn:
                return {"status": "ok", "state": await self._state_fn()}
            return {"status": "ok", "state": {}}

        @api.post("/intake/{handler_name}")
        async def intake(handler_name: str, request: Request):
            body = await request.json()
            event = Event(**body) if "subject" in body else Event(
                subject=f"intake.{handler_name}",
                payload=body,
                source_app="arbor-core",
            )
            for subject, _filter, fn in self._handlers:
                if handler_name in subject.replace(".", "_") or f"intake/{handler_name}" in subject:
                    filter_fn = make_filter(_filter)
                    if filter_fn is None or filter_fn(event):
                        result = await fn(event)
                        return {"status": "ok", "result": result}
            raise HTTPException(status_code=404, detail=f"No handler for {handler_name}")

        @api.post("/action/{name}")
        async def call_action(name: str, request: Request):
            if name not in self._actions:
                raise HTTPException(status_code=404, detail=f"Action {name} not registered")
            body = await request.json()
            result = await self._actions[name](**body)
            return {"status": "ok", "result": result}

    # ── lifecycle ────────────────────────────────────────────────────────────

    async def _startup(self):
        logger.info("[%s] starting up", self.app_id)
        await bus_connect(self.config.nats_url, self.app_id)
        await ctx_connect(self.config.redis_url)
        await mem_connect(self.config.postgres_url)

        for subject, filter_config, handler in self._handlers:
            filter_fn = make_filter(filter_config)
            await subscribe(subject, handler, filter_fn=filter_fn, queue_group=self.app_id)

        asyncio.create_task(self._register_with_retry())
        asyncio.create_task(self._heartbeat_loop())
        logger.info("[%s] ready on port %s", self.app_id, self.config.port)

    async def _shutdown(self):
        logger.info("[%s] shutting down", self.app_id)
        await bus_disconnect()
        await ctx_disconnect()
        await mem_disconnect()
        await self.llm.close()

    async def _heartbeat_loop(self, interval: int = 60) -> None:
        await asyncio.sleep(interval)
        while True:
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    await client.post(f"{self.config.arbor_url}/apps/{self.app_id}/heartbeat")
            except Exception as exc:
                logger.debug("[%s] heartbeat failed: %s", self.app_id, exc)
            await asyncio.sleep(interval)

    async def _register_with_retry(self, max_attempts: int = 5) -> None:
        manifest_data = self._manifest.model_dump() if self._manifest else {
            "schema_version": "0.1",
            "id": self.app_id,
            "name": self.app_id,
        }
        endpoint_url = self.config.internal_url
        for attempt in range(1, max_attempts + 1):
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.post(
                        f"{self.config.arbor_url}/apps/register",
                        json={"manifest": manifest_data, "endpoint_url": endpoint_url},
                    )
                    resp.raise_for_status()
                logger.info("[%s] registered with Arbor Core", self.app_id)
                return
            except Exception as exc:
                if attempt < max_attempts:
                    wait = 2 ** attempt
                    logger.warning("[%s] registration attempt %s failed (%s); retrying in %ss", self.app_id, attempt, exc, wait)
                    await asyncio.sleep(wait)
                else:
                    logger.error("[%s] registration failed after %s attempts: %s", self.app_id, max_attempts, exc)

    def run(self, port: int | None = None, host: str = "0.0.0.0"):
        if port:
            self.config.port = port

        @asynccontextmanager
        async def lifespan(api: FastAPI):
            await self._startup()
            yield
            await self._shutdown()

        self._api.router.lifespan_context = lifespan
        uvicorn.run(self._api, host=host, port=self.config.port, log_level="info", access_log=False)
