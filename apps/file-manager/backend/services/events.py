import asyncio
import json
from typing import AsyncIterator

_subscribers: list[asyncio.Queue] = []


def subscribe() -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue()
    _subscribers.append(q)
    return q


def unsubscribe(q: asyncio.Queue) -> None:
    try:
        _subscribers.remove(q)
    except ValueError:
        pass


async def emit(data: dict) -> None:
    for q in list(_subscribers):
        await q.put(data)


async def stream(q: asyncio.Queue) -> AsyncIterator[str]:
    try:
        while True:
            try:
                data = await asyncio.wait_for(q.get(), timeout=25)
                yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
            except asyncio.TimeoutError:
                yield ": ping\n\n"
    finally:
        unsubscribe(q)
