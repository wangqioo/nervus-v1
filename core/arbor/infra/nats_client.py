"""
内存事件总线 — 替换 nats-py 客户端

提供 subscribe/publish 接口，事件在单进程内异步派发。
无需外部服务，零延迟。
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any, Callable, Coroutine

logger = logging.getLogger("nervus.infra.nats")

MessageCallback = Callable[[Any], Coroutine[Any, Any, None]]


@dataclass
class Msg:
    """模拟 nats-py Msg 对象"""
    subject: str
    data: bytes
    reply: str = ""

    def decode(self) -> str:
        return self.data.decode("utf-8")


class EventBus:
    """单进程事件总线 — 替代 NATS"""

    def __init__(self) -> None:
        self._subscriptions: list[tuple[str, MessageCallback]] = []

    async def connect(self, url: str = "") -> None:
        logger.info("EventBus ready (in-process, no NATS needed)")

    async def disconnect(self) -> None:
        self._subscriptions.clear()
        logger.info("EventBus disconnected")

    async def publish(self, subject: str, payload: str | dict | bytes) -> None:
        """发布事件到所有匹配的订阅者"""
        if isinstance(payload, dict):
            data = json.dumps(payload).encode()
        elif isinstance(payload, str):
            data = payload.encode()
        else:
            data = payload

        msg = Msg(subject=subject, data=data)
        for pattern, cb in self._subscriptions:
            if _subject_matches(subject, pattern):
                try:
                    await cb(msg)
                except Exception:
                    logger.exception("EventBus callback error for %s → %s", subject, pattern)

    async def subscribe(self, subject: str, cb: MessageCallback) -> None:
        self._subscriptions.append((subject, cb))
        logger.debug("EventBus subscribed: %s", subject)

    async def unsubscribe(self, subject: str) -> None:
        self._subscriptions = [(s, cb) for s, cb in self._subscriptions if s != subject]

    @property
    def is_connected(self) -> bool:
        return True


def _subject_matches(subject: str, pattern: str) -> bool:
    """NATS 风格主题匹配（精确 / * / >）"""
    if pattern == subject:
        return True
    if pattern.endswith(">"):
        return subject.startswith(pattern[:-1])
    sub_parts = subject.split(".")
    pat_parts = pattern.split(".")
    if len(sub_parts) != len(pat_parts):
        return False
    return all(p == "*" or p == sp for p, sp in zip(pat_parts, sub_parts))


_client: EventBus | None = None


def get_bus() -> EventBus:
    global _client
    if _client is None:
        _client = EventBus()
    return _client


# ── 向上兼容（nats_client.client / connect / disconnect / publish / subscribe） ──
client = get_bus()


async def connect(url: str = "") -> None:
    await get_bus().connect(url)


async def disconnect() -> None:
    await get_bus().disconnect()


async def publish(subject: str, payload: str | dict | bytes) -> None:
    await get_bus().publish(subject, payload)


async def subscribe(subject: str, cb: MessageCallback) -> None:
    await get_bus().subscribe(subject, cb)


async def unsubscribe(subject: str) -> None:
    await get_bus().unsubscribe(subject)
