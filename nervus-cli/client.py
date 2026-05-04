"""Nervus HTTP 客户端 — 对接 Arbor Core 及各 App"""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import httpx
import nats

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
        self._nc = None                     # NATS 连接
        self._seen_notif_ids: set[str] = set()
        self._message_cb = None             # 收到新消息时的回调
        self._status_cb = None              # 状态变化时的回调

    # ── 生命周期 ──────────────────────────────────────────────────────────

    async def connect(self):
        self._http = httpx.AsyncClient(base_url=config.ARBOR_URL, timeout=10.0)
        try:
            self._nc = await nats.connect(config.NATS_URL)
            await self._subscribe_responses()
            logger.info("NATS 已连接")
        except Exception as e:
            logger.warning("NATS 连接失败，将使用轮询模式: %s", e)
            self._nc = None

    async def close(self):
        if self._nc:
            await self._nc.close()
        if self._http:
            await self._http.aclose()

    def on_message(self, cb):
        """注册新消息回调: cb(ChatMessage)"""
        self._message_cb = cb

    def on_status(self, cb):
        """注册状态变化回调: cb(dict)"""
        self._status_cb = cb

    # ── 用户输入 ──────────────────────────────────────────────────────────

    async def send_text(self, text: str):
        """发送用户文本，通过 NATS 事件总线路由"""
        payload = {
            "text": text,
            "source": "cli",
            "timestamp": datetime.now().isoformat(),
        }
        if self._nc:
            await self._nc.publish(
                "system.user.input",
                json.dumps(payload).encode(),
            )
        else:
            # 降级：直接写入 events 表（通过 arbor HTTP）
            await self._post_event("system.user.input", payload)

    # ── NATS 订阅 ─────────────────────────────────────────────────────────

    async def _subscribe_responses(self):
        if not self._nc:
            return

        async def _on_msg(msg):
            try:
                data = json.loads(msg.data.decode())
                text = (
                    data.get("result")
                    or data.get("response")
                    or data.get("text")
                    or data.get("message")
                    or json.dumps(data, ensure_ascii=False)
                )
                source = msg.subject.split(".")[0]
                cm = ChatMessage(role="app", text=str(text), source=source)
                if self._message_cb:
                    asyncio.get_event_loop().call_soon_threadsafe(
                        lambda: asyncio.ensure_future(self._fire_message(cm))
                    )
            except Exception as e:
                logger.debug("NATS 消息解析失败: %s", e)

        # 订阅各 App 的响应和通知
        for subj in [
            "system.arbor.response",
            "system.cli.response",
            "reminder.>",
            "calendar.>",
            "memory.>",
            "knowledge.response",
        ]:
            await self._nc.subscribe(subj, cb=_on_msg)

    async def _fire_message(self, cm: ChatMessage):
        if self._message_cb:
            await self._message_cb(cm)

    # ── 轮询通知（无 NATS 时的降级方案）─────────────────────────────────

    async def poll_notifications(self):
        """后台轮询通知，定期调用此方法"""
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
                # 标记已读
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
            return {"nats": "unknown", "redis": "unknown", "postgres": "unknown"}

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

    # ── App 直接调用 ──────────────────────────────────────────────────────

    async def call_app_action(self, app_id: str, action: str, params: dict = {}) -> Any:
        url = f"{config.app_url(app_id)}/actions/{action}"
        try:
            async with httpx.AsyncClient(timeout=15.0) as c:
                r = await c.post(url, json=params)
                return r.json()
        except Exception as e:
            return {"error": str(e)}

    # ── 内部工具 ──────────────────────────────────────────────────────────

    async def _post_event(self, subject: str, payload: dict):
        try:
            await self._http.post("/events", json={"subject": subject, "payload": payload})
        except Exception as e:
            logger.debug("HTTP 事件发送失败: %s", e)

    @property
    def is_connected(self) -> bool:
        if self._http is None:
            return False
        if self._nc:
            return self._nc.is_connected
        return True  # HTTP 模式视为连接
