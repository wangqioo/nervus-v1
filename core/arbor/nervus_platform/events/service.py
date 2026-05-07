from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from .schemas import PlatformEvent

logger = logging.getLogger("nervus.platform.events")


class EventService:
    def __init__(self) -> None:
        self._pool: Any = None

    async def init(self, pool: Any) -> None:
        self._pool = pool

    async def ingest(self, subject: str, payload: dict[str, Any], source_app: str = "system") -> PlatformEvent | None:
        if self._pool is None:
            logger.warning("EventService: no DB pool, skipping persist for %s", subject)
            return None
        row = await self._pool.fetchrow(
            """INSERT INTO platform_events (subject, payload, source_app)
               VALUES (?, ?, ?)
               RETURNING id, subject, payload, source_app, created_at""",
            subject,
            json.dumps(payload),
            source_app,
        )
        if row is None:
            return None
        return _row_to_event(row)

    async def get_recent(
        self,
        limit: int = 50,
        subject_prefix: str = "",
        source_app: str = "",
        since: datetime | None = None,
        offset: int = 0,
    ) -> list[PlatformEvent]:
        if self._pool is None:
            return []

        conditions: list[str] = []
        params: list[Any] = []

        if subject_prefix:
            conditions.append("subject LIKE ?")
            params.append(f"{subject_prefix}%")

        if source_app:
            conditions.append("source_app = ?")
            params.append(source_app)

        if since:
            conditions.append("created_at >= ?")
            params.append(since.isoformat())

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        params.extend([limit, offset])

        rows = await self._pool.fetch(
            f"""SELECT id, subject, payload, source_app, created_at
                FROM platform_events
                {where}
                ORDER BY created_at DESC LIMIT ? OFFSET ?""",
            *params,
        )
        return [_row_to_event(r) for r in rows]

    async def count(self, subject_prefix: str = "", source_app: str = "") -> int:
        if self._pool is None:
            return 0
        conditions: list[str] = []
        params: list[Any] = []
        if subject_prefix:
            conditions.append("subject LIKE ?")
            params.append(f"{subject_prefix}%")
        if source_app:
            conditions.append("source_app = ?")
            params.append(source_app)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        row = await self._pool.fetchrow(f"SELECT COUNT(*) AS cnt FROM platform_events {where}", *params)
        return row["cnt"] if row else 0


def _row_to_event(row: dict) -> PlatformEvent:
    payload_data = row["payload"]
    if isinstance(payload_data, str):
        try:
            payload_data = json.loads(payload_data)
        except (json.JSONDecodeError, TypeError):
            payload_data = {}
    return PlatformEvent(
        id=str(row["id"]),
        subject=row["subject"],
        payload=payload_data,
        source_app=row.get("source_app", "system"),
        created_at=row.get("created_at"),
    )
