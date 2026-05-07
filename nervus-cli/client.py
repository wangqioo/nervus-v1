"""Nervus HTTP 客户端 — 对接 Arbor Core"""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable

import httpx

import config

logger = logging.getLogger("nervus.cli.client")


@dataclass
class ChatMessage:
    role: str           # "user" | "system" | "app"
    text: str
    source: str = ""    # app_id 或 "arbor"
    ts: datetime = field(default_factory=datetime.now)

    def label(self) -> str:
        if self.role == "user":
            return "你"
        if self.source:
            return self.source
        return "Nervus"


class NervusClient:
    def __init__(self):
        self._http: httpx.AsyncClient | None = None
        self._seen_notif_ids: set[str] = set()
        self._message_cb: Callable | None = None
        self._status_cb: Callable | None = None

    # ── 生命周期 ──────────────────────────────────────────────────────────

    async def connect(self):
        self._http = httpx.AsyncClient(base_url=config.ARBOR_URL, timeout=10.0)
        logger.info("已连接 Arbor Core: %s", config.ARBOR_URL)

    async def close(self):
        if self._http:
            await self._http.aclose()
            self._http = None

    def on_message(self, cb):
        self._message_cb = cb

    def on_status(self, cb):
        self._status_cb = cb

    # ── 用户输入 ──────────────────────────────────────────────────────────

    async def send_text(self, text: str):
        """发送用户文本（写入事件总线，由 Arbor Core 路由）"""
        payload = {
            "text": text,
            "source": "cli",
            "timestamp": datetime.now().isoformat(),
        }
        await self._post_event("system.user.input", payload)

    # ── 轮询通知 ──────────────────────────────────────────────────────────

    async def poll_notifications(self):
        """后台轮询通知，定期调用此方法"""
        if not self._http:
            return
        try:
            resp = await self._http.get("/notifications", params={"unread_only": True, "limit": 10})
            if resp.status_code != 200:
                return
            items = resp.json().get("notifications", [])
            for n in items:
                nid = str(n.get("id", ""))
                if nid in self._seen_notif_ids:
                    continue
                self._seen_notif_ids.add(nid)
                asyncio.ensure_future(self._mark_read(nid))
                cm = ChatMessage(
                    role="app",
                    text=f"[{n.get('title','')}] {n.get('body','')}",
                    source=n.get("metadata", {}).get("source_app", "arbor"),
                )
                if self._message_cb:
                    await self._message_cb(cm)
        except Exception as e:
            logger.debug("轮询通知失败: %s", e)

    async def _mark_read(self, nid: str):
        if not self._http:
            return
        try:
            await self._http.post(f"/notifications/{nid}/read")
        except Exception:
            pass

    # ── 系统状态 ──────────────────────────────────────────────────────────

    async def get_status(self) -> dict:
        try:
            r = await self._http.get("/status")
            return r.json()
        except Exception as e:
            return {"error": str(e)}

    async def get_health(self) -> dict[str, str]:
        try:
            r = await self._http.get("/health")
            return r.json().get("services", {})
        except Exception:
            return {"database": "unknown"}

    async def get_apps(self) -> list[dict]:
        try:
            r = await self._http.get("/apps")
            return r.json().get("apps", [])
        except Exception:
            return []

    async def get_recent_logs(self, limit: int = 10) -> list[dict]:
        try:
            r = await self._http.get("/logs", params={"limit": limit})
            return r.json().get("logs", [])
        except Exception:
            return []

    # ── 内部工具 ──────────────────────────────────────────────────────────

    async def _post_event(self, subject: str, payload: dict):
        if not self._http:
            return
        try:
            await self._http.post("/events", json={"subject": subject, "payload": payload})
        except Exception as e:
            logger.debug("事件发送失败: %s", e)

    @property
    def is_connected(self) -> bool:
        return self._http is not None
