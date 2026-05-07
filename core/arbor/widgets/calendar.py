"""
Calendar Widget — 日程管理
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException, Query
from pydantic import BaseModel

from .base import Widget, ConfirmIntent, _make_id, _now, _today


# ── Schema ───────────────────────────────────────────────────

class EventCreate(BaseModel):
    title: str
    description: str = ""
    location: str = ""
    start_at: str
    end_at: str = ""
    all_day: bool = False
    color: str = "#4A90E2"


class EventUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    location: Optional[str] = None
    start_at: Optional[str] = None
    end_at: Optional[str] = None
    all_day: Optional[bool] = None
    color: Optional[str] = None


# ── Widget ───────────────────────────────────────────────────

class CalendarWidget(Widget):
    id = "calendar"
    name = "日历"
    icon = "📅"

    def init_db(self) -> None:
        with self.get_db() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS events (
                    id          TEXT PRIMARY KEY,
                    title       TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    location    TEXT DEFAULT '',
                    start_at    TEXT NOT NULL,
                    end_at      TEXT NOT NULL,
                    all_day     INTEGER DEFAULT 0,
                    recurrence  TEXT DEFAULT '',
                    color       TEXT DEFAULT '#4A90E2',
                    status     TEXT DEFAULT 'confirmed',
                    created_at  TEXT NOT NULL,
                    updated_at  TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_ev_start ON events(start_at);
                CREATE INDEX IF NOT EXISTS idx_ev_date ON events(date(start_at));
            """)

    # ── CRUD ──────────────────────────────────────────────────

    def list(self, date_from: str = "", date_to: str = "", limit: int = 100) -> list[dict]:
        today = _today()
        from_dt = date_from or today
        to_dt = date_to or (date.today() + timedelta(days=30)).isoformat()
        with self.get_db() as conn:
            rows = conn.execute(
                "SELECT * FROM events WHERE date(start_at) >= ? AND date(start_at) <= ? ORDER BY start_at LIMIT ?",
                (from_dt, to_dt, limit)
            ).fetchall()
        return [_event_to_dict(r) for r in rows]

    def get(self, event_id: str) -> dict:
        with self.get_db() as conn:
            row = conn.execute("SELECT * FROM events WHERE id=?", (event_id,)).fetchone()
        if not row:
            raise HTTPException(404, "日程事件不存在")
        return _event_to_dict(row)

    def create(self, data: dict) -> dict:
        eid = _make_id()
        now = _now()
        end_at = data.get("end_at") or data["start_at"]
        with self.get_db() as conn:
            conn.execute(
                """INSERT INTO events (id, title, description, location, start_at, end_at,
                   all_day, color, status, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (eid, data["title"], data.get("description", ""), data.get("location", ""),
                 data["start_at"], end_at, int(data.get("all_day", False)),
                 data.get("color", "#4A90E2"), "confirmed", now, now)
            )
        return self.get(eid)

    def update(self, event_id: str, data: dict) -> dict:
        with self.get_db() as conn:
            row = conn.execute("SELECT * FROM events WHERE id=?", (event_id,)).fetchone()
            if not row:
                raise HTTPException(404, "日程事件不存在")
            now = _now()
            fields = {"title", "description", "location", "start_at", "end_at", "all_day", "color"}
            sets = []
            vals = []
            for k in fields:
                if k in data:
                    sets.append(f"{k}=?")
                    v = int(data[k]) if k == "all_day" else data[k]
                    vals.append(v)
            if not sets:
                return _event_to_dict(row)
            sets.append("updated_at=?")
            vals.append(now)
            vals.append(event_id)
            conn.execute(f"UPDATE events SET {', '.join(sets)} WHERE id=?", vals)
        return self.get(event_id)

    def delete(self, event_id: str) -> dict:
        with self.get_db() as conn:
            row = conn.execute("SELECT * FROM events WHERE id=?", (event_id,)).fetchone()
            if not row:
                raise HTTPException(404, "日程事件不存在")
            conn.execute("DELETE FROM events WHERE id=?", (event_id,))
        return {"id": event_id, "status": "deleted"}

    def today(self) -> list[dict]:
        today = _today()
        with self.get_db() as conn:
            rows = conn.execute(
                "SELECT * FROM events WHERE date(start_at)=? ORDER BY start_at", (today,)
            ).fetchall()
        return [_event_to_dict(r) for r in rows]

    def upcoming(self, hours: int = 24) -> list[dict]:
        now = _now()
        deadline = (datetime.now(tz=timezone.utc) + timedelta(hours=hours)).isoformat()
        with self.get_db() as conn:
            rows = conn.execute(
                "SELECT * FROM events WHERE start_at > ? AND start_at < ? ORDER BY start_at LIMIT 20",
                (now, deadline)
            ).fetchall()
        return [_event_to_dict(r) for r in rows]

    # ── Widget 接口 ────────────────────────────────────────────

    def handle_read(self, intent: str, params: dict) -> dict:
        if intent == "today":
            return {"date": _today(), "events": self.today()}
        if intent == "upcoming":
            return {"events": self.upcoming(int(params.get("hours", 24)))}
        if intent == "get":
            return self.get(params.get("id", ""))
        return {
            "events": self.list(
                date_from=params.get("date_from", ""),
                date_to=params.get("date_to", ""),
                limit=int(params.get("limit", 100))
            )
        }

    def execute_write(self, intent: str, params: dict) -> dict:
        if intent == "create":
            return {"event": self.create(params)}
        if intent == "update":
            return {"event": self.update(params.get("id", ""), params)}
        if intent == "delete":
            return self.delete(params.get("id", ""))
        return {"error": f"unknown intent: {intent}"}

    def get_state(self) -> dict:
        with self.get_db() as conn:
            today = _today()
            today_count = conn.execute(
                "SELECT COUNT(*) as c FROM events WHERE date(start_at)=?", (today,)
            ).fetchone()["c"]
            next_row = conn.execute(
                "SELECT title, start_at FROM events WHERE start_at > ? ORDER BY start_at LIMIT 1",
                (_now(),)
            ).fetchone()
        return {
            "today_events": today_count,
            "next_event": dict(next_row) if next_row else None,
        }

    # ── 路由 ──────────────────────────────────────────────────

    def _register_routes(self) -> None:
        r = self.router

        @r.get("")
        def list_events(date_from: str = Query(""), date_to: str = Query(""), limit: int = Query(100)):
            return {"events": self.list(date_from, date_to, limit)}

        @r.post("")
        def create_event(body: EventCreate):
            return {"event": self.create(body.model_dump())}

        @r.get("/today")
        def today_events():
            return {"date": _today(), "events": self.today()}

        @r.get("/upcoming")
        def upcoming_events(hours: int = Query(24)):
            return {"events": self.upcoming(hours)}

        @r.get("/state")
        def state():
            return self.get_state()

        @r.get("/{event_id}")
        def get_event(event_id: str):
            return self.get(event_id)

        @r.put("/{event_id}")
        def update_event(event_id: str, body: EventUpdate):
            return {"event": self.update(event_id, body.model_dump(exclude_none=True))}

        @r.delete("/{event_id}")
        def delete_event(event_id: str):
            return self.delete(event_id)


# ── 辅助 ─────────────────────────────────────────────────────

def _event_to_dict(row) -> dict:
    d = dict(row)
    d["all_day"] = bool(d.get("all_day", 0))
    return d
