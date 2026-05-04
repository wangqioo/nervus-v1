"""
Calendar App — 日程管理
管理本地日程事件，与 Context Graph 同步今日日程和即将到来的事件
根据认知负荷提供日程调整建议
"""

import os
import asyncio
import sqlite3
import json
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Optional

import sys
sys.path.insert(0, "/app/nervus-sdk")
from nervus_sdk import NervusApp, Context, emit
from nervus_sdk.models import Event
from nervus_sdk.llm import LLMClient

nervus = NervusApp("calendar")

DB_PATH = os.getenv("DB_PATH", "/data/calendar.db")
ARBOR_URL = os.getenv("ARBOR_URL", "http://nervus-arbor:8090")
llm = LLMClient(ARBOR_URL)

# ── 数据库初始化 ──────────────────────────────────────────


def get_db():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
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
                status      TEXT DEFAULT 'confirmed',
                created_at  TEXT NOT NULL,
                updated_at  TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_events_start ON events(start_at);
            CREATE INDEX IF NOT EXISTS idx_events_date ON events(date(start_at));
        """)


init_db()


# ── 工具函数 ──────────────────────────────────────────────

def _make_id() -> str:
    import uuid
    return str(uuid.uuid4())


def _event_to_dict(row) -> dict:
    d = dict(row)
    d["all_day"] = bool(d.get("all_day", 0))
    return d


def _today_str() -> str:
    return date.today().isoformat()


async def _sync_context():
    """将今日日程和即将到来的事件同步到 Context Graph"""
    today = _today_str()
    now_dt = datetime.utcnow()
    next_24h = (now_dt + timedelta(hours=24)).isoformat()

    with get_db() as conn:
        today_events = conn.execute(
            "SELECT title, start_at, end_at FROM events WHERE date(start_at) = ? ORDER BY start_at",
            (today,)
        ).fetchall()

        upcoming = conn.execute(
            "SELECT title, start_at FROM events WHERE start_at > ? AND start_at < ? ORDER BY start_at LIMIT 5",
            (now_dt.isoformat(), next_24h)
        ).fetchall()

    schedule_str = " | ".join(f"{r['title']} {r['start_at'][11:16]}-{r['end_at'][11:16]}" for r in today_events)
    upcoming_list = [{"title": r["title"], "start_at": r["start_at"]} for r in upcoming]

    await Context.set("temporal.current_schedule", schedule_str)
    await Context.set("temporal.upcoming_events", upcoming_list)


# ── 事件订阅 ──────────────────────────────────────────────

@nervus.on("context.user_state.updated")
async def handle_state_update(event: Event):
    """认知负荷变化时更新日程建议"""
    payload = event.payload
    if payload.get("field") == "cognitive.load":
        # 同步 context，感知页会自动刷新
        await _sync_context()
    return {"status": "ok"}


@nervus.on("schedule.event.created")
async def handle_external_event(event: Event):
    """接收外部创建的日程事件（如来自其他应用）"""
    payload = event.payload
    title = payload.get("title", "")
    start_at = payload.get("start_at", "")
    end_at = payload.get("end_at", start_at)

    if title and start_at:
        event_id = _make_id()
        now = datetime.utcnow().isoformat()
        with get_db() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO events (id, title, start_at, end_at, created_at, updated_at) VALUES (?,?,?,?,?,?)",
                (event_id, title, start_at, end_at, now, now)
            )
        await _sync_context()

    return {"status": "ok"}


# ── Actions ───────────────────────────────────────────────

@nervus.action("create_event")
async def action_create_event(payload: dict) -> dict:
    """创建日程事件"""
    title = payload.get("title", "").strip()
    start_at = payload.get("start_at", "").strip()
    end_at = payload.get("end_at", start_at).strip()
    description = payload.get("description", "")
    location = payload.get("location", "")
    all_day = bool(payload.get("all_day", False))
    color = payload.get("color", "#4A90E2")

    if not title:
        return {"error": "title 不能为空"}
    if not start_at:
        return {"error": "start_at 不能为空"}

    event_id = _make_id()
    now = datetime.utcnow().isoformat()

    with get_db() as conn:
        conn.execute(
            """INSERT INTO events (id, title, description, location, start_at, end_at, all_day, color, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (event_id, title, description, location, start_at, end_at, int(all_day), color, now, now)
        )

    await _sync_context()
    await emit("schedule.event.created", {
        "event_id": event_id,
        "title": title,
        "start_at": start_at,
        "end_at": end_at,
    })

    return {"event_id": event_id, "status": "created"}


@nervus.action("get_today_schedule")
async def action_get_today_schedule(payload: dict) -> dict:
    """获取今日日程"""
    today = _today_str()
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM events WHERE date(start_at) = ? ORDER BY start_at",
            (today,)
        ).fetchall()
    return {"date": today, "events": [_event_to_dict(r) for r in rows]}


@nervus.action("suggest_schedule")
async def action_suggest_schedule(payload: dict) -> dict:
    """根据认知负荷建议日程调整"""
    cognitive_load = payload.get("cognitive_load") or await Context.get("cognitive.load", "medium")

    today = _today_str()
    with get_db() as conn:
        rows = conn.execute(
            "SELECT title, start_at, end_at FROM events WHERE date(start_at) >= ? ORDER BY start_at LIMIT 10",
            (today,)
        ).fetchall()

    events_summary = [{"title": r["title"], "start": r["start_at"][11:16], "end": r["end_at"][11:16]} for r in rows]

    if not events_summary:
        return {"suggestions": [], "cognitive_load": cognitive_load}

    try:
        result = await llm.chat_json(
            system="你是一个时间管理助手。根据用户的认知负荷状态，给出简洁的日程调整建议。返回 JSON: {\"suggestions\": [{\"type\": \"info|warning|tip\", \"message\": \"...\"}]}",
            messages=[{
                "role": "user",
                "content": f"当前认知负荷：{cognitive_load}\n今后的日程：{json.dumps(events_summary, ensure_ascii=False)}\n请给出 2-3 条建议。"
            }]
        )
        suggestions = result.get("suggestions", [])
    except Exception:
        # 本地规则回退
        suggestions = []
        if cognitive_load == "high":
            suggestions.append({"type": "warning", "message": "认知负荷较高，建议推迟非紧急会议"})
            suggestions.append({"type": "tip", "message": "尝试在午休后安排需要高度专注的任务"})
        elif cognitive_load == "low":
            suggestions.append({"type": "info", "message": "状态良好，适合处理重要且复杂的任务"})
        else:
            suggestions.append({"type": "info", "message": "状态正常，按计划执行即可"})

    return {"suggestions": suggestions, "cognitive_load": cognitive_load}


@nervus.action("delete_event")
async def action_delete_event(payload: dict) -> dict:
    event_id = payload.get("event_id")
    if not event_id:
        return {"error": "event_id 不能为空"}
    with get_db() as conn:
        conn.execute("DELETE FROM events WHERE id = ?", (event_id,))
    await _sync_context()
    return {"event_id": event_id, "status": "deleted"}


# ── REST API ──────────────────────────────────────────────

@nervus._api.get("/events")
async def list_events(date_from: Optional[str] = None, date_to: Optional[str] = None, limit: int = 50):
    """查询日程，支持日期范围筛选"""
    today = _today_str()
    from_dt = date_from or today
    to_dt = date_to or (date.today() + timedelta(days=30)).isoformat()

    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM events WHERE date(start_at) >= ? AND date(start_at) <= ? ORDER BY start_at LIMIT ?",
            (from_dt, to_dt, limit)
        ).fetchall()
    return {"events": [_event_to_dict(r) for r in rows]}


@nervus._api.get("/events/today")
async def today_events():
    return await action_get_today_schedule({})


@nervus._api.get("/events/upcoming")
async def upcoming_events(hours: int = 24):
    now_dt = datetime.utcnow()
    end_dt = (now_dt + timedelta(hours=hours)).isoformat()
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM events WHERE start_at > ? AND start_at < ? ORDER BY start_at",
            (now_dt.isoformat(), end_dt)
        ).fetchall()
    return {"events": [_event_to_dict(r) for r in rows]}


@nervus._api.post("/events")
async def create_event_api(body: dict):
    return await action_create_event(body)


@nervus._api.get("/events/{event_id}")
async def get_event_api(event_id: str):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
    if not row:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="事件不存在")
    return _event_to_dict(row)


@nervus._api.put("/events/{event_id}")
async def update_event_api(event_id: str, body: dict):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
        if not row:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="事件不存在")

        now = datetime.utcnow().isoformat()
        conn.execute(
            """UPDATE events SET title=?, description=?, location=?, start_at=?, end_at=?,
               all_day=?, color=?, updated_at=? WHERE id=?""",
            (
                body.get("title", row["title"]),
                body.get("description", row["description"]),
                body.get("location", row["location"]),
                body.get("start_at", row["start_at"]),
                body.get("end_at", row["end_at"]),
                int(body.get("all_day", row["all_day"])),
                body.get("color", row["color"]),
                now, event_id
            )
        )
    await _sync_context()
    return {"event_id": event_id, "status": "updated"}


@nervus._api.delete("/events/{event_id}")
async def delete_event_api(event_id: str):
    return await action_delete_event({"event_id": event_id})


@nervus._api.get("/suggestions")
async def get_suggestions():
    return await action_suggest_schedule({})


@nervus.state
async def get_state():
    today = _today_str()
    with get_db() as conn:
        today_count = conn.execute(
            "SELECT COUNT(*) as c FROM events WHERE date(start_at) = ?", (today,)
        ).fetchone()["c"]
        next_event = conn.execute(
            "SELECT title, start_at FROM events WHERE start_at > ? ORDER BY start_at LIMIT 1",
            (datetime.utcnow().isoformat(),)
        ).fetchone()
    return {
        "today_events": today_count,
        "next_event": dict(next_event) if next_event else None,
    }


if __name__ == "__main__":
    nervus.run(port=int(os.getenv("APP_PORT", "8010")))
