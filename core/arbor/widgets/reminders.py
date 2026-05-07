"""
Reminder Widget — 提醒助手
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException, Query, Request
from pydantic import BaseModel

from .base import Widget, ConfirmIntent, _make_id, _now


# ── Schema ───────────────────────────────────────────────────

class ReminderCreate(BaseModel):
    title: str
    message: str = ""
    remind_at: str
    repeat: str = "none"
    priority: str = "normal"


class ReminderUpdate(BaseModel):
    title: Optional[str] = None
    message: Optional[str] = None
    remind_at: Optional[str] = None
    repeat: Optional[str] = None
    priority: Optional[str] = None


# ── Widget ───────────────────────────────────────────────────

class ReminderWidget(Widget):
    id = "reminders"
    name = "提醒"
    icon = "🔔"

    def init_db(self) -> None:
        with self.get_db() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS reminders (
                    id          TEXT PRIMARY KEY,
                    title       TEXT NOT NULL,
                    message     TEXT DEFAULT '',
                    remind_at   TEXT NOT NULL,
                    repeat      TEXT DEFAULT 'none',
                    priority    TEXT DEFAULT 'normal',
                    active      INTEGER DEFAULT 1,
                    snoozed     INTEGER DEFAULT 0,
                    fired_count INTEGER DEFAULT 0,
                    created_at  TEXT NOT NULL,
                    updated_at  TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_rem_remind ON reminders(remind_at);
                CREATE INDEX IF NOT EXISTS idx_rem_active ON reminders(active, remind_at);
            """)

    # ── CRUD 实现 ──────────────────────────────────────────────

    def list(self, active_only: bool = False) -> list[dict]:
        with self.get_db() as conn:
            if active_only:
                rows = conn.execute(
                    "SELECT * FROM reminders WHERE active=1 ORDER BY remind_at LIMIT 100"
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM reminders ORDER BY remind_at DESC LIMIT 100"
                ).fetchall()
        return [dict(r) for r in rows]

    def get(self, reminder_id: str) -> dict:
        with self.get_db() as conn:
            row = conn.execute("SELECT * FROM reminders WHERE id=?", (reminder_id,)).fetchone()
        if not row:
            raise HTTPException(404, "提醒不存在")
        return dict(row)

    def create(self, data: dict) -> dict:
        rid = _make_id()
        now = _now()
        with self.get_db() as conn:
            conn.execute(
                """INSERT INTO reminders (id, title, message, remind_at, repeat, priority,
                   active, snoozed, fired_count, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,1,0,0,?,?)""",
                (rid, data["title"], data.get("message", ""),
                 data["remind_at"], data.get("repeat", "none"),
                 data.get("priority", "normal"), now, now)
            )
        return dict(conn.execute("SELECT * FROM reminders WHERE id=?", (rid,)).fetchone())

    def update(self, reminder_id: str, data: dict) -> dict:
        with self.get_db() as conn:
            row = conn.execute("SELECT * FROM reminders WHERE id=?", (reminder_id,)).fetchone()
            if not row:
                raise HTTPException(404, "提醒不存在")
            now = _now()
            fields = {"title", "message", "remind_at", "repeat", "priority", "active"}
            sets = []
            vals = []
            for k in fields:
                if k in data:
                    sets.append(f"{k}=?")
                    vals.append(data[k])
            if not sets:
                return dict(row)
            sets.append("updated_at=?")
            vals.append(now)
            vals.append(reminder_id)
            conn.execute(f"UPDATE reminders SET {', '.join(sets)} WHERE id=?", vals)
        return self.get(reminder_id)

    def delete(self, reminder_id: str) -> dict:
        with self.get_db() as conn:
            row = conn.execute("SELECT * FROM reminders WHERE id=?", (reminder_id,)).fetchone()
            if not row:
                raise HTTPException(404, "提醒不存在")
            conn.execute("DELETE FROM reminders WHERE id=?", (reminder_id,))
        return {"id": reminder_id, "status": "deleted"}

    def upcoming(self, hours: int = 24) -> list[dict]:
        now = _now()
        deadline = (datetime.now(tz=timezone.utc) + timedelta(hours=hours)).isoformat()
        with self.get_db() as conn:
            rows = conn.execute(
                "SELECT * FROM reminders WHERE active=1 AND remind_at BETWEEN ? AND ? ORDER BY remind_at",
                (now, deadline)
            ).fetchall()
        return [dict(r) for r in rows]

    def snooze(self, reminder_id: str, minutes: int = 15) -> dict:
        with self.get_db() as conn:
            row = conn.execute("SELECT * FROM reminders WHERE id=?", (reminder_id,)).fetchone()
            if not row:
                raise HTTPException(404, "提醒不存在")
            new_time = (datetime.now(tz=timezone.utc) + timedelta(minutes=minutes)).isoformat()
            now = _now()
            conn.execute(
                "UPDATE reminders SET remind_at=?, snoozed=1, updated_at=? WHERE id=?",
                (new_time, now, reminder_id)
            )
        return self.get(reminder_id)

    # ── Widget 接口 ────────────────────────────────────────────

    def handle_read(self, intent: str, params: dict) -> dict:
        if intent == "upcoming":
            return {"reminders": self.upcoming(int(params.get("hours", 24)))}
        if intent == "get":
            return self.get(params.get("id", ""))
        return {"reminders": self.list(active_only=params.get("active_only", True))}

    def execute_write(self, intent: str, params: dict) -> dict:
        if intent == "create":
            return {"reminder": self.create(params)}
        if intent == "update":
            return {"reminder": self.update(params.get("id", ""), params)}
        if intent == "delete":
            return self.delete(params.get("id", ""))
        if intent == "snooze":
            return {"reminder": self.snooze(params.get("id", ""), int(params.get("minutes", 15)))}
        return {"error": f"unknown intent: {intent}"}

    def get_state(self) -> dict:
        with self.get_db() as conn:
            active = conn.execute("SELECT COUNT(*) as c FROM reminders WHERE active=1").fetchone()["c"]
            upcoming = conn.execute(
                "SELECT COUNT(*) as c FROM reminders WHERE active=1 AND remind_at > ?",
                (_now(),)
            ).fetchone()["c"]
            next_row = conn.execute(
                "SELECT title, remind_at FROM reminders WHERE active=1 AND remind_at > ? ORDER BY remind_at LIMIT 1",
                (_now(),)
            ).fetchone()
        return {
            "active_count": active,
            "upcoming_count": upcoming,
            "next_reminder": dict(next_row) if next_row else None,
        }

    # ── 路由注册 ──────────────────────────────────────────────

    def _register_routes(self) -> None:
        r = self.router

        @r.get("")
        def list_reminders(active: bool = Query(False)):
            return {"reminders": self.list(active_only=active)}

        @r.post("")
        def create_reminder(body: ReminderCreate):
            return {"reminder": self.create(body.model_dump())}

        @r.get("/upcoming")
        def list_upcoming(hours: int = Query(24)):
            return {"reminders": self.upcoming(hours)}

        @r.get("/state")
        def state():
            return self.get_state()

        @r.get("/{reminder_id}")
        def get_reminder(reminder_id: str):
            return self.get(reminder_id)

        @r.put("/{reminder_id}")
        def update_reminder(reminder_id: str, body: ReminderUpdate):
            return {"reminder": self.update(reminder_id, body.model_dump(exclude_none=True))}

        @r.delete("/{reminder_id}")
        def delete_reminder(reminder_id: str):
            return self.delete(reminder_id)

        @r.post("/{reminder_id}/snooze")
        def snooze_reminder(reminder_id: str, minutes: int = Query(15)):
            return {"reminder": self.snooze(reminder_id, minutes)}
