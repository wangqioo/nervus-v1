"""
Alarms Widget — 闹钟
与提醒(Reminder)不同：闹钟是固定时间的每日/定时响铃，不涉及 snooze、优先级、认知负荷
"""

from __future__ import annotations

import json
from typing import Optional

from fastapi import HTTPException, Query
from pydantic import BaseModel

from .base import Widget, _make_id, _now


# ── Schema ───────────────────────────────────────────────────

class AlarmCreate(BaseModel):
    title: str
    hour: int
    minute: int
    enabled: bool = True
    repeat: str = "daily"          # once / daily / weekdays / weekends
    sound: str = "default"


class AlarmUpdate(BaseModel):
    title: Optional[str] = None
    hour: Optional[int] = None
    minute: Optional[int] = None
    enabled: Optional[bool] = None
    repeat: Optional[str] = None
    sound: Optional[str] = None


# ── Widget ───────────────────────────────────────────────────

class AlarmsWidget(Widget):
    id = "alarms"
    name = "闹钟"
    icon = "⏰"

    def init_db(self) -> None:
        with self.get_db() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS alarms (
                    id          TEXT PRIMARY KEY,
                    title       TEXT NOT NULL,
                    hour        INTEGER NOT NULL,
                    minute      INTEGER NOT NULL,
                    enabled     INTEGER DEFAULT 1,
                    repeat      TEXT DEFAULT 'daily',
                    sound       TEXT DEFAULT 'default',
                    created_at  TEXT NOT NULL,
                    updated_at  TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_alarms_time ON alarms(hour, minute);
            """)

    # ── CRUD ──────────────────────────────────────────────────

    def list(self, enabled_only: bool = False) -> list[dict]:
        with self.get_db() as conn:
            if enabled_only:
                rows = conn.execute(
                    "SELECT * FROM alarms WHERE enabled=1 ORDER BY hour, minute"
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM alarms ORDER BY hour, minute"
                ).fetchall()
        return [dict(r) for r in rows]

    def get(self, alarm_id: str) -> dict:
        with self.get_db() as conn:
            row = conn.execute("SELECT * FROM alarms WHERE id=?", (alarm_id,)).fetchone()
        if not row:
            raise HTTPException(404, "闹钟不存在")
        return dict(row)

    def create(self, data: dict) -> dict:
        aid = _make_id()
        now = _now()
        # validate hour/minute
        hour, minute = int(data["hour"]), int(data["minute"])
        if not (0 <= hour <= 23):
            raise HTTPException(422, "hour 必须在 0-23")
        if not (0 <= minute <= 59):
            raise HTTPException(422, "minute 必须在 0-59")
        with self.get_db() as conn:
            conn.execute(
                """INSERT INTO alarms (id, title, hour, minute, enabled, repeat, sound, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (aid, data["title"], hour, minute,
                 int(data.get("enabled", True)),
                 data.get("repeat", "daily"),
                 data.get("sound", "default"), now, now)
            )
        return self.get(aid)

    def update(self, alarm_id: str, data: dict) -> dict:
        with self.get_db() as conn:
            row = conn.execute("SELECT * FROM alarms WHERE id=?", (alarm_id,)).fetchone()
            if not row:
                raise HTTPException(404, "闹钟不存在")
            now = _now()
            fields = {"title", "hour", "minute", "enabled", "repeat", "sound"}
            sets = []
            vals = []
            for k in fields:
                if k in data:
                    sets.append(f"{k}=?")
                    v = int(data[k]) if k in ("enabled", "hour", "minute") else data[k]
                    vals.append(v)
            if not sets:
                return dict(row)
            sets.append("updated_at=?")
            vals.append(now)
            vals.append(alarm_id)
            conn.execute(f"UPDATE alarms SET {', '.join(sets)} WHERE id=?", vals)
        return self.get(alarm_id)

    def delete(self, alarm_id: str) -> dict:
        with self.get_db() as conn:
            row = conn.execute("SELECT * FROM alarms WHERE id=?", (alarm_id,)).fetchone()
            if not row:
                raise HTTPException(404, "闹钟不存在")
            conn.execute("DELETE FROM alarms WHERE id=?", (alarm_id,))
        return {"id": alarm_id, "status": "deleted"}

    def toggle(self, alarm_id: str) -> dict:
        with self.get_db() as conn:
            row = conn.execute("SELECT * FROM alarms WHERE id=?", (alarm_id,)).fetchone()
            if not row:
                raise HTTPException(404, "闹钟不存在")
            now = _now()
            new_val = 0 if row["enabled"] else 1
            conn.execute("UPDATE alarms SET enabled=?, updated_at=? WHERE id=?", (new_val, now, alarm_id))
        return self.get(alarm_id)

    # ── Widget 接口 ────────────────────────────────────────────

    def handle_read(self, intent: str, params: dict) -> dict:
        if intent == "get":
            return self.get(params.get("id", ""))
        return {"alarms": self.list(enabled_only=params.get("enabled_only", False))}

    def execute_write(self, intent: str, params: dict) -> dict:
        if intent == "create":
            return {"alarm": self.create(params)}
        if intent == "update":
            return {"alarm": self.update(params.get("id", ""), params)}
        if intent == "delete":
            return self.delete(params.get("id", ""))
        if intent == "toggle":
            return {"alarm": self.toggle(params.get("id", ""))}
        return {"error": f"unknown intent: {intent}"}

    def get_state(self) -> dict:
        with self.get_db() as conn:
            total = conn.execute("SELECT COUNT(*) as c FROM alarms").fetchone()["c"]
            enabled = conn.execute("SELECT COUNT(*) as c FROM alarms WHERE enabled=1").fetchone()["c"]
            next_row = conn.execute(
                "SELECT title, hour, minute FROM alarms WHERE enabled=1 ORDER BY hour, minute LIMIT 1"
            ).fetchone()
        return {
            "total": total,
            "enabled": enabled,
            "next_alarm": dict(next_row) if next_row else None,
        }

    # ── 路由 ──────────────────────────────────────────────────

    def _register_routes(self) -> None:
        r = self.router

        @r.get("")
        def list_alarms(enabled: bool = Query(False)):
            return {"alarms": self.list(enabled_only=enabled)}

        @r.post("")
        def create_alarm(body: AlarmCreate):
            return {"alarm": self.create(body.model_dump())}

        @r.get("/state")
        def state():
            return self.get_state()

        @r.get("/{alarm_id}")
        def get_alarm(alarm_id: str):
            return self.get(alarm_id)

        @r.put("/{alarm_id}")
        def update_alarm(alarm_id: str, body: AlarmUpdate):
            return {"alarm": self.update(alarm_id, body.model_dump(exclude_none=True))}

        @r.delete("/{alarm_id}")
        def delete_alarm(alarm_id: str):
            return self.delete(alarm_id)

        @r.post("/{alarm_id}/toggle")
        def toggle_alarm(alarm_id: str):
            return {"alarm": self.toggle(alarm_id)}
