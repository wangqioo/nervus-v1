from __future__ import annotations

import json
import logging
from typing import Any

from .schemas import AppManifest, AppStatus, AppStatusResponse, RegisteredApp

logger = logging.getLogger("nervus.platform.apps")


class AppRegistry:
    def __init__(self):
        self._pool: Any = None
        self._apps: dict[str, RegisteredApp] = {}

    async def init(self, pool: Any) -> None:
        self._pool = pool
        await self._load_from_db()
        logger.info("App Platform loaded %s registered apps", len(self._apps))

    async def _load_from_db(self) -> None:
        if self._pool is None:
            return
        rows = await self._pool.fetch("SELECT app_id, manifest, endpoint_url, status FROM app_registry")
        for row in rows:
            manifest_data = row["manifest"]
            if isinstance(manifest_data, str):
                try:
                    manifest_data = json.loads(manifest_data)
                except (json.JSONDecodeError, TypeError):
                    continue
            manifest = self._parse_manifest(manifest_data, row["endpoint_url"])
            self._apps[manifest.id] = RegisteredApp(
                id=manifest.id,
                name=manifest.name,
                type=manifest.type,
                version=manifest.version,
                description=manifest.description,
                icon=manifest.icon,
                route=manifest.route,
                status=AppStatus(row["status"]) if row["status"] in AppStatus._value2member_map_ else AppStatus.offline,
                endpoint_url=row["endpoint_url"],
                manifest=manifest,
            )

    async def register(self, manifest_data: dict[str, Any], endpoint_url: str = "") -> RegisteredApp:
        manifest = self._parse_manifest(manifest_data, endpoint_url)
        endpoint = endpoint_url or manifest.service.internal_url
        app = RegisteredApp(
            id=manifest.id,
            name=manifest.name,
            type=manifest.type,
            version=manifest.version,
            description=manifest.description,
            icon=manifest.icon,
            route=manifest.route,
            status=AppStatus.online,
            endpoint_url=endpoint,
            manifest=manifest,
        )
        self._apps[app.id] = app
        if self._pool:
            import datetime
            now = datetime.datetime.now(datetime.timezone.utc).isoformat()
            await self._pool.execute(
                """INSERT INTO app_registry (app_id, name, version, description, manifest, endpoint_url, status, last_heartbeat)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT (app_id) DO UPDATE SET
                       name = EXCLUDED.name,
                       version = EXCLUDED.version,
                       description = EXCLUDED.description,
                       manifest = EXCLUDED.manifest,
                       endpoint_url = EXCLUDED.endpoint_url,
                       status = EXCLUDED.status,
                       last_heartbeat = EXCLUDED.last_heartbeat""",
                app.id, app.name, app.version, app.description,
                app.manifest.model_dump_json(), app.endpoint_url,
                app.status.value, now,
            )
        return app

    def list_apps(self) -> list[RegisteredApp]:
        return sorted(self._apps.values(), key=lambda app: app.name)

    def get_app(self, app_id: str) -> RegisteredApp | None:
        return self._apps.get(app_id)

    async def update_heartbeat(self, app_id: str) -> bool:
        app = self._apps.get(app_id)
        if app is None:
            return False
        self._apps[app_id] = app.model_copy(update={"status": AppStatus.online})
        if self._pool:
            await self._pool.execute(
                "UPDATE app_registry SET status = 'online', last_heartbeat = datetime('now') WHERE app_id = ?",
                app_id,
            )
        return True

    async def mark_offline_stale(self, timeout_seconds: int = 120) -> int:
        if self._pool is None:
            return 0
        # SQLite: 标记所有 heartbeat 超时的 online app
        rows = await self._pool.fetch(
            """SELECT app_id FROM app_registry
               WHERE status = 'online'
                 AND last_heartbeat < datetime('now', ?)
                 AND app_id != 'nervus-system'""",
            f"-{timeout_seconds} seconds",
        )
        for row in rows:
            app = self._apps.get(row["app_id"])
            if app:
                self._apps[row["app_id"]] = app.model_copy(update={"status": AppStatus.offline})
            await self._pool.execute(
                "UPDATE app_registry SET status = 'offline' WHERE app_id = ?",
                row["app_id"],
            )
        n = len(rows)
        if n:
            logger.info("marked %s app(s) offline (heartbeat timeout)", n)
        return n

    async def get_status(self, app_id: str) -> AppStatusResponse | None:
        import httpx
        app = self.get_app(app_id)
        if app is None:
            return None
        if not app.endpoint_url:
            return AppStatusResponse(id=app.id, status=AppStatus.not_configured, error="missing endpoint_url")
        health: dict[str, Any] = {}
        state: dict[str, Any] = {}
        try:
            async with httpx.AsyncClient(timeout=2.5) as client:
                health_resp = await client.get(f"{app.endpoint_url.rstrip('/')}/health")
                health_resp.raise_for_status()
                health = health_resp.json()
                state_resp = await client.get(f"{app.endpoint_url.rstrip('/')}/state")
                if state_resp.status_code == 200:
                    state = state_resp.json()
            status = AppStatus.online if health.get("status") in ("ok", "online") else AppStatus.degraded
            return AppStatusResponse(id=app.id, status=status, health=health, state=state)
        except Exception as exc:
            return AppStatusResponse(id=app.id, status=AppStatus.offline, health=health, state=state, error=str(exc))

    async def call_action(self, app_id: str, action_name: str, params: dict[str, Any]) -> dict[str, Any]:
        import httpx
        app = self._apps.get(app_id)
        if not app:
            raise ValueError(f"App {app_id} is not registered")
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(f"{app.endpoint_url.rstrip('/')}/action/{action_name}", json=params)
            resp.raise_for_status()
            return resp.json()

    async def send_intake(self, app_id: str, handler: str, event: dict[str, Any]) -> dict[str, Any]:
        import httpx
        app = self._apps.get(app_id)
        if not app:
            raise ValueError(f"App {app_id} is not registered")
        handler_path = handler.lstrip("/")
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(f"{app.endpoint_url.rstrip('/')}/{handler_path}", json=event)
            resp.raise_for_status()
            return resp.json()

    def find_subscribers(self, subject: str) -> list[dict[str, Any]]:
        result = []
        for app in self._apps.values():
            for pattern in app.manifest.capabilities.consumes:
                if self._subject_matches(subject, pattern):
                    result.append({
                        "app_id": app.id,
                        "endpoint_url": app.endpoint_url,
                        "handler": f"/intake/{subject.replace('.', '_')}",
                        "filter": {},
                        "subject_pattern": pattern,
                    })
        return result

    def find_action_provider(self, app_id: str, action_name: str) -> dict[str, Any] | None:
        app = self._apps.get(app_id)
        if not app:
            return None
        for action in app.manifest.capabilities.actions:
            if action.get("name") == action_name:
                return {"app_id": app_id, "endpoint_url": app.endpoint_url, "action": action}
        return None

    @staticmethod
    def _parse_manifest(data: dict[str, Any], endpoint_url: str = "") -> AppManifest:
        if data.get("schema_version") == "0.1":
            manifest = AppManifest.model_validate(data)
            if endpoint_url and not manifest.service.internal_url:
                manifest.service.internal_url = endpoint_url
            return manifest
        return AppManifest.from_legacy(data, endpoint_url)

    @staticmethod
    def _subject_matches(subject: str, pattern: str) -> bool:
        if pattern == subject:
            return True
        if pattern.endswith(">"):
            return subject.startswith(pattern[:-1])
        subject_parts = subject.split(".")
        pattern_parts = pattern.split(".")
        if len(subject_parts) != len(pattern_parts):
            return False
        return all(pattern == "*" or pattern == part for part, pattern in zip(subject_parts, pattern_parts))
