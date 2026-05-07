"""
Notes Widget — 备忘录
"""

from __future__ import annotations

import json
from typing import Optional

from fastapi import HTTPException, Query
from pydantic import BaseModel

from .base import Widget, ConfirmIntent, _make_id, _now


# ── Schema ───────────────────────────────────────────────────

class NoteCreate(BaseModel):
    title: str
    content: str = ""
    tags: list[str] = []


class NoteUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    tags: Optional[list[str]] = None


# ── Widget ───────────────────────────────────────────────────

class NotesWidget(Widget):
    id = "notes"
    name = "备忘录"
    icon = "📝"

    def init_db(self) -> None:
        with self.get_db() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS notes (
                    id          TEXT PRIMARY KEY,
                    title       TEXT NOT NULL,
                    content     TEXT NOT NULL DEFAULT '',
                    tags        TEXT DEFAULT '[]',
                    pinned      INTEGER DEFAULT 0,
                    created_at  TEXT NOT NULL,
                    updated_at  TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_notes_updated ON notes(updated_at DESC);
            """)

    # ── CRUD ──────────────────────────────────────────────────

    def list(self, tag: str = "", query: str = "", limit: int = 50) -> list[dict]:
        with self.get_db() as conn:
            if query:
                rows = conn.execute(
                    "SELECT * FROM notes WHERE title LIKE ? OR content LIKE ? ORDER BY pinned DESC, updated_at DESC LIMIT ?",
                    (f"%{query}%", f"%{query}%", limit)
                ).fetchall()
            elif tag:
                rows = conn.execute(
                    "SELECT * FROM notes WHERE tags LIKE ? ORDER BY pinned DESC, updated_at DESC LIMIT ?",
                    (f'%"{tag}"%', limit)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM notes ORDER BY pinned DESC, updated_at DESC LIMIT ?",
                    (limit,)
                ).fetchall()
        return [_note_to_dict(r) for r in rows]

    def get(self, note_id: str) -> dict:
        with self.get_db() as conn:
            row = conn.execute("SELECT * FROM notes WHERE id=?", (note_id,)).fetchone()
        if not row:
            raise HTTPException(404, "笔记不存在")
        return _note_to_dict(row)

    def create(self, data: dict) -> dict:
        nid = _make_id()
        now = _now()
        tags = json.dumps(data.get("tags", []), ensure_ascii=False)
        with self.get_db() as conn:
            conn.execute(
                "INSERT INTO notes (id, title, content, tags, pinned, created_at, updated_at) VALUES (?,?,?,?,0,?,?)",
                (nid, data["title"], data.get("content", ""), tags, now, now)
            )
        return self.get(nid)

    def update(self, note_id: str, data: dict) -> dict:
        with self.get_db() as conn:
            row = conn.execute("SELECT * FROM notes WHERE id=?", (note_id,)).fetchone()
            if not row:
                raise HTTPException(404, "笔记不存在")
            now = _now()
            sets = []
            vals = []
            if "title" in data:
                sets.append("title=?")
                vals.append(data["title"])
            if "content" in data:
                sets.append("content=?")
                vals.append(data["content"])
            if "tags" in data:
                sets.append("tags=?")
                vals.append(json.dumps(data["tags"], ensure_ascii=False))
            if not sets:
                return _note_to_dict(row)
            sets.append("updated_at=?")
            vals.append(now)
            vals.append(note_id)
            conn.execute(f"UPDATE notes SET {', '.join(sets)} WHERE id=?", vals)
        return self.get(note_id)

    def delete(self, note_id: str) -> dict:
        with self.get_db() as conn:
            row = conn.execute("SELECT * FROM notes WHERE id=?", (note_id,)).fetchone()
            if not row:
                raise HTTPException(404, "笔记不存在")
            conn.execute("DELETE FROM notes WHERE id=?", (note_id,))
        return {"id": note_id, "status": "deleted"}

    def toggle_pin(self, note_id: str) -> dict:
        with self.get_db() as conn:
            row = conn.execute("SELECT * FROM notes WHERE id=?", (note_id,)).fetchone()
            if not row:
                raise HTTPException(404, "笔记不存在")
            now = _now()
            new_pinned = 0 if row["pinned"] else 1
            conn.execute("UPDATE notes SET pinned=?, updated_at=? WHERE id=?", (new_pinned, now, note_id))
        return self.get(note_id)

    def list_tags(self) -> list[str]:
        with self.get_db() as conn:
            rows = conn.execute("SELECT tags FROM notes").fetchall()
        tag_set = set()
        for row in rows:
            try:
                tag_set.update(json.loads(row["tags"] or "[]"))
            except Exception:
                pass
        return sorted(tag_set)

    # ── Widget 接口 ────────────────────────────────────────────

    def handle_read(self, intent: str, params: dict) -> dict:
        if intent == "get":
            return self.get(params.get("id", ""))
        if intent == "tags":
            return {"tags": self.list_tags()}
        return {
            "notes": self.list(
                tag=params.get("tag", ""),
                query=params.get("query", ""),
                limit=int(params.get("limit", 50))
            )
        }

    def execute_write(self, intent: str, params: dict) -> dict:
        if intent == "create":
            return {"note": self.create(params)}
        if intent == "update":
            return {"note": self.update(params.get("id", ""), params)}
        if intent == "delete":
            return self.delete(params.get("id", ""))
        if intent == "pin":
            return {"note": self.toggle_pin(params.get("id", ""))}
        return {"error": f"unknown intent: {intent}"}

    def get_state(self) -> dict:
        with self.get_db() as conn:
            total = conn.execute("SELECT COUNT(*) as c FROM notes").fetchone()["c"]
            pinned = conn.execute("SELECT COUNT(*) as c FROM notes WHERE pinned=1").fetchone()["c"]
            recent = conn.execute(
                "SELECT id, title, updated_at FROM notes ORDER BY updated_at DESC LIMIT 5"
            ).fetchall()
        return {
            "total_notes": total,
            "pinned_notes": pinned,
            "recent": [dict(r) for r in recent],
        }

    # ── 路由 ──────────────────────────────────────────────────

    def _register_routes(self) -> None:
        r = self.router

        @r.get("")
        def list_notes(tag: str = Query(""), q: str = Query(""), limit: int = Query(50)):
            return {"notes": self.list(tag=tag, query=q, limit=limit)}

        @r.post("")
        def create_note(body: NoteCreate):
            return {"note": self.create(body.model_dump())}

        @r.get("/tags")
        def list_tags():
            return {"tags": self.list_tags()}

        @r.get("/state")
        def state():
            return self.get_state()

        @r.get("/{note_id}")
        def get_note(note_id: str):
            return self.get(note_id)

        @r.put("/{note_id}")
        def update_note(note_id: str, body: NoteUpdate):
            return {"note": self.update(note_id, body.model_dump(exclude_none=True))}

        @r.delete("/{note_id}")
        def delete_note(note_id: str):
            return self.delete(note_id)

        @r.post("/{note_id}/pin")
        def toggle_pin(note_id: str):
            return {"note": self.toggle_pin(note_id)}


# ── 辅助 ─────────────────────────────────────────────────────

def _note_to_dict(row) -> dict:
    d = dict(row)
    try:
        d["tags"] = json.loads(d.get("tags", "[]"))
    except Exception:
        d["tags"] = []
    d["pinned"] = bool(d.get("pinned", 0))
    return d
